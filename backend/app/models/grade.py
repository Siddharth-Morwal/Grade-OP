# ============================================================
# models/grade.py
# ============================================================
#
# CONCEPT: JSONB — storing structured data inside a Postgres column
# ------------------------------------------------------------------
# `per_question_breakdown` needs to store variable-length data:
# [
#   { "question_id": "abc", "score": 4, "max_score": 5, "feedback": "..." },
#   { "question_id": "def", "score": 2, "max_score": 5, "feedback": "..." },
# ]
#
# Options:
#   A) Separate table `question_scores`  → normalized, but complex JOINs
#   B) JSON column (text)                → stored as string, can't query inside
#   C) JSONB column (binary JSON)        → stored efficiently, QUERYABLE!
#
# JSONB in Postgres lets you do:
#   SELECT * FROM grades WHERE per_question_breakdown @> '[{"score": 0}]'
#   (find all grades with at least one zero score)
#
# For ML pipeline output that varies per exam type, JSONB is the right tool.
#
# CONCEPT: Two FK columns pointing at the SAME table (users)
# ------------------------------------------------------------
# Grade has BOTH:
#   student_id  → FK to users (the student being graded)
#   reviewed_by → FK to users (the teacher who reviewed)
#
# SQLAlchemy needs help when there are multiple FKs to the same table.
# You must specify foreign_keys=[...] on each relationship explicitly,
# otherwise SQLAlchemy raises an "AmbiguousForeignKeys" error.
#
# CONCEPT: Nullable FK columns
# -----------------------------
# reviewed_by is nullable because a grade starts as "pending"
# — no one has reviewed it yet. Once a teacher approves/overrides,
# we populate it. Nullable FK = "optional relationship".
# ============================================================

import uuid
import enum
from datetime import datetime
from typing import Any

