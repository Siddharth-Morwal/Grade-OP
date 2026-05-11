import uuid
from datetime import datetime, timezone
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database.postgres import get_db
from app.auth.dependencies import get_current_user, require_roles
from app.schemas.reviews import ReviewOut, OverridePayload

router = APIRouter(tags=["reviews"])

@router.get("/", response_model=List[ReviewOut])
async def list_pending_reviews(
    exam_id: Optional[str] = Query(None, description="Filter by exam"),
    review_status: Optional[str] = Query("pending", description="Filter by status: pending | approved | overridden"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_roles("teacher", "admin")),
):
    """List grades that have been flagged for human review."""
    from app.models.grade import Grade

    query = select(Grade).where(Grade.flagged_for_review.is_(True))

    if current_user.role == "teacher":
        from app.models.exam import Exam
        exam_subq = select(Exam.id).where(Exam.created_by == current_user.id).subquery()
        query = query.where(Grade.exam_id.in_(exam_subq))

    if exam_id:
        query = query.where(Grade.exam_id == uuid.UUID(exam_id))

    if review_status:
        query = query.where(Grade.review_status == review_status)

    result = await db.execute(
        query.order_by(Grade.created_at.desc()).offset(skip).limit(limit)
    )
    grades = result.scalars().all()

    return grades

@router.patch("/{grade_id}/approve", response_model=ReviewOut)
async def approve_grade(
    grade_id: str,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_roles("teacher", "admin")),
):
    """Approve an ML-generated grade as correct."""
    grade = await _get_flagged_grade(db, grade_id)
    _assert_not_already_reviewed(grade)

    grade.review_status = "approved"
    grade.reviewed_by = current_user.id
    grade.reviewed_at = datetime.now(timezone.utc)

    db.add(grade)
    await db.commit()
    await db.refresh(grade)

    return grade

@router.patch("/{grade_id}/override", response_model=ReviewOut)
async def override_grade(
    grade_id: str,
    payload: OverridePayload,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_roles("teacher", "admin")),
):
    """Override an ML-generated grade with a manual score."""
    grade = await _get_flagged_grade(db, grade_id)
    _assert_not_already_reviewed(grade)

    if payload.new_score < 0 or payload.new_score > grade.max_score:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"New score must be between 0 and {grade.max_score}",
        )

    grade.original_ml_score = grade.score
    grade.score = payload.new_score
    grade.review_status = "overridden"
    grade.reviewed_by = current_user.id
    grade.reviewed_at = datetime.now(timezone.utc)
    grade.override_reason = payload.override_reason

    db.add(grade)
    await db.commit()
    await db.refresh(grade)

    return grade

@router.get("/{grade_id}", response_model=ReviewOut)
async def get_review(
    grade_id: str,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_roles("teacher", "admin")),
):
    """Fetch a specific flagged grade / review."""
    return await _get_flagged_grade(db, grade_id)


async def _get_flagged_grade(db: AsyncSession, grade_id: str):
    """Fetch a grade that's flagged for review, or raise 404."""
    from app.models.grade import Grade

    result = await db.execute(
        select(Grade).where(
            Grade.id == uuid.UUID(grade_id),
            Grade.flagged_for_review.is_(True),
        )
    )
    grade = result.scalar_one_or_none()

    if not grade:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Review not found or grade is not flagged for review",
        )
    return grade

def _assert_not_already_reviewed(grade) -> None:
    """Raise 409 if a grade has already been approved or overridden."""
    if grade.review_status in ("approved", "overridden"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Grade has already been {grade.review_status}. Cannot action again.",
        )
