# ============================================================
# routers/questions.py
# ============================================================
#
# CONCEPT: Why MongoDB for Questions?
# -------------------------------------
# Questions have wildly different shapes:
#   MCQ:   { text, options: [A,B,C,D], correct_answer, marks }
#   Essay: { text, word_limit, rubric: {...}, marks }
#   Code:  { text, language, starter_code, test_cases: [...], marks }
#
# In PostgreSQL you'd need multiple tables + complex JOINs,
# or a messy JSONB column. MongoDB's document model fits naturally —
# each question is just a document with whatever fields it needs.
#
# CONCEPT: Motor (async MongoDB driver)
# ----------------------------------------
# PyMongo is synchronous → blocks the event loop in async FastAPI.
# Motor wraps PyMongo with async/await support.
# Usage is almost identical to PyMongo, just add `await`.
#
# CONCEPT: Mixing two databases
# --------------------------------
# exam metadata (title, subject, file) → PostgreSQL (structured)
# exam questions                        → MongoDB  (flexible)
# They link via exam_id (UUID string stored as a field in Mongo docs)
# ============================================================

import uuid
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.database.mongo import get_mongo_db
from app.database.postgres import get_db
from app.auth.dependencies import get_current_user, require_roles
from app.schemas.questions import QuestionCreate, QuestionOut, QuestionUpdate

# NOTE: prefix is set in main.py via include_router() — do NOT set it here too.
router = APIRouter(tags=["questions"])

COLLECTION = "questions"   # MongoDB collection name (like a SQL table)


# ---------------------------------------------------------------
# Helper: ensure exam exists in Postgres before touching Mongo
# ---------------------------------------------------------------
# CONCEPT: Cross-database integrity
# ----------------------------------
# MongoDB has no foreign key constraints. If you store exam_id in Mongo
# but the exam was deleted from Postgres, you get orphaned documents.
# Solution: manually validate the foreign key in your application layer.
# ---------------------------------------------------------------
async def _verify_exam_exists(exam_id: str, db) -> None:
    from app.models.exam import Exam
    from sqlalchemy import select

    result = await db.execute(select(Exam).where(Exam.id == uuid.UUID(exam_id)))
    if not result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Exam '{exam_id}' does not exist",
        )


# ---------------------------------------------------------------
# GET /questions/{exam_id}  → List all questions for an exam
# ---------------------------------------------------------------
# CONCEPT: MongoDB find() with filters
# --------------------------------------
# mongo_db["questions"].find({"exam_id": exam_id})
# This is a cursor — call .to_list(length=N) to get results.
# MongoDB auto-creates the collection on first insert (no migrations!).
#
# CONCEPT: _id in MongoDB
# -------------------------
# MongoDB stores documents with an "_id" field (ObjectId by default).
# ObjectId is not JSON-serializable. We store our own UUID as "id"
# and convert _id to string when returning documents.
# ---------------------------------------------------------------
@router.get("/{exam_id}", response_model=List[QuestionOut])
async def list_questions(
    exam_id: str,
    question_type: Optional[str] = Query(None, description="Filter by: mcq, essay, code"),
    db=Depends(get_db),
    mongo: AsyncIOMotorDatabase = Depends(get_mongo_db),
    current_user=Depends(get_current_user),
):
    """
    Return all questions for a given exam.
    Students see questions only for published exams.
    """
    await _verify_exam_exists(exam_id, db)

    # ---- Build Mongo filter ----
    mongo_filter = {"exam_id": exam_id}
    if question_type:
        mongo_filter["type"] = question_type

    # ---- Query MongoDB ----
    # find() returns a cursor; to_list materializes it into a Python list.
    # limit=0 means "no limit" in Motor — careful in production; always limit.
    cursor = mongo[COLLECTION].find(mongo_filter).sort("order", 1)  # sort by question order
    raw_docs = await cursor.to_list(length=500)

    # ---- Serialize: convert ObjectId → string ----
    questions = []
    for doc in raw_docs:
        doc["_id"] = str(doc["_id"])   # ObjectId → str for JSON serialization
        questions.append(doc)

    return questions


# ---------------------------------------------------------------
# POST /questions/{exam_id}  → Add a question to an exam
# ---------------------------------------------------------------
# CONCEPT: insert_one() returns InsertOneResult
# -----------------------------------------------
# result.inserted_id → the ObjectId of the new document
# We store our own UUID as "id" for consistency with the rest of the API.
# ---------------------------------------------------------------
@router.post("/{exam_id}", response_model=QuestionOut, status_code=status.HTTP_201_CREATED)
async def create_question(
    exam_id: str,
    payload: QuestionCreate,
    db=Depends(get_db),
    mongo: AsyncIOMotorDatabase = Depends(get_mongo_db),
    current_user=Depends(require_roles("teacher", "admin")),
):
    """Add a question to an exam. Teachers and admins only."""
    await _verify_exam_exists(exam_id, db)

    # Build the document to insert
    doc = {
        "id": str(uuid.uuid4()),          # Our own UUID (stable, URL-safe)
        "exam_id": exam_id,
        "created_by": str(current_user.id),
        **payload.model_dump(),           # Spread the Pydantic schema (type, text, marks, etc.)
    }

    result = await mongo[COLLECTION].insert_one(doc)
    doc["_id"] = str(result.inserted_id)  # Add the MongoDB _id for the response

    return doc


# ---------------------------------------------------------------
# PATCH /questions/{exam_id}/{question_id}  → Update a question
# ---------------------------------------------------------------
# CONCEPT: MongoDB update_one()
# ------------------------------
# update_one(filter, update_doc)
# filter    → which document(s) to match
# $set      → MongoDB operator: "set only these fields" (like SQL's UPDATE SET)
# Without $set, you'd REPLACE the entire document — dangerous!
# ---------------------------------------------------------------
@router.patch("/{exam_id}/{question_id}", response_model=QuestionOut)
async def update_question(
    exam_id: str,
    question_id: str,
    payload: QuestionUpdate,
    mongo: AsyncIOMotorDatabase = Depends(get_mongo_db),
    current_user=Depends(require_roles("teacher", "admin")),
):
    """Partially update a question. Teachers and admins only."""
    update_data = payload.model_dump(exclude_unset=True)  # Only sent fields

    if not update_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields provided for update",
        )

    result = await mongo[COLLECTION].update_one(
        {"id": question_id, "exam_id": exam_id},  # filter
        {"$set": update_data},                     # update — $set is critical!
    )

    if result.matched_count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Question '{question_id}' not found in exam '{exam_id}'",
        )

    # Fetch and return the updated document
    updated = await mongo[COLLECTION].find_one({"id": question_id})
    updated["_id"] = str(updated["_id"])
    return updated


# ---------------------------------------------------------------
# DELETE /questions/{exam_id}/{question_id}
# ---------------------------------------------------------------
# CONCEPT: delete_one() vs delete_many()
# ----------------------------------------
# Always use delete_one() with a unique filter when deleting a specific doc.
# delete_many() + a wrong filter = data loss nightmare.
# ---------------------------------------------------------------
@router.delete("/{exam_id}/{question_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_question(
    exam_id: str,
    question_id: str,
    mongo: AsyncIOMotorDatabase = Depends(get_mongo_db),
    _teacher=Depends(require_roles("teacher", "admin")),
):
    """Delete a single question. Teachers and admins only."""
    result = await mongo[COLLECTION].delete_one(
        {"id": question_id, "exam_id": exam_id}
    )

    if result.deleted_count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Question not found",
        )
