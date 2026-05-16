# ============================================================
# models/exam.py
# ============================================================
#
# CONCEPT: Foreign Keys in SQLAlchemy
# -------------------------------------
# A foreign key is a column whose value must exist in another table.
#   exams.created_by → must match a row in users.id
#
# This is REFERENTIAL INTEGRITY — the database enforces it:
#   INSERT INTO exams (created_by='fake-uuid') → ERROR (no such user)
#   DELETE a user who has exams              → ERROR (or CASCADE)
#
# In SQLAlchemy:
#   ForeignKey("users.id")  ← string: "tablename.columnname"
#
# CONCEPT: ondelete behavior
# ---------------------------
# What happens if the referenced user is deleted?
#   RESTRICT   → block the delete (safest default)
#   CASCADE    → delete all their exams too (dangerous!)
#   SET NULL   → set created_by = NULL (requires nullable=True)
#
# For exams: RESTRICT is safest. Don't cascade-delete a teacher's
# entire exam history just because their account was deactivated.
# Remember: we soft-delete users anyway (is_active=False),
# so the FK is never actually violated.
#
# CONCEPT: ExamStatus as a Python Enum
# --------------------------------------
# The exam lifecycle is a pipeline:
#   pending   → uploaded, waiting for ML processing
#   processing→ ML pipeline is running
#   published → ready for students
#   archived  → hidden from students, kept for records
# ============================================================

import uuid
import enum
from sqlalchemy import String, Integer, Text, Enum as SAEnum, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from app.models.base import Base, UUIDMixin, TimestampMixin


class ExamStatus(str, enum.Enum):
    """Lifecycle stages for an uploaded exam paper."""
    pending    = "pending"     # Just uploaded, ML hasn't processed it yet
    processing = "processing"  # ML pipeline is actively grading
    published  = "published"   # Visible to students
    archived   = "archived"    # Hidden but preserved


class Exam(UUIDMixin, TimestampMixin, Base):
    """
    Represents an uploaded exam paper.
    Metadata lives here in Postgres; questions live in MongoDB.
    """

    __tablename__ = "exams"

    # ---- Core metadata ----
    title: Mapped[str] = mapped_column(
        String(300),
        nullable=False,
        comment="Human-readable exam title, e.g. 'Midterm Exam 2025'",
    )

    subject: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
        index=True,                          # We filter by subject frequently
        comment="Subject area, e.g. 'Mathematics', 'Physics'",
    )

    description: Mapped[str | None] = mapped_column(
        Text,                                # TEXT = unlimited length (vs VARCHAR)
        nullable=True,
        comment="Optional longer description or instructions for students",
    )

    # CONCEPT: Integer vs Float for marks
    # ------------------------------------
    # Marks are always whole numbers in this system (no half marks).
    # Integer is smaller, faster, and avoids floating-point precision bugs.
    # If you needed 0.5 marks, use Numeric(precision=5, scale=1) — NOT Float.
    # Float has rounding errors: 0.1 + 0.2 ≠ 0.3 in IEEE 754.
    total_marks: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Maximum achievable score on this exam",
    )

    # ---- File storage ----
    # CONCEPT: Store path, not file
    # ------------------------------
    # The file bytes live on disk (or S3). We only store the location.
    # This keeps the DB row small and lets you swap storage backends
    # without touching the DB schema.
    file_path: Mapped[str] = mapped_column(
        String(1000),
        nullable=False,
        comment="Absolute path or S3 URI to the uploaded exam file",
    )

    file_name: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        comment="Original filename as uploaded by the teacher",
    )

    answer_key_path: Mapped[str | None] = mapped_column(
        String(1000),
        nullable=True,
        comment="Path to the uploaded answer key/rubric",
    )

    student_script_path: Mapped[str | None] = mapped_column(
        String(1000),
        nullable=True,
        comment="Path to the bulk student answers PDF",
    )

    # ---- Lifecycle status ----
    status: Mapped[ExamStatus] = mapped_column(
        SAEnum(ExamStatus, name="examstatus", native_enum=True),
        nullable=False,
        default=ExamStatus.pending,
        index=True,                          # We filter by status frequently
        comment="Processing and visibility state of the exam",
    )

    # ---- Ownership ----
    # CONCEPT: ForeignKey("users.id")
    # ---------------------------------
    # "users.id" is the string reference format: "table.column"
    # ondelete="RESTRICT" → Postgres blocks deleting a user who owns exams
    # This keeps our data consistent even if application code has bugs.
    created_by: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,                          # Teachers query "my exams" frequently
        comment="User ID of the teacher who uploaded this exam",
    )

    # ---- Relationship: back to the User who created this exam ----
    # CONCEPT: Why define the relationship here AND on User?
    # --------------------------------------------------------
    # Defining it on BOTH sides (with back_populates) lets you navigate
    # from either direction:
    #   exam.creator       → User object
    #   user.exams         → list of Exam objects
    #
    # If you define it on only one side, the other direction won't work.
    creator: Mapped["User"] = relationship(
        "User",
        foreign_keys=[created_by],
        lazy="select",                       # Load User only when accessed
    )

    # ---- Relationship: grades for this exam ----
    # CONCEPT: lazy="dynamic" (deprecated) vs lazy="select"
    # -------------------------------------------------------
    # Use selectinload() in your queries for collections instead of
    # relying on lazy loading. Lazy loading in async is tricky.
    # For now we just declare the relationship; actual loading
    # uses explicit .options(selectinload(Exam.grades)) in routers.
    grades: Mapped[list["Grade"]] = relationship(
        "Grade",
        back_populates="exam",
        cascade="all, delete-orphan",        # Delete grades if exam is deleted
    )

    def __repr__(self) -> str:
        return f"<Exam id={self.id} title='{self.title}' status={self.status}>"
