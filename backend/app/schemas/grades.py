# ============================================================
# schemas/grades.py
# ============================================================
#
# CONCEPT: Nested schemas — validating structured JSONB fields
# -----------------------------------------------------------
# Grade.per_question_breakdown is stored as raw JSONB in Postgres.
# At the DB level it's just bytes — no structure is enforced there.
# Pydantic fixes this: we define QuestionScore as a proper model,
# declare the field as List[QuestionScore], and Pydantic validates
# every dict in the list on both the way IN (request) and OUT (response).
#
# The flow IN:
#   ML pipeline JSON → GradeCreate.per_question_breakdown: List[QuestionScore]
#   → Pydantic validates each item → router stores to JSONB
#
# The flow OUT:
#   JSONB from Postgres → Python list[dict] → GradeOut.per_question_breakdown
#   → Pydantic re-validates → serialised JSON response
#
# CONCEPT: @computed_field (Pydantic v2)
# ----------------------------------------
# Grade ORM has @property percentage and @property is_reviewed.
# To surface them in the API response with NO extra DB column:
#   → declare @computed_field in the schema
#   → Pydantic calls them during serialisation
#   → they appear in JSON like regular fields
# ============================================================

import uuid
from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, Field, field_validator, computed_field, model_validator

from app.models.grade import ReviewStatus
from app.schemas.base import AppResponseSchema, PaginatedResponse


# ---------------------------------------------------------------
# Nested schema: a single row inside per_question_breakdown
# ---------------------------------------------------------------
# CONCEPT: Strict nested schemas > dict[str, Any]
# ------------------------------------------------
# dict[str, Any] lets anything through — typos, wrong types, missing keys.
# A real schema enforces the exact shape the ML pipeline must produce.
# If question_id is missing → 422 before the router body runs.
# ---------------------------------------------------------------
class QuestionScore(BaseModel):
    """
    One item inside a grade's per_question_breakdown list.
    Validates the structure the ML pipeline writes for each question.
    """
    question_id: str = Field(
        ...,
        description="UUID of the question as stored in MongoDB",
    )
    score: int = Field(..., ge=0, description="Points awarded for this question")
    max_score: int = Field(..., ge=1, description="Maximum points for this question")
    feedback: Optional[str] = Field(
        default=None,
        description="ML-generated feedback string shown to the student",
    )
    is_correct: Optional[bool] = Field(
        default=None,
        description="True/False for MCQ questions; None for open-ended",
    )

    @model_validator(mode="after")
    def score_cannot_exceed_max(self) -> "QuestionScore":
        """Per-question score must not exceed its own max."""
        if self.score > self.max_score:
            raise ValueError(
                f"score {self.score} exceeds max_score {self.max_score} "
                f"for question '{self.question_id}'"
            )
        return self


# ---------------------------------------------------------------
# GradeCreate — POST /grades  (ML pipeline → API)
# ---------------------------------------------------------------
# CONCEPT: Machine-to-machine request bodies
# ------------------------------------------
# This schema is NOT for human users. The ML service sends it.
# Differences from a normal user-facing schema:
#   - UUIDs arrive as plain strings (ML doesn't know Python uuid.UUID)
#   - We validate UUID FORMAT with @field_validator, not type coercion
#   - confidence_score is a float from the model's own softmax output
#   - flagged_for_review is decided by the ML model, not the user
# ---------------------------------------------------------------
class GradeCreate(BaseModel):
    """
    Payload the ML pipeline POSTs to /grades after grading a paper.
    Authenticated with an API key, not a JWT.
    """

    student_id: str = Field(..., description="UUID of the student whose paper was graded")
    exam_id: str    = Field(..., description="UUID of the exam that was graded")

    # CONCEPT: @field_validator for format checking external UUIDs
    # -------------------------------------------------------------
    # The ML pipeline sends UUIDs as strings.
    # We validate format here so uuid.UUID(payload.student_id)
    # in the router can never raise a ValueError crash.
    @field_validator("student_id", "exam_id", mode="after")
    @classmethod
    def must_be_valid_uuid(cls, v: str) -> str:
        try:
            uuid.UUID(v)
        except ValueError:
            raise ValueError(f"'{v}' is not a valid UUID")
        return v

    score: int = Field(..., ge=0, description="Total score awarded by the ML model")
    max_score: int = Field(..., ge=1, description="Maximum possible score for this exam")

    per_question_breakdown: Optional[List[QuestionScore]] = Field(
        default=None,
        description=(
            "Per-question detail. Optional — some exam types only produce "
            "a total score with no per-question breakdown."
        ),
    )

    # CONCEPT: ge / le on floats for range validation
    # -------------------------------------------------
    # ge=0.0 → greater than or equal to 0.0
    # le=1.0 → less than or equal to 1.0
    # Together they enforce the [0.0, 1.0] probability range.
    confidence_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Model confidence: 0.0 = completely unsure, 1.0 = certain",
    )

    flagged_for_review: bool = Field(
        default=False,
        description="True when the ML model's confidence is below its own threshold",
    )

    ml_model_version: Optional[str] = Field(
        default=None,
        max_length=50,
        description="Semver of the grading model, e.g. 'v2.1.0'",
    )

    # CONCEPT: @model_validator(mode="after") — cross-field validation
    # -----------------------------------------------------------------
    # mode="after" means: all individual fields have already been
    # validated and coerced to their types. Now we can compare them.
    # Use this for rules that span two or more fields.
    @model_validator(mode="after")
    def total_score_cannot_exceed_max(self) -> "GradeCreate":
        """Total score must not exceed max_score."""
        if self.score > self.max_score:
            raise ValueError(
                f"score ({self.score}) cannot exceed max_score ({self.max_score})"
            )
        return self


