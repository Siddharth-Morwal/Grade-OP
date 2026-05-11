# ============================================================
# models/user.py
# ============================================================
#
# CONCEPT: __tablename__
# -----------------------
# This string is the actual PostgreSQL table name.
# Convention: lowercase, plural, snake_case → "users"
# SQLAlchemy uses this to generate all SQL against that table.
#
# CONCEPT: Enum types in PostgreSQL
# ----------------------------------
# For columns with a fixed set of valid values (like user roles),
# you have two options:
#
# Option A: VARCHAR with a CHECK constraint
#   role VARCHAR CHECK (role IN ('student', 'teacher', 'admin'))
#   → Simple, but the valid values live in the DB constraint only
#
# Option B: PostgreSQL native ENUM type
#   CREATE TYPE user_role AS ENUM ('student', 'teacher', 'admin');
#   → The valid values are a first-class DB citizen; enforced by PG
#
# We use SQLAlchemy's Enum() which creates the PG ENUM type.
# The advantage: if you try INSERT ... role = 'hacker', Postgres
# rejects it at the DB level, not just in application code.
#
# CONCEPT: Index strategy
# -------------------------
# Index = a separate data structure (B-tree) that lets Postgres find
# rows without scanning the entire table (like a book's index).
#
# Add an index when you FILTER or JOIN by that column frequently.
#   WHERE email = ?          → Index on email ✓
#   WHERE role = 'student'   → Index on role ✓ (if you query this a lot)
#   WHERE hashed_password = ?→ NEVER (you never search by hash)
#
# unique=True implicitly creates a unique index (no duplicates + fast lookup).
# ============================================================

import uuid
import enum
from sqlalchemy import String, Boolean, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDMixin, TimestampMixin


# ---------------------------------------------------------------
# Python Enum → mirrors the PostgreSQL ENUM type
# ---------------------------------------------------------------
# CONCEPT: Why define the Enum in Python AND PostgreSQL?
# -------------------------------------------------------
# The Python enum gives you:
#   - Autocomplete in your IDE
#   - Type safety (user.role == UserRole.student, not "student")
#   - Single source of truth for valid values
#
# SQLAlchemy reads this Python enum and creates the matching
# PostgreSQL ENUM type automatically when you run create_all().
# ---------------------------------------------------------------
class UserRole(str, enum.Enum):
    """Valid roles a user can have in the system."""
    student = "student"
    teacher = "teacher"
    admin   = "admin"

    # Inheriting from `str` means UserRole.student == "student" is True.
    # This matters when comparing against JWT payload strings or query params.


# ---------------------------------------------------------------
# User ORM Model
# ---------------------------------------------------------------
class User(UUIDMixin, TimestampMixin, Base):
    """
    Represents a registered user.

    Inherits:
      UUIDMixin      → id (UUID primary key)
      TimestampMixin → created_at, updated_at
      Base           → SQLAlchemy declarative registry
    """

    __tablename__ = "users"

    # ---- Identity ----
    # CONCEPT: unique=True + index=True
    # ----------------------------------
    # unique=True   → DB-level constraint: no two rows can share an email
    # index=True    → creates a B-tree index for fast WHERE email = ? lookups
    # nullable=False→ NOT NULL constraint: email is required
    #
    # Note: unique=True already creates an index, so you don't need
    # index=True when unique=True. SQLAlchemy handles this correctly.
    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
        comment="User's login email — must be unique across the system",
    )

    full_name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        comment="Display name shown in the UI",
    )

    # ---- Authentication ----
    # CONCEPT: Never expose this column
    # ----------------------------------
    # hashed_password is the bcrypt hash.
    # It NEVER appears in API responses (Pydantic schemas exclude it).
    # The column comment documents this intent for future developers.
    hashed_password: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="bcrypt hash — NEVER expose in API responses",
    )

    # ---- Role ----
    # CONCEPT: SAEnum with native_enum=True
    # ----------------------------------------
    # native_enum=True  → create a real PostgreSQL ENUM type
    # native_enum=False → store as VARCHAR with app-level validation only
    #
    # name="userrole" → the name of the PG ENUM type in the DB
    # values_callable → tells SAEnum to read values from the Python enum
    role: Mapped[UserRole] = mapped_column(
        SAEnum(UserRole, name="userrole", native_enum=True),
        nullable=False,
        default=UserRole.student,
        comment="Access level: student < teacher < admin",
    )

    # ---- Status ----
    # CONCEPT: Soft delete flag
    # --------------------------
    # is_active=False means the user is "deleted" but the row persists.
    # Benefits: audit history, foreign key integrity, data recovery.
    # All queries that list users should filter WHERE is_active = TRUE.
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",  # DB default if Python default somehow skipped
        comment="False = soft-deleted; exclude from normal queries",
    )

    # ---- Optional profile fields ----
    avatar_url: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="URL to profile picture",
    )

    # ---------------------------------------------------------------
    # Relationships (defined here, used via SQLAlchemy lazy/eager loading)
    # ---------------------------------------------------------------
    # CONCEPT: relationship() and back_populates
    # --------------------------------------------
    # relationship() lets you navigate between models in Python:
    #   user.exams         → list of Exam objects this user created
    #   exam.creator       → the User who created it
    #
    # back_populates links the two sides:
    #   User.exams ↔ Exam.creator
    #
    # lazy="select" (default) → SQLAlchemy runs a separate SELECT
    # when you access user.exams. Fine for single-record loads.
    # For list endpoints, use .options(selectinload(User.exams)) to
    # load them in ONE query instead of N+1 queries.
    # ---------------------------------------------------------------
    from sqlalchemy.orm import relationship  # noqa: F401 — needed for type hints

    # exams: Mapped[list["Exam"]] = relationship("Exam", back_populates="creator")
    # grades: Mapped[list["Grade"]] = relationship("Grade", back_populates="student",
    #                                               foreign_keys="Grade.student_id")
    #
    # ↑ Uncommented when Exam and Grade models exist (avoids circular import at startup).
    # In production, move all relationships to a separate models/__init__.py
    # that imports all models after they're all defined.

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email} role={self.role}>"
