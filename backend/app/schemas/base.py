# ============================================================
# schemas/base.py
# ============================================================
#
# CONCEPT: What is a Pydantic schema and why is it different from an ORM model?
# ------------------------------------------------------------------------------
#
#   ORM Model  (app/models/)  ← describes the DATABASE table
#     - Has SQLAlchemy columns, ForeignKeys, relationships
#     - Maps directly to a PostgreSQL table row
#     - Contains ALL data including secrets (hashed_password)
#
#   Pydantic Schema (app/schemas/) ← describes the HTTP boundary
#     - Validates incoming JSON request bodies
#     - Shapes outgoing JSON response bodies
#     - Controls exactly which fields are VISIBLE to API clients
#     - Has NO concept of database or SQL
#
# The same database table often has MULTIPLE schemas:
#   UserCreate  → what the client sends when registering
#   UserUpdate  → what the client sends when editing (all optional)
#   UserOut     → what we return (never includes hashed_password)
#
# This file defines shared building blocks used by all other schema files.
#
# CONCEPT: Pydantic v2 (the current version as of 2024)
# -------------------------------------------------------
# FastAPI requires Pydantic. Two major versions exist:
#   v1: class Config: ...  (old style, still common in tutorials)
#   v2: model_config = ConfigDict(...)  (new style, what we use)
#
# Key v2 changes:
#   .dict()       → .model_dump()
#   .parse_obj()  → .model_validate()
#   class Config  → model_config = ConfigDict(...)
# ============================================================

from datetime import datetime
from typing import Generic, TypeVar, List
from pydantic import BaseModel, ConfigDict


# ---------------------------------------------------------------
# Base configuration shared by ALL response schemas
# ---------------------------------------------------------------
# CONCEPT: model_config = ConfigDict(from_attributes=True)
# ---------------------------------------------------------
# By default Pydantic only reads data from dicts:
#   UserOut(id="abc", email="x@y.com")  ← works
#   UserOut.model_validate(user_orm_object) ← FAILS without this config
#
# from_attributes=True (formerly orm_mode=True in v1) tells Pydantic:
# "also try reading values from object attributes, not just dict keys"
#
# This is what makes  `return user_orm_object` work in a route
# whose response_model=UserOut. FastAPI internally calls
# UserOut.model_validate(user_orm_object) — and it works because
# of from_attributes=True.
#
# Rule: ALL response schemas need this. Request schemas don't.
# ---------------------------------------------------------------
class AppResponseSchema(BaseModel):
    """
    Base class for all schemas that serialize ORM objects into responses.
    Sets from_attributes=True so SQLAlchemy ORM objects can be passed directly.
    """
    model_config = ConfigDict(
        from_attributes=True,      # Read from ORM object attributes
        populate_by_name=True,     # Allow field aliases AND original names
        str_strip_whitespace=True, # Auto-strip leading/trailing spaces from strings
    )


# ---------------------------------------------------------------
# Generic Paginated List Response
# ---------------------------------------------------------------
# CONCEPT: Python Generics with TypeVar
# ----------------------------------------
# We want a reusable pagination wrapper that works for ANY item type:
#   GradeListResponse  → PaginatedResponse[GradeOut]
#   ExamListResponse   → PaginatedResponse[ExamOut]
#
# Without generics, you'd copy this class for every resource — DRY violation.
#
# TypeVar("T") creates a placeholder type variable.
# Generic[T] makes the class generic (parameterizable by T).
# When you write PaginatedResponse[GradeOut], Python substitutes T=GradeOut.
#
# FastAPI understands Generics and generates correct OpenAPI docs
# for each concrete instantiation.
# ---------------------------------------------------------------
T = TypeVar("T")


class PaginatedResponse(AppResponseSchema, Generic[T]):
    """
    Standard paginated list wrapper returned by all list endpoints.

    Example response:
    {
        "items": [...],
        "total": 147,
        "skip": 20,
        "limit": 20
    }

    The client uses total + skip + limit to know:
    - How many pages exist: ceil(total / limit)
    - Whether there's a next page: skip + limit < total
    """
    items: List[T]    # The actual list of objects (type varies per endpoint)
    total: int        # Total count of ALL matching records (ignoring pagination)
    skip: int         # How many records were skipped (current offset)
    limit: int        # Max records per page that was requested