"""
app/database/postgres.py — Async PostgreSQL setup via SQLAlchemy

WHAT THIS FILE DOES (read this first):
──────────────────────────────────────
This file is the "foundation layer" for your entire backend.
It creates three things that everything else depends on:

  1. engine   — the async connection pool to PostgreSQL
  2. Session  — a factory that produces per-request database sessions
  3. Base     — the parent class for all your ORM models

Every router that needs to talk to PostgreSQL will:
  a) import `get_db` from this file
  b) declare it as a FastAPI dependency →  db: AsyncSession = Depends(get_db)
  c) use `db` to run queries

# NOTE: `X | None` union syntax requires Python 3.10+.
# If you are on Python 3.8/3.9, change these to Optional[AsyncIOMotorClient]
# and import Optional from typing.

DRIVER CHOICE — why asyncpg?
──────────────────────────────
Python has two PostgreSQL drivers:
  • psycopg2    — synchronous (blocks the thread while waiting for DB)
  • asyncpg     — async (yields the thread back to the event loop while waiting)

FastAPI is built on asyncio. Using psycopg2 with FastAPI would block the
entire event loop every time a query runs, destroying concurrency.
asyncpg lets FastAPI handle other requests while we wait for Postgres.

The SQLAlchemy connection URL for asyncpg uses the dialect string:
  postgresql+asyncpg://user:password@host:port/dbname

CONNECTION POOLING — why it matters:
──────────────────────────────────────
Opening a new TCP connection to PostgreSQL is expensive (~50ms).
A connection pool keeps N connections permanently open and reuses them.
SQLAlchemy's AsyncEngine manages this pool automatically.

Key pool settings:
  pool_size        — steady-state connections kept alive (default 5)
  max_overflow     — extra connections allowed under heavy load (default 10)
  pool_timeout     — seconds to wait for a free connection before error (30)
  pool_recycle     — seconds before a connection is replaced (prevents stale)

DEPENDENCY INJECTION — the `get_db` pattern:
─────────────────────────────────────────────
FastAPI's Depends() system calls `get_db` before each request and injects
the yielded session into your route function.  After the route returns,
execution resumes after `yield` — so the finally block always runs,
even if the route raised an exception. This guarantees every session
is closed and never leaks.
"""

import os
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,           # The async-aware session class
    async_sessionmaker,     # Factory that creates sessions (replaces sessionmaker)
    create_async_engine,    # Creates the async connection pool
)
from sqlalchemy.orm import DeclarativeBase

import logging

logger = logging.getLogger("grader.postgres")


# ─────────────────────────────────────────────────────────────────────────────
# 1.  DATABASE URL
#     We read from an environment variable so we never hard-code credentials
#     in source code (which would end up in git).
#
#     In development, create a .env file (never commit it!) and load it with
#     python-dotenv.  In production, set the env var in your container/server.
#
#     Example .env:
#         DATABASE_URL=postgresql+asyncpg://grader:secret@localhost:5432/hitl_db
#
#     If DATABASE_URL is not set, we fall back to a local dev default so the
#     app still starts for first-time setup.
# ─────────────────────────────────────────────────────────────────────────────
DATABASE_URL: str = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://grader:secret@localhost:5432/hitl_db",   # dev fallback
)

# Safety guard: asyncpg MUST be in the URL.
# If someone accidentally sets a psycopg2-style URL, we catch it early.
if "postgresql+asyncpg" not in DATABASE_URL:
    raise ValueError(
        "DATABASE_URL must use the 'postgresql+asyncpg://' scheme for async support. "
        f"Got: {DATABASE_URL!r}"
    )


# ─────────────────────────────────────────────────────────────────────────────
# 2.  ENGINE  (the connection pool)
#
#     create_async_engine() does NOT connect immediately — it builds the pool
#     configuration. The first real connection happens on the first query.
#
#     echo=True prints every SQL statement SQLAlchemy generates.
#     VERY useful while learning, but turn it off in production (it's noisy).
#     Controlled via the SQLALCHEMY_ECHO env var: set to "true" to enable.
# ─────────────────────────────────────────────────────────────────────────────
engine = create_async_engine(
    DATABASE_URL,

    # ── Logging ──────────────────────────────────────────────────────────────
    echo=os.getenv("SQLALCHEMY_ECHO", "false").lower() == "true",

    # ── Pool tuning ──────────────────────────────────────────────────────────
    # For a small exam-grading system with a few concurrent TAs, these are fine.
    # Increase pool_size + max_overflow as your load grows.
    pool_size=5,           # Keep 5 connections alive at all times
    max_overflow=10,       # Allow 10 extra under bursts (15 total max)
    pool_timeout=30,       # Raise after 30s waiting for a free connection
    pool_recycle=1800,     # Replace connections older than 30 minutes
                           # (prevents "server closed the connection unexpectedly")
    pool_pre_ping=True,    # Before using a connection, send a cheap ping to
                           # verify it is still alive. Guards against stale
                           # connections after a DB restart.
)

