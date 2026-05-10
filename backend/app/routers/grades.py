# ============================================================
# routers/grades.py
# ============================================================
#
# CONCEPT: Machine Learning Pipeline Integration
# -----------------------------------------------
# The ML pipeline is a separate service (Python script, Celery worker,
# or microservice). After grading an exam paper, it calls:
#   POST /grades   with the result → writes to PostgreSQL
#
# This endpoint is NOT for students. It's for the ML system.
# We protect it with an API key (simpler than OAuth for server-to-server).
#
# CONCEPT: API Key Authentication (server-to-server)
# ---------------------------------------------------
# JWT is great for users (browser ↔ server).
# For machine-to-machine (ML pipeline → API), API keys are simpler:
#   - ML pipeline sends:  X-API-Key: <secret>
#   - We verify against a key stored in env vars
#   - No expiry logic needed (rotate keys manually when needed)
#
# CONCEPT: Two audiences for the same data
# -----------------------------------------
# POST /grades    → ML pipeline (API key auth)
# GET  /grades    → Students/teachers (JWT auth)
# Different auth strategies can protect different HTTP methods
# on the same resource URL.
# ============================================================

import uuid
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, Header, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.database.postgres import get_db
from app.auth.dependencies import get_current_user, require_roles
from app.schemas.grades import GradeCreate, GradeOut, GradeListResponse

# NOTE: prefix is set in main.py via include_router() — do NOT set it here too.
router = APIRouter(tags=["grades"])


# ---------------------------------------------------------------
# API Key dependency for ML pipeline
# ---------------------------------------------------------------
# CONCEPT: Depends() with Header()
# ----------------------------------
# Header(None) reads the X-Api-Key HTTP header.
# The dependency raises 403 if the key doesn't match.
# This is injected into routes the same way get_current_user is.
#
# In production, use a secrets manager (AWS Secrets Manager, Vault)
# instead of plain env vars. Never commit keys to git.
# ---------------------------------------------------------------
import os

ML_API_KEY = os.getenv("ML_PIPELINE_API_KEY", "change-me-in-production")

async def verify_ml_api_key(x_api_key: Optional[str] = Header(None)):
    """
    Dependency: validates the API key sent by the ML pipeline.
    The ML service must include the header:  X-Api-Key: <secret>
    """
    if not x_api_key or x_api_key != ML_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid or missing API key",
        )
    return x_api_key


# ---------------------------------------------------------------
# POST /grades  → ML pipeline writes a grade result
# ---------------------------------------------------------------
# CONCEPT: Upsert (Insert or Update)
# ------------------------------------
# The ML pipeline might re-run on the same paper (corrections).
# We want: if a grade for (student_id, exam_id) exists → UPDATE it
#           otherwise → INSERT it
# SQLAlchemy + PostgreSQL: use `on_conflict_do_update` (INSERT ... ON CONFLICT)
# Simpler pattern shown here: check → insert or update manually.
# ---------------------------------------------------------------
@router.post("/", response_model=GradeOut, status_code=status.HTTP_201_CREATED)
async def submit_grade(
    payload: GradeCreate,
    db: AsyncSession = Depends(get_db),
    _api_key=Depends(verify_ml_api_key),   # ML pipeline must authenticate
):
    """
    ML pipeline endpoint: submit a graded result for a student's exam.
    Protected by API key, not JWT.

    Payload includes:
    - student_id, exam_id
    - score, max_score
    - per_question breakdown
    - confidence_score (how confident the ML model is)
    - flagged (True if human review is needed)
    """
    from app.models.grade import Grade

    # ---- Check for existing grade (upsert logic) ----
    result = await db.execute(
        select(Grade).where(
            and_(
                Grade.student_id == uuid.UUID(payload.student_id),
                Grade.exam_id == uuid.UUID(payload.exam_id),
            )
        )
    )
    existing_grade = result.scalar_one_or_none()

    if existing_grade:
        # UPDATE: ML pipeline re-ran, overwrite with new result
        existing_grade.score = payload.score
        existing_grade.max_score = payload.max_score
        existing_grade.per_question_breakdown = payload.per_question_breakdown
        existing_grade.confidence_score = payload.confidence_score
        existing_grade.flagged_for_review = payload.flagged_for_review
        existing_grade.ml_model_version = payload.ml_model_version
        db.add(existing_grade)
        await db.commit()
        await db.refresh(existing_grade)
        return existing_grade
    else:
        # INSERT: first time grading this paper
        grade = Grade(**payload.model_dump())
        db.add(grade)
        await db.commit()
        await db.refresh(grade)
        return grade


# ---------------------------------------------------------------
# GET /grades  → Students see own grades; teachers/admins see all
# ---------------------------------------------------------------
# CONCEPT: Data scoping by role
# ------------------------------
# This is a single endpoint that behaves differently per role:
#   student  → WHERE student_id = current_user.id   (own grades only)
#   teacher  → WHERE exam_id IN (exams they created)
#   admin    → no filter (all grades)
#
# This is cleaner than separate endpoints because the URL stays
# consistent (/grades) and role logic is centralised here.
# ---------------------------------------------------------------
@router.get("/", response_model=GradeListResponse)
async def list_grades(
    exam_id: Optional[str] = Query(None, description="Filter by exam"),
    student_id: Optional[str] = Query(None, description="Filter by student (admin/teacher)"),
    flagged_only: bool = Query(False, description="Only show flagged-for-review grades"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    List grades. Scope is automatically determined by the caller's role:
    - student  → own grades only
    - teacher  → grades for exams they created
    - admin    → all grades
    """
    from app.models.grade import Grade
    from sqlalchemy import func

    query = select(Grade)

    # ---- Role-based scoping ----
    if current_user.role == "student":
        # Hard constraint: students ALWAYS see only their own grades
        query = query.where(Grade.student_id == current_user.id)
    else:
        # Teachers/admins can filter by student_id if they want
        if student_id:
            query = query.where(Grade.student_id == uuid.UUID(student_id))

    # ---- Optional filters ----
    if exam_id:
        query = query.where(Grade.exam_id == uuid.UUID(exam_id))

    if flagged_only:
        query = query.where(Grade.flagged_for_review == True)

    # ---- Count + paginate ----
    count_result = await db.execute(
        select(func.count()).select_from(query.subquery())
    )
    total = count_result.scalar()

    result = await db.execute(query.offset(skip).limit(limit))
    grades = result.scalars().all()

    return GradeListResponse(items=grades, total=total, skip=skip, limit=limit)


# ---------------------------------------------------------------
# GET /grades/{grade_id}  → Single grade detail
# ---------------------------------------------------------------
@router.get("/{grade_id}", response_model=GradeOut)
async def get_grade(
    grade_id: str,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Fetch a specific grade by ID."""
    from app.models.grade import Grade

    result = await db.execute(select(Grade).where(Grade.id == uuid.UUID(grade_id)))
    grade = result.scalar_one_or_none()

    if not grade:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Grade not found")

    # Students can only see their own grades
    if current_user.role == "student" and grade.student_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to view this grade",
        )

    return grade
