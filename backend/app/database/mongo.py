"""
app/database/mongo.py — Async MongoDB setup via Motor

WHAT THIS FILE DOES:
────────────────────
Manages the lifecycle of your MongoDB connection and exposes two things
every router will need:

  1. connect_mongo() / close_mongo()  ← called by main.py lifespan
  2. get_mongo_db()                   ← FastAPI dependency for routers
  3. get_collection(name)             ← convenience helper

WHY TWO DATABASES (Postgres + MongoDB) IN ONE PROJECT?
───────────────────────────────────────────────────────
This is the key architectural question — you are not using two databases
out of habit. Each solves a different problem:

  PostgreSQL (structured, relational)
  ────────────────────────────────────
  ✔ Users, exams, questions — rows with fixed columns and foreign keys
  ✔ Transactions: "assign exam + create question slots" must be atomic
  ✔ Complex joins: "show all questions for exams belonging to this user"
  ✔ Strong consistency guarantees

  MongoDB (flexible, document-oriented)
  ──────────────────────────────────────
  ✔ AI grade results — every LLM response has a different JSON shape
    (rubric feedback, confidence scores, model name, raw completion text)
    Forcing this into Postgres columns = constant schema migrations
  ✔ Rubric definitions — deeply nested JSON with per-question criteria
  ✔ TA review audit trail — free-form override notes and diff history
  ✔ Scan page metadata — variable OCR fields per question type

  The rule of thumb: if you need JOIN and transactions → Postgres.
  If your data is naturally a JSON document with variable shape → MongoDB.

DRIVER CHOICE — Motor:
─────────────────────
Motor is the official async MongoDB driver maintained by MongoDB, Inc.
It wraps PyMongo (the sync driver) in asyncio-compatible coroutines.

  pip install motor

Motor's `AsyncIOMotorClient` manages an internal connection pool just
like SQLAlchemy's engine — you create ONE client at startup and share it
across all requests.

GLOBAL CLIENT PATTERN — why we use a module-level variable:
────────────────────────────────────────────────────────────
Unlike SQLAlchemy where the engine is stateless and we can pass it
around easily, Motor's client holds the connection pool state.
The standard pattern is:

  module-level _client: AsyncIOMotorClient | None = None

  connect_mongo()  → creates _client, stores it here
  close_mongo()    → calls _client.close(), sets it to None
  get_mongo_db()   → returns _client[DATABASE_NAME]

This is functionally identical to a singleton — one pool, reused
everywhere, cleaned up on shutdown.
"""

import os
import logging
from typing import AsyncGenerator, Optional

from motor.motor_asyncio import (
    AsyncIOMotorClient,    # The connection pool + client
    AsyncIOMotorDatabase,  # Represents one database inside MongoDB
    AsyncIOMotorCollection,  # Represents one collection (like a SQL table)
)
from pymongo import ASCENDING, DESCENDING  # for creating indexes
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError

logger = logging.getLogger("grader.mongo")


# ─────────────────────────────────────────────────────────────────────────────
# 1.  CONFIGURATION
#
#     MONGO_URI:     Full connection string.  In development this is usually
#                    mongodb://localhost:27017 (no auth).
#                    In production, use a full Atlas URI like:
#                    mongodb+srv://user:pass@cluster.mongodb.net/?retryWrites=true
#
#     MONGO_DB_NAME: The database name inside MongoDB.
#                    MongoDB creates it automatically on first write — no
#                    CREATE DATABASE needed.
# ─────────────────────────────────────────────────────────────────────────────
MONGO_URI: str = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB_NAME: str = os.getenv("MONGO_DB_NAME", "hitl_grading")


# ─────────────────────────────────────────────────────────────────────────────
# 2.  MODULE-LEVEL STATE
#
#     These two variables hold the live client and database objects.
#     They start as None and are populated by connect_mongo().
#
#     WHY not create them at import time?
#     If you call AsyncIOMotorClient() at module import, it tries to
#     connect immediately. If MongoDB isn't running yet (e.g. during
#     unit tests or CI), the import itself fails.
#     Deferring to connect_mongo() gives you control over when the
#     connection actually happens.
# ─────────────────────────────────────────────────────────────────────────────
_client: Optional[AsyncIOMotorClient] = None
_db:     Optional[AsyncIOMotorDatabase] = None


