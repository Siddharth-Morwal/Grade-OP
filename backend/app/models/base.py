# ============================================================
# models/base.py
# ============================================================
#
# CONCEPT: What is an ORM?
# --------------------------
# ORM = Object Relational Mapper.
# Instead of writing raw SQL strings, you define Python classes.
# SQLAlchemy translates them into CREATE TABLE, INSERT, SELECT etc.
#
#   class User(Base):           →    CREATE TABLE users (
#       id = Column(UUID...)              id UUID PRIMARY KEY,
#       email = Column(String...)         email VARCHAR UNIQUE NOT NULL
#                                       );
#
# You then query with Python:
#   select(User).where(User.email == "x")
#   →  SELECT * FROM users WHERE email = 'x'
#
# CONCEPT: DeclarativeBase (SQLAlchemy 2.0 style)
# -------------------------------------------------
# SQLAlchemy 2.0 introduced a cleaner API.
# DeclarativeBase replaces the old `declarative_base()` factory.
# All your ORM models inherit from this single Base.
# SQLAlchemy tracks them via Base.metadata — that's how
# `Base.metadata.create_all(engine)` knows which tables to make.
#
# CONCEPT: Mixins — the DRY solution for shared columns
# -------------------------------------------------------
# EVERY table in this project needs: id, created_at, updated_at
# Instead of copy-pasting those 3 columns into every model,
# define them ONCE in a mixin and inherit wherever needed.
#
# Mixin = a class with no table of its own, just columns to borrow.
# ============================================================

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID as PG_UUID


# ---------------------------------------------------------------
# The single Base all models inherit from
# ---------------------------------------------------------------
# CONCEPT: Why one Base matters
# ------------------------------
# All models must share the SAME Base instance.
# If you accidentally create two Base instances, SQLAlchemy
# won't know about tables from the other one → missing tables.
# We define it here and import it everywhere else.
# ---------------------------------------------------------------
class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------
# TimestampMixin — automatic created_at / updated_at
# ---------------------------------------------------------------
# CONCEPT: mapped_column() — SQLAlchemy 2.0 typed columns
# ---------------------------------------------------------
# Old style (1.x):  id = Column(UUID(as_uuid=True), ...)
# New style (2.0):  id: Mapped[uuid.UUID] = mapped_column(...)
#
# `Mapped[T]` is a Python type annotation that tells:
#   - Your IDE: "this attribute is of type T"
#   - SQLAlchemy: "this is an ORM column, not just a class variable"
# This makes models fully type-checked — huge win for large codebases.
#
# CONCEPT: server_default vs default
# ------------------------------------
# default        → Python sets the value BEFORE the INSERT reaches DB
# server_default → the DATABASE sets it (e.g. NOW(), gen_random_uuid())
#
# For timestamps: server_default="now()" → DB handles it atomically.
# For UUIDs: default=uuid.uuid4 → Python generates before INSERT
#            (lets us know the ID before the DB round-trip).
#
# CONCEPT: onupdate
# ------------------
# `onupdate=lambda: datetime.now(timezone.utc)` tells SQLAlchemy:
# whenever you UPDATE this row, refresh updated_at automatically.
# You never have to remember to set it manually.
# ---------------------------------------------------------------
class TimestampMixin:
    """Adds created_at and updated_at to any model that inherits this."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),  # Auto-refreshes on UPDATE
        nullable=False,
    )


# ---------------------------------------------------------------
# UUIDMixin — UUID primary key for every table
# ---------------------------------------------------------------
# CONCEPT: UUID vs Integer primary keys
# ----------------------------------------
# Integer PK:  1, 2, 3, 4 ...
#   ✓ Tiny (4 bytes), fast index lookups
#   ✗ Predictable (attacker can enumerate /users/1, /users/2 ...)
#   ✗ Hard to merge data from two databases (ID conflicts)
#
# UUID PK:  550e8400-e29b-41d4-a716-446655440000
#   ✓ Globally unique — safe to merge DBs, generate offline
#   ✓ Non-enumerable — attacker can't guess other users' IDs
#   ✗ Slightly larger (16 bytes), index performance is slightly worse
#
# For an exam system with students and teachers, UUIDs are correct.
# The slight performance cost is worth the security and flexibility.
#
# `as_uuid=True` → SQLAlchemy hands you a Python uuid.UUID object,
# not a raw hex string. Much more convenient.
# ---------------------------------------------------------------
class UUIDMixin:
    """Adds a UUID primary key to any model that inherits this."""

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,   # Python generates the UUID before INSERT
        nullable=False,
    )