logger.info("Async PostgreSQL engine created (pool_size=5, max_overflow=10).")


# ─────────────────────────────────────────────────────────────────────────────
# 3.  SESSION FACTORY
#
#     async_sessionmaker is the async equivalent of SQLAlchemy's sessionmaker.
#     It is a *factory* — calling it returns a new AsyncSession each time.
#
#     expire_on_commit=False:
#       By default SQLAlchemy expires (clears) all attributes on a model
#       after db.commit(), so accessing them would trigger a new SELECT.
#       In async code that causes "MissingGreenlet" errors because SQLAlchemy
#       tries to run that SELECT outside an async context.
#       Setting expire_on_commit=False keeps the in-memory values intact
#       after commit, which is the right default for async FastAPI apps.
# ─────────────────────────────────────────────────────────────────────────────
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


# ─────────────────────────────────────────────────────────────────────────────
# 4.  DECLARATIVE BASE
#
#     DeclarativeBase is the parent class for every SQLAlchemy model.
#     When you write:
#
#         class Exam(Base):
#             __tablename__ = "exams"
#             id = mapped_column(Integer, primary_key=True)
#             ...
#
#     SQLAlchemy registers that class in Base.metadata — a registry of all
#     tables. That's what main.py uses here:
#
#         await conn.run_sync(Base.metadata.create_all)
#
#     This creates all tables that don't exist yet. It never drops or
#     modifies existing tables, so it is safe to call on every startup.
#     (For schema *changes* use Alembic migrations instead.)
# ─────────────────────────────────────────────────────────────────────────────
class Base(DeclarativeBase):
    """
    Parent class for all ORM models in this project.

    Usage in models/exam.py:
        from app.database.postgres import Base

        class Exam(Base):
            __tablename__ = "exams"
            ...
    """
    pass


# ─────────────────────────────────────────────────────────────────────────────
# 5.  DEPENDENCY — get_db
#
#     This is an async generator used as a FastAPI dependency.
#     FastAPI calls it before each request, injects the session, then
#     resumes it (the finally block) after the request completes.
#
#     Usage in a router:
#
#         from fastapi import Depends
#         from app.database.postgres import get_db
#         from sqlalchemy.ext.asyncio import AsyncSession
#
#         @router.get("/exams/{exam_id}")
#         async def get_exam(exam_id: int, db: AsyncSession = Depends(get_db)):
#             result = await db.execute(select(Exam).where(Exam.id == exam_id))
#             exam = result.scalar_one_or_none()
#             if exam is None:
#                 raise HTTPException(status_code=404, detail="Exam not found")
#             return exam
#
#     WHY yield AND NOT return?
#       `yield` turns this into a generator. FastAPI runs everything before
#       `yield` (setup), injects the value, runs your route, then runs
#       everything after `yield` (teardown). The `finally` block ensures
#       cleanup happens even when the route raises an HTTPException.
# ─────────────────────────────────────────────────────────────────────────────
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency that yields a database session per request.

    Opens a session → yields it to the route → closes it when done.
    `async with AsyncSessionLocal()` automatically closes the session on exit,
    so we must NOT call session.close() manually — doing so would close it
    twice and raise sqlalchemy.exc.InvalidRequestError in SQLAlchemy 2.x.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            # If the route completes without raising, commit any pending changes.
            # (Routes can also call db.commit() themselves for more control.)
            await session.commit()
        except Exception:
            # Something went wrong — roll back to keep the DB consistent.
            await session.rollback()
            raise
        # NOTE: Do NOT add `finally: await session.close()` here.
        # The `async with` context manager above already handles closing.
        # A second close() call raises InvalidRequestError in SQLAlchemy 2.x.


# ─────────────────────────────────────────────────────────────────────────────
# WHAT TO INSTALL
# ─────────────────────────────────────────────────────────────────────────────
#
#   pip install sqlalchemy asyncpg
#
#   Add to requirements.txt:
#     sqlalchemy>=2.0          # v2 introduced the modern async API we use here
#     asyncpg>=0.29            # the async Postgres driver
#
#   Optional but strongly recommended for schema migrations:
#     alembic>=1.13            # run: alembic init alembic
#
# ─────────────────────────────────────────────────────────────────────────────