# ─────────────────────────────────────────────────────────────────────────────
# 3.  COLLECTION NAMES — single source of truth
#
#     Define every collection name as a constant here so we never
#     mistype "grade_results" as "grades_results" in three different files.
#     Routers import these constants instead of bare strings.
#
#     WHAT GOES IN EACH COLLECTION:
#
#     GRADES_COLLECTION
#       One document per (exam_id, question_id, student_id) triple.
#       Contains the raw LLM output, parsed score, rubric sub-scores,
#       and model metadata.  Shape varies between rubric types.
#       Example document:
#         {
#           "exam_id": 42,              ← foreign key into Postgres
#           "question_id": 7,           ← foreign key into Postgres
#           "student_id": "s_abc123",
#           "score": 8,
#           "max_score": 10,
#           "model": "claude-sonnet-4-20250514",
#           "rubric_scores": {
#             "methodology": 3,
#             "evidence": 3,
#             "clarity": 2
#           },
#           "llm_feedback": "Strong methodology section...",
#           "raw_completion": "...",    ← full LLM response for audit
#           "graded_at": ISODate(...)
#         }
#
#     RUBRICS_COLLECTION
#       One document per exam_id. Stores the full rubric as structured JSON.
#       This is much more natural in Mongo than in Postgres (no EAV hacks).
#       Example document:
#         {
#           "exam_id": 42,
#           "questions": [
#             {
#               "question_id": 7,
#               "max_score": 10,
#               "criteria": [
#                 {"name": "methodology", "max": 4, "description": "..."},
#                 {"name": "evidence",    "max": 4, "description": "..."},
#                 {"name": "clarity",     "max": 2, "description": "..."}
#               ]
#             }
#           ]
#         }
#
#     REVIEWS_COLLECTION
#       TA review decisions and override history. Free-form override notes
#       are awkward in a typed column — Mongo handles them naturally.
#       Example document:
#         {
#           "grade_id": ObjectId("..."),  ← ref to grades collection
#           "ta_id": 15,
#           "status": "approved",         ← "approved" | "overridden"
#           "original_score": 8,
#           "override_score": 9,
#           "override_reason": "Partial credit for correct approach",
#           "reviewed_at": ISODate(...)
#         }
# ─────────────────────────────────────────────────────────────────────────────
GRADES_COLLECTION  = "grade_results"
RUBRICS_COLLECTION = "rubrics"
REVIEWS_COLLECTION = "ta_reviews"


# ─────────────────────────────────────────────────────────────────────────────
# 4.  LIFECYCLE — connect and close
#
#     main.py calls these from its lifespan context manager:
#
#         await connect_mongo()   # startup
#         yield
#         await close_mongo()    # shutdown
# ─────────────────────────────────────────────────────────────────────────────
async def connect_mongo() -> None:
    """
    Create the Motor client and store it in module-level state.
    Runs a ping to verify the server is reachable before returning.

    Motor's client constructor does NOT actually connect — the first
    real network call happens here via the ping command.
    """
    global _client, _db

    logger.info(f"Connecting to MongoDB at {MONGO_URI!r}...")

    _client = AsyncIOMotorClient(
        MONGO_URI,

        # ── Connection pool ───────────────────────────────────────────────
        # Motor defaults to maxPoolSize=100 which is fine for most apps.
        # Tune these if you have specific concurrency requirements.
        maxPoolSize=20,
        minPoolSize=2,

        # ── Timeouts ──────────────────────────────────────────────────────
        # serverSelectionTimeoutMS: how long to wait for a MongoDB server
        # to respond before raising ServerSelectionTimeoutError.
        # 5 seconds is reasonable for startup; increase for Atlas.
        serverSelectionTimeoutMS=5_000,

        # connectTimeoutMS: how long to wait when opening a new TCP socket.
        connectTimeoutMS=3_000,

        # socketTimeoutMS: how long to wait for a response on an open socket.
        socketTimeoutMS=30_000,

        # ── Reliability ───────────────────────────────────────────────────
        # retryWrites: automatically retry one-time write failures caused
        # by network blips or primary failover (Atlas / replica sets).
        retryWrites=True,

        # ── App identification ────────────────────────────────────────────
        # Appears in MongoDB Atlas monitoring and db.currentOp() output.
        # Invaluable when debugging which service is hammering the DB.
        appname="hitl-grading-server",
    )

    # Select the database (doesn't create it — MongoDB does that on first write)
    _db = _client[MONGO_DB_NAME]

    # ── Verify connectivity ───────────────────────────────────────────────────
    # Motor is lazy — the client constructor never actually connects.
    # We force a real network call here so startup fails fast if MongoDB
    # is unreachable, rather than failing silently on the first request.
    try:
        await _client.admin.command("ping")
        logger.info(f"MongoDB connected — database: '{MONGO_DB_NAME}'")
    except (ConnectionFailure, ServerSelectionTimeoutError) as exc:
        logger.error(f"MongoDB connection failed: {exc}")
        raise  # Let the lifespan handler propagate this — don't start the server

    # ── Create indexes ────────────────────────────────────────────────────────
    # Indexes speed up queries dramatically. Build them at startup so they
    # exist before any request comes in.
    # create_index() is idempotent — safe to call on every startup.
    await _create_indexes()


async def close_mongo() -> None:
    """
    Close the Motor client and release all pooled connections.
    Called by main.py on shutdown.
    """
    global _client, _db
    if _client is not None:
        _client.close()
        _client = None
        _db = None
        logger.info("MongoDB connection closed.")