# ---------------------------------------------------------------
# GradeOut — response for GET /grades and POST /grades
# ---------------------------------------------------------------
class GradeOut(AppResponseSchema):
    """
    Full grade record returned by the API.
    Covers ML output, review state, and the complete audit trail.
    """

    # Identity
    id: uuid.UUID
    student_id: uuid.UUID = Field(description="Student who sat the exam")
    exam_id: uuid.UUID    = Field(description="Exam that was graded")

    # ML output
    score: int            = Field(description="Current score (may have been overridden by a teacher)")
    max_score: int        = Field(description="Maximum achievable score")
    per_question_breakdown: Optional[List[QuestionScore]] = Field(
        default=None,
        description="Per-question score breakdown. None if not produced by the ML model.",
    )
    confidence_score: float       = Field(description="ML confidence 0.0–1.0")
    ml_model_version: Optional[str] = Field(default=None)

    # Review workflow
    flagged_for_review: bool      = Field(description="True = awaiting human review")
    review_status: ReviewStatus   = Field(description="pending | approved | overridden")

    # Audit trail — all nullable until a teacher acts
    reviewed_by: Optional[uuid.UUID] = Field(
        default=None,
        description="UUID of the teacher who reviewed. None = not yet reviewed.",
    )
    reviewed_at: Optional[datetime]  = Field(
        default=None,
        description="Timestamp of the review action",
    )
    original_ml_score: Optional[int] = Field(
        default=None,
        description="ML score before a teacher override. None = not overridden.",
    )
    override_reason: Optional[str]   = Field(
        default=None,
        description="Teacher's written justification for the grade change",
    )

    # Timestamps
    created_at: datetime
    updated_at: datetime

    # CONCEPT: @computed_field — exposes ORM @property in JSON response
    # ------------------------------------------------------------------
    # These are NOT stored in the DB. They're computed at serialisation time.
    # Pydantic v2 calls the property on the ORM object (via from_attributes=True)
    # and includes the result in the JSON output.
    # The @property decorator is required alongside @computed_field.
    @computed_field
    @property
    def percentage(self) -> float:
        """Score as a percentage of max_score. Safe against division by zero."""
        if self.max_score == 0:
            return 0.0
        return round((self.score / self.max_score) * 100, 2)

    @computed_field
    @property
    def is_reviewed(self) -> bool:
        """True once a teacher has approved or overridden this grade."""
        return self.review_status in (ReviewStatus.approved, ReviewStatus.overridden)


# ---------------------------------------------------------------
# GradeListResponse — paginated wrapper for GET /grades
# ---------------------------------------------------------------
class GradeListResponse(PaginatedResponse[GradeOut]):
    """
    Paginated list of grades.
    Inherits: items (List[GradeOut]), total, skip, limit from PaginatedResponse.
    """
    pass
