# ============================================================
# models/__init__.py
# ============================================================
#
# CONCEPT: Why does this file matter so much?
# --------------------------------------------
# SQLAlchemy's Base.metadata only knows about a table if the
# model CLASS has been IMPORTED (executed) at least once.
#
# Python doesn't load a module until something imports it.
# If you never import Grade, SQLAlchemy doesn't know the
# `grades` table exists → create_all() skips it → your
# app crashes with "table grades does not exist".
#
# This file is the SINGLE place that imports every model.
# Then in your app startup (main.py or database/postgres.py),
# you import models → all tables are registered → create_all() works.
#
# CONCEPT: Import ORDER matters for circular references
# -------------------------------------------------------
# If User imports Grade AND Grade imports User, you get a
# circular import error. The fix:
#   1. Define models with string forward references: relationship("Grade")
#      (SQLAlchemy resolves the string lazily — not at import time)
#   2. Import all models HERE in dependency order:
#      Base first → no deps
#      User  next → no model deps (only Base)
#      Exam  next → depends on User (FK)
#      Grade last → depends on User + Exam (FK)
# ============================================================

# Re-export Base so other modules can do:
#   from app.models import Base
# instead of digging into app.models.base
from app.models.base import Base, UUIDMixin, TimestampMixin  # noqa: F401

# Import all ORM models so Base.metadata knows about every table.
# The order here follows foreign key dependencies:
#   User has no FK deps          → import first
#   Exam depends on User         → import second
#   Grade depends on User + Exam → import last
from app.models.user  import User, UserRole          # noqa: F401
from app.models.exam  import Exam, ExamStatus        # noqa: F401
from app.models.grade import Grade, ReviewStatus     # noqa: F401

# ---------------------------------------------------------------
# What `noqa: F401` means
# ---------------------------------------------------------------
# F401 is the flake8 lint rule: "imported but unused".
# We import these for their SIDE EFFECT (registering with Base.metadata),
# not because we use the names in this file.
# `noqa: F401` silences the linter warning. It's correct code.
# ---------------------------------------------------------------

__all__ = [
    # Base infrastructure
    "Base",
    "UUIDMixin",
    "TimestampMixin",
    # ORM models
    "User",
    "UserRole",
    "Exam",
    "ExamStatus",
    "Grade",
    "ReviewStatus",
]
