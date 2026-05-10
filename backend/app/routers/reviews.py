# ============================================================
# routers/reviews.py
# ============================================================
#
# CONCEPT: Human-in-the-loop Review Workflow
# -------------------------------------------
# The ML pipeline grades papers automatically, but sets
# `flagged_for_review = True` when it's unsure (low confidence).
# A human teacher then:
#   PATCH /reviews/{id}/approve  → accept the ML grade as-is
#   PATCH /reviews/{id}/override → replace the ML grade with a manual one
#
# This is a state machine:
#   pending → approved
#   pending → overridden
#
# CONCEPT: Why PATCH and not PUT?
# --------------------------------
# We're changing ONE thing (status + maybe score).
# PUT would require sending the full resource.
# PATCH is semantically correct for partial state transitions.
#
# CONCEPT: Audit Trail
# ----------------------
# For any grading system, you need to know:
#   - WHO approved/overrode a grade
#   - WHEN they did it
#   - WHAT the original ML grade was (before override)
# We store all of this — never delete the original ML score.
# ============================================================

import uuid
from datetime import datetime, timezone
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database.postgres import get_db
from app.auth.dependencies import get_current_user, require_roles
from app.schemas.reviews import ReviewOut, OverridePayload, ReviewListResponse

# NOTE: prefix is set in main.py via include_router() — do NOT set it here too.
router = APIRouter(tags=["reviews"])


# ---------------------------------------------------------------
# GET /reviews  → List all pending reviews (teacher/admin)
# ---------------------------------------------------------------
# CONCEPT: Filtering flagged grades
# ----------------------------------
# "Reviews" are not a separate table — they're grades with
# `flagged_for_review = True` that haven't been actioned yet.
# Keeping them in the Grade table avoids duplication and keeps
# the data model simple.
# ---------------------------------------------------------------
@router.get("/", response_model=ReviewListResponse)
async def list_pending_reviews(
    exam_id: Optional[str] = Query(None, description="Filter by exam"),
    review_status: Optional[str] = Query(
        "pending",
        description="Filter by status: pending | approved | overridden"
    ),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_roles("teacher", "admin")),
):
    """
    List grades that have been flagged for human review.
    Teachers see reviews for their own exams.
    Admins see all reviews.
    """
    from app.models.grade import Grade
    from sqlalchemy import func

    query = select(Grade).where(Grade.flagged_for_review.is_(True))

    # ---- Teachers only see their own exams' reviews ----
    # CONCEPT: Joining for authorization
    # In production, join Grade → Exam and filter Exam.created_by == teacher.id
    # Simplified here for clarity:
    if current_user.role == "teacher":
        from app.models.exam import Exam
        # Subquery: exam IDs this teacher owns
        exam_subq = select(Exam.id).where(Exam.created_by == current_user.id).subquery()
        query = query.where(Grade.exam_id.in_(exam_subq))

    if exam_id:
        query = query.where(Grade.exam_id == uuid.UUID(exam_id))

    if review_status:
        query = query.where(Grade.review_status == review_status)

    count_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = count_result.scalar()

    result = await db.execute(
        query.order_by(Grade.created_at.desc()).offset(skip).limit(limit)
    )
    grades = result.scalars().all()

    return ReviewListResponse(items=grades, total=total, skip=skip, limit=limit)


# ---------------------------------------------------------------
# PATCH /reviews/{grade_id}/approve  → Accept ML grade as correct
# ---------------------------------------------------------------
# CONCEPT: Sub-resource actions with path verbs
# ----------------------------------------------
# REST purists say URLs should be nouns, not verbs.
# But for state transitions (approve, reject, publish),
# sub-resource actions like /approve are widely accepted
# and more readable than PATCH /reviews/{id} {status: "approved"}.
#
# Both approaches work — be consistent within your API.
# ---------------------------------------------------------------
@router.patch("/{grade_id}/approve", response_model=ReviewOut)
async def approve_grade(
    grade_id: str,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_roles("teacher", "admin")),
):
    """
    Approve an ML-generated grade as correct.
    The score is unchanged; only the review status is updated.
    """
    from app.models.grade import Grade

    grade = await _get_flagged_grade(db, grade_id)
    _assert_not_already_reviewed(grade)

    # ---- Record the approval ----
    grade.review_status = "approved"
    grade.reviewed_by = current_user.id
    grade.reviewed_at = datetime.now(timezone.utc)
    # NOTE: We keep grade.score unchanged — ML got it right.

    db.add(grade)
    await db.commit()
    await db.refresh(grade)

    return grade


# ---------------------------------------------------------------
# PATCH /reviews/{grade_id}/override  → Replace ML grade manually
# ---------------------------------------------------------------
# CONCEPT: Preserving history on override
# ----------------------------------------
# When a teacher overrides a grade, we:
#   1. Save the original ML score in `original_ml_score`
#   2. Save the teacher's manual score in `score`
#   3. Record WHY they overrode (override_reason)
#
# This creates an audit trail. Later you can:
#   - Measure ML accuracy (compare original_ml_score vs manual)
#   - Detect bias patterns
#   - Retrain the model on corrections
# ---------------------------------------------------------------
@router.patch("/{grade_id}/override", response_model=ReviewOut)
async def override_grade(
    grade_id: str,
    payload: OverridePayload,          # { new_score, override_reason }
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_roles("teacher", "admin")),
):
    """
    Override an ML-generated grade with a manual score.
    The original ML score is preserved for audit purposes.
    """
    from app.models.grade import Grade

    grade = await _get_flagged_grade(db, grade_id)
    _assert_not_already_reviewed(grade)

    # ---- Validate new score ----
    if payload.new_score < 0 or payload.new_score > grade.max_score:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"New score must be between 0 and {grade.max_score}",
        )

    # ---- Store original ML score before overwriting ----
    grade.original_ml_score = grade.score        # Preserve for audit
    grade.score = payload.new_score              # Apply manual correction
    grade.review_status = "overridden"
    grade.reviewed_by = current_user.id
    grade.reviewed_at = datetime.now(timezone.utc)
    grade.override_reason = payload.override_reason

    db.add(grade)
    await db.commit()
    await db.refresh(grade)

    return grade


# ---------------------------------------------------------------
# GET /reviews/{grade_id}  → Fetch a specific review
# ---------------------------------------------------------------
@router.get("/{grade_id}", response_model=ReviewOut)
async def get_review(
    grade_id: str,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_roles("teacher", "admin")),
):
    """Fetch a specific flagged grade / review."""
    return await _get_flagged_grade(db, grade_id)


# ---------------------------------------------------------------
# Private helpers (not routes — just shared logic)
# ---------------------------------------------------------------
# CONCEPT: DRY (Don't Repeat Yourself)
# --------------------------------------
# Both /approve and /override need to:
#   1. Find the grade by ID
#   2. Confirm it's flagged for review
#   3. Confirm it hasn't already been actioned
# Extract that into helpers to avoid copying the same 10 lines twice.
# ---------------------------------------------------------------

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