# ─────────────────────────────────────────────────────────────────────────────
# 5.  INDEX CREATION
#
#     WHAT ARE INDEXES?
#     Without an index, MongoDB scans every document to find matches
#     (a "collection scan").  On a collection with 100k grade documents,
#     a query like {"exam_id": 42} might read all 100k docs.
#     An index on "exam_id" turns that into a fast B-tree lookup.
#
#     WHICH FIELDS TO INDEX:
#     Any field you filter on (WHERE clause equivalent) or sort by.
#
#     COMPOUND INDEXES:
#     An index on (exam_id, question_id) speeds up queries that filter
#     on BOTH fields.  The field order matters — put the most selective
#     (fewest matching docs) field first.
# ─────────────────────────────────────────────────────────────────────────────
async def _create_indexes() -> None:
    """
    Build indexes for all collections.
    Called once during connect_mongo() startup.
    create_index() is idempotent — safe on every restart.
    """
    if _db is None:
        return

    # ── grade_results indexes ─────────────────────────────────────────────────
    grades = _db[GRADES_COLLECTION]

    # Compound: look up all grades for a specific question in an exam
    await grades.create_index(
        [("exam_id", ASCENDING), ("question_id", ASCENDING)],
        name="idx_grades_exam_question",
    )

    # Look up all grades for a student across exams (TA review view)
    await grades.create_index(
        [("student_id", ASCENDING), ("graded_at", DESCENDING)],
        name="idx_grades_student_time",
    )

    # ── rubrics indexes ───────────────────────────────────────────────────────
    rubrics = _db[RUBRICS_COLLECTION]

    # One rubric per exam — make exam_id unique so we can't duplicate
    await rubrics.create_index(
        [("exam_id", ASCENDING)],
        name="idx_rubrics_exam",
        unique=True,    # Enforces one rubric per exam at the DB level
    )

    # ── ta_reviews indexes ────────────────────────────────────────────────────
    reviews = _db[REVIEWS_COLLECTION]

    # Look up all reviews for a grade document
    await reviews.create_index(
        [("grade_id", ASCENDING)],
        name="idx_reviews_grade",
    )

    # Look up all reviews a specific TA has made (admin reporting)
    await reviews.create_index(
        [("ta_id", ASCENDING), ("reviewed_at", DESCENDING)],
        name="idx_reviews_ta_time",
    )

    logger.info("MongoDB indexes verified.")


# ─────────────────────────────────────────────────────────────────────────────
# 6.  FASTAPI DEPENDENCY — get_mongo_db
#
#     Works exactly like postgres.py's get_db(), but simpler because
#     MongoDB has no explicit transaction to commit or roll back
#     (individual document writes are atomic by default).
#
#     Usage in a router:
#
#         from fastapi import Depends
#         from motor.motor_asyncio import AsyncIOMotorDatabase
#         from app.database.mongo import get_mongo_db, GRADES_COLLECTION
#
#         @router.get("/grades/{exam_id}")
#         async def list_grades(
#             exam_id: int,
#             mongo: AsyncIOMotorDatabase = Depends(get_mongo_db),
#         ):
#             cursor = mongo[GRADES_COLLECTION].find({"exam_id": exam_id})
#             grades = await cursor.to_list(length=100)
#             return grades
# ─────────────────────────────────────────────────────────────────────────────
async def get_mongo_db() -> AsyncGenerator[AsyncIOMotorDatabase, None]:
    """
    FastAPI dependency that yields the Motor database object.

    Unlike Postgres sessions, we don't open/close anything per request —
    we yield the shared database handle backed by the module-level pool.
    The guard raises a clear error if called before connect_mongo().
    """
    if _db is None:
        raise RuntimeError(
            "MongoDB is not connected. "
            "Ensure connect_mongo() ran during the app lifespan startup."
        )
    yield _db


# ─────────────────────────────────────────────────────────────────────────────
# 7.  CONVENIENCE HELPER — get_collection
#
#     For use OUTSIDE of FastAPI route handlers (e.g. background tasks,
#     CLI scripts, or the LLM grading pipeline that runs outside a request).
#
#     In a route handler, always prefer Depends(get_mongo_db) — it's more
#     testable because you can swap in a mock database during tests.
#
#     Example (background task):
#
#         from app.database.mongo import get_collection, GRADES_COLLECTION
#
#         async def save_grade_result(grade: dict) -> str:
#             col = get_collection(GRADES_COLLECTION)
#             result = await col.insert_one(grade)
#             return str(result.inserted_id)
# ─────────────────────────────────────────────────────────────────────────────
def get_collection(name: str) -> AsyncIOMotorCollection:
    """
    Return a Motor collection by name from the module-level database.
    Raises RuntimeError if called before connect_mongo().
    """
    if _db is None:
        raise RuntimeError(
            "MongoDB is not connected. Call connect_mongo() first."
        )
    return _db[name]


# ─────────────────────────────────────────────────────────────────────────────
# WHAT TO INSTALL
# ─────────────────────────────────────────────────────────────────────────────
#
#   pip install motor pymongo
#
#   Add to requirements.txt:
#     motor>=3.4        # async MongoDB driver (wraps pymongo)
#     pymongo>=4.6      # underlying sync driver (motor's dependency)
#
# ─────────────────────────────────────────────────────────────────────────────