from sqlalchemy import (
    String, Integer, Float, Boolean, Text,
    DateTime, Enum as SAEnum, ForeignKey, UniqueConstraint, CheckConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDMixin, TimestampMixin


class ReviewStatus(str, enum.Enum):
    """State of the human review workflow for a flagged grade."""
    pending    = "pending"     # Flagged, awaiting teacher action
    approved   = "approved"    # Teacher confirmed ML grade is correct
    overridden = "overridden"  # Teacher manually corrected the score


class Grade(UUIDMixin, TimestampMixin, Base):
    """
    Stores the ML pipeline's grading output for one student's exam attempt.
    Also carries the review audit trail when a teacher inspects a flagged grade.

    Key design decisions:
    - One row per (student, exam) pair — enforced by UniqueConstraint
    - The ML grade is preserved even after a teacher override (original_ml_score)
    - Review history (who, when, why) is embedded here, not a separate table
    """

    __tablename__ = "grades"

    # ---------------------------------------------------------------
    # Table-level constraints (multi-column)
    # ---------------------------------------------------------------
    # CONCEPT: __table_args__ for table-level constraints
    # -----------------------------------------------------
    # Some constraints span multiple columns and can't be expressed
    # on a single mapped_column(). Put them in __table_args__.
    #
    # UniqueConstraint("student_id", "exam_id") →
    #   UNIQUE (student_id, exam_id)
    #   One student gets exactly one grade per exam.
    #   The upsert logic in grades.py depends on this guarantee.
    #
    # CheckConstraint →
    #   score <= max_score at the DB level — belt AND suspenders.
    #   Even if application code has a bug, Postgres rejects bad data.
    # ---------------------------------------------------------------
    __table_args__ = (
        UniqueConstraint(
            "student_id", "exam_id",
            name="uq_grade_student_exam",       # Named constraints appear in error messages
        ),
        CheckConstraint(
            "score >= 0 AND score <= max_score",
            name="ck_grade_score_range",
        ),
        CheckConstraint(
            "confidence_score >= 0.0 AND confidence_score <= 1.0",
            name="ck_grade_confidence_range",
        ),
    )

    # ---- Who took which exam ----
    student_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
        comment="The student who took the exam",
    )

    exam_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("exams.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
        comment="The exam that was graded",
    )

    # ---- ML grading output ----
    score: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Final score (may be overridden by a teacher)",
    )

    max_score: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Maximum possible score (mirrors Exam.total_marks at grading time)",
    )

    # CONCEPT: JSONB for ML breakdown data
    # ----------------------------------------
    # The per-question scores are structured but variable-length.
    # JSONB lets us store them without designing a third table.
    # Shape: [{"question_id": str, "score": int, "max_score": int, "feedback": str}]
    per_question_breakdown: Mapped[Any] = mapped_column(
        JSONB,
        nullable=True,
        comment="Per-question score details from the ML pipeline",
    )

    # CONCEPT: Float for probability/confidence (0.0–1.0)
    # -----------------------------------------------------
    # Float is fine here because we're storing a statistical estimate,
    # not a financial value. Tiny rounding errors don't matter.
    # The CheckConstraint above ensures it stays in [0.0, 1.0].
    confidence_score: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        comment="ML model's confidence: 0.0 (unsure) to 1.0 (certain)",
    )

    ml_model_version: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="Version string of the ML model that produced this grade (e.g. 'v2.1.0')",
    )

    overall_justification: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Overall justification provided by the ML model",
    )

    # ---- Human review workflow ----
    # CONCEPT: Denormalized review state
    # ------------------------------------
    # We're embedding review state in the Grade row rather than
    # a separate GradeReview table. This is a deliberate trade-off:
    #   ✓ Simpler queries (one table)
    #   ✓ Atomic updates (no JOIN needed)
    #   ✗ Can't store review history (only the LAST review action)
    #
    # If you need full audit history (multiple review rounds),
    # extract to a separate `grade_reviews` table later.
    flagged_for_review: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        index=True,                          # Reviews page queries this constantly
        comment="True when ML confidence is low and human review is needed",
    )

    review_status: Mapped[ReviewStatus] = mapped_column(
        SAEnum(ReviewStatus, name="reviewstatus", native_enum=True),
        nullable=False,
        default=ReviewStatus.pending,
        index=True,
        comment="Tracks where this grade is in the human review pipeline",
    )

    # CONCEPT: Nullable FK — optional relationship
    # ----------------------------------------------
    # reviewed_by is NULL until a teacher actions this grade.
    # nullable=True + ForeignKey = "this relationship may not exist yet"
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),  # If reviewer is deleted, set NULL
        nullable=True,
        comment="User ID of the teacher who reviewed this grade",
    )

    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Timestamp of when the review action was taken",
    )

    # CONCEPT: Preserving original ML score for audit + retraining
    # --------------------------------------------------------------
    # When a teacher overrides a grade, we:
    #   1. Copy current score → original_ml_score
    #   2. Set score = teacher's new value
    # This lets us later measure ML accuracy and use disagreements
    # as training data for the next model version.
    original_ml_score: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="The ML score before a teacher override. NULL if not overridden.",
    )

    override_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Teacher's written justification for changing the ML grade",
    )

    # ---------------------------------------------------------------
    # Relationships
    # ---------------------------------------------------------------
    # CONCEPT: Multiple FKs to the same table → must specify foreign_keys
    # ---------------------------------------------------------------------
    # SQLAlchemy sees two paths to `users` (student_id and reviewed_by)
    # and doesn't know which one `student` or `reviewer` should use.
    # foreign_keys=[...] explicitly tells it: "use THIS column for THIS relationship"
    student: Mapped["User"] = relationship(
        "User",
        foreign_keys=[student_id],
        lazy="select",
    )

    reviewer: Mapped["User | None"] = relationship(
        "User",
        foreign_keys=[reviewed_by],
        lazy="select",
    )

    exam: Mapped["Exam"] = relationship(
        "Exam",
        back_populates="grades",
        lazy="select",
    )

    # ---- Computed property ----
    # CONCEPT: @property — derived values without storing them
    # ---------------------------------------------------------
    # percentage doesn't need its own column. Derive it on-the-fly
    # in Python. Pydantic schemas can include it via @computed_field.
    @property
    def percentage(self) -> float:
        """Score as a percentage of max_score. Avoids division-by-zero."""
        if self.max_score == 0:
            return 0.0
        return round((self.score / self.max_score) * 100, 2)

    @property
    def student_name(self) -> str | None:
        """Helper for API responses to include the student's name."""
        return self.student.full_name if self.student else None

    @property
    def student_roll(self) -> str | None:
        """Helper for API responses to include the student's roll number."""
        return self.student.roll_number if self.student else None

    @property
    def is_reviewed(self) -> bool:
        """True if a teacher has actioned this grade."""
        return self.review_status in (ReviewStatus.approved, ReviewStatus.overridden)

    def __repr__(self) -> str:
        return (
            f"<Grade id={self.id} student={self.student_id} "
            f"exam={self.exam_id} score={self.score}/{self.max_score}>"
        )
