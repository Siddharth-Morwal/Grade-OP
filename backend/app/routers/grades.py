import uuid
import os
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, Header, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.database.postgres import get_db
from app.auth.dependencies import get_current_user, require_roles
from app.schemas.grades import GradeCreate, GradeOut

router = APIRouter(tags=["grades"])

ML_API_KEY = os.getenv("ML_PIPELINE_API_KEY", "change-me-in-production")

async def verify_ml_api_key(x_api_key: Optional[str] = Header(None)):
    """Dependency: validates the API key sent by the ML pipeline."""
    if not x_api_key or x_api_key != ML_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid or missing API key",
        )
    return x_api_key

@router.post("/", response_model=GradeOut, status_code=status.HTTP_201_CREATED)
async def submit_grade(
    payload: GradeCreate,
    db: AsyncSession = Depends(get_db),
    _api_key=Depends(verify_ml_api_key),
):
    """ML pipeline endpoint: submit a graded result for a student's exam."""
    from app.models.grade import Grade

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
        grade = Grade(**payload.model_dump())
        db.add(grade)
        await db.commit()
        await db.refresh(grade)
        return grade

@router.get("/", response_model=List[GradeOut])
async def list_grades(
    exam_id: Optional[str] = Query(None, description="Filter by exam"),
    student_id: Optional[str] = Query(None, description="Filter by student (admin/teacher)"),
    flagged_only: bool = Query(False, description="Only show flagged-for-review grades"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """List grades."""
    from app.models.grade import Grade

    query = select(Grade)

    if current_user.role == "student":
        query = query.where(Grade.student_id == current_user.id)
    else:
        if student_id:
            query = query.where(Grade.student_id == uuid.UUID(student_id))

    if exam_id:
        query = query.where(Grade.exam_id == uuid.UUID(exam_id))

    if flagged_only:
        query = query.where(Grade.flagged_for_review == True)

    result = await db.execute(query.offset(skip).limit(limit))
    grades = result.scalars().all()

    return grades

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

    if current_user.role == "student" and grade.student_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to view this grade",
        )

    return grade
