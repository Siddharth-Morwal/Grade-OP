# ============================================================
# schemas/reviews.py
# ============================================================
#
# CONCEPT: Reviews are a VIEW of grades, not a separate resource
# ---------------------------------------------------------------
# There is no `reviews` DB table. A "review" is just a Grade row
# where flagged_for_review = True. The reviews router reads from
# and writes to the grades table.
#
# Because of this, ReviewOut SHARES all fields with GradeOut —
# every grade field is relevant when a teacher is reviewing.
# We inherit GradeOut rather than duplicate its field declarations.
#
# What's NEW in the reviews layer:
#   OverridePayload → the PATCH body a teacher sends to override a grade
#   ReviewListResponse → same pagination wrapper but clearly named for reviews
#
# CONCEPT: Inheritance in Pydantic schemas
# -----------------------------------------
# ReviewOut(GradeOut) → ReviewOut has every field GradeOut has,
# plus anything ReviewOut adds on top.
# This works for response schemas because the underlying data
# (a Grade ORM row) satisfies both schemas.
#
# For request schemas, inheritance is used when one schema is a
# strict superset of another:
#   AdminOverridePayload(OverridePayload) might add `notify_student: bool`
#   that only admins can set — teachers use the base OverridePayload.
# ============================================================

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator

from app.schemas.grades import GradeOut
from app.schemas.base import PaginatedResponse


# ---------------------------------------------------------------
# OverridePayload — PATCH /reviews/{id}/override  request body
# ---------------------------------------------------------------
# CONCEPT: Minimal request bodies for action endpoints
# -----------------------------------------------------
# This endpoint does ONE thing: change a grade's score and record why.
# The payload only needs:
#   new_score     → the corrected score the teacher is setting
#   override_reason → mandatory justification (audit trail!)
#
# We do NOT re-send student_id, exam_id, etc. — those come from
# the URL path parameter (grade_id). Sending them in the body too
# would create an inconsistency risk (body says one thing, path another).
# Path parameters identify the resource; body carries the mutation.
# ---------------------------------------------------------------
class OverridePayload(BaseModel):
    """
    Payload for PATCH /reviews/{grade_id}/override.
    A teacher sends this to replace an ML grade with their own score.
    """

    new_score: int = Field(
        ...,
        ge=0,
        description=(
            "The corrected score this teacher is awarding. "
            "Must be >= 0 and <= the grade's max_score "
            "(the router enforces the upper bound against the DB value)."
        ),
    )

    # CONCEPT: Mandatory override_reason for audit trails
    # ----------------------------------------------------
    # We REQUIRE a reason — not Optional[str].
    # A forced justification text:
    #   - Creates a paper trail for disputes
    #   - Gives the ML team signal for why the model was wrong
    #   - Discourages lazy or unjustified overrides
    #   - min_length=10 prevents "." or "wrong" — forces a real explanation
    override_reason: str = Field(
        ...,
        min_length=10,
        max_length=2000,
        description=(
            "Mandatory explanation for why the ML grade is being overridden. "
            "Minimum 10 characters — 'wrong' is not a sufficient reason."
        ),
        examples=["Student correctly identified the formula but used different notation than expected by the model."],
    )

    @field_validator("override_reason", mode="before")
    @classmethod
    def strip_reason(cls, v: str) -> str:
        """Strip accidental whitespace from the reason text."""
        return v.strip()


# ---------------------------------------------------------------
# ReviewOut — response for all /reviews endpoints
# ---------------------------------------------------------------
# CONCEPT: Inheriting GradeOut — DRY schema reuse
# -------------------------------------------------
# A review IS a grade with extra context. Every field in GradeOut
# is relevant when a teacher is looking at a flagged grade:
#   - score, max_score, percentage → what did the ML give?
#   - confidence_score             → why was this flagged?
#   - per_question_breakdown       → where did the model struggle?
#   - review_status, reviewed_by   → what's the current review state?
#
# By inheriting GradeOut we get all of that for free.
# We add two extra computed display fields specific to the review UI:
#   confidence_label  → "Low / Medium / High" string from the float
#   days_pending      → how long this grade has been waiting for review
#
# CONCEPT: @computed_field on inherited schemas
# ----------------------------------------------
# @computed_field works in child schemas too. The parent's @computed_fields
# (percentage, is_reviewed) are inherited automatically.
# We add MORE computed fields on top in the child.
# ---------------------------------------------------------------
from pydantic import computed_field


class ReviewOut(GradeOut):
    """
    A flagged grade presented in the review workflow context.
    Inherits all GradeOut fields and adds review-specific computed fields.
    """

    # CONCEPT: @computed_field for display-layer derived values
    # ----------------------------------------------------------
    # confidence_label converts the raw float (0.73) into something
    # a teacher can understand at a glance ("Medium confidence").
    # This is display logic — keeping it in the schema (not the frontend)
    # means every client (web, mobile, PDF report) gets the same label.
    @computed_field
    @property
    def confidence_label(self) -> str:
        """
        Human-readable confidence band for the review UI.
        Thresholds are based on the ML team's calibration.
        """
        score = self.confidence_score
        if score >= 0.85:
            return "High"
        elif score >= 0.60:
            return "Medium"
        else:
            return "Low"

    @computed_field
    @property
    def days_pending(self) -> Optional[int]:
        """
        How many whole days this grade has been waiting for review.
        None if already reviewed (no longer pending).
        Useful for the review dashboard to surface stale reviews first.
        """
        if self.review_status.value != "pending":
            return None
        delta = datetime.utcnow() - self.created_at.replace(tzinfo=None)
        return delta.days


# ---------------------------------------------------------------
# ReviewListResponse — paginated list for GET /reviews
# ---------------------------------------------------------------
# CONCEPT: Separate list response type per resource
# --------------------------------------------------
# We could reuse GradeListResponse — the data shape is identical.
# But using a dedicated name has benefits:
#   - OpenAPI generates a distinct schema named "ReviewListResponse"
#     (not "GradeListResponse") in the /docs page — clearer for API consumers
#   - If we add review-specific list metadata later (e.g. pending_count),
#     we add it here without touching grades schemas
# ---------------------------------------------------------------
class ReviewListResponse(PaginatedResponse[ReviewOut]):
    """
    Paginated list of flagged grades in the review queue.
    Inherits: items (List[ReviewOut]), total, skip, limit.
    """
    pass
