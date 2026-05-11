# ============================================================
# schemas/exams.py
# ============================================================
#
# CONCEPT: No ExamCreate schema here — why?
# ------------------------------------------
# The exam upload endpoint uses multipart/form-data (file + fields).
# FastAPI handles multipart via Form() and File() parameters directly
# in the route function signature — NOT via a Pydantic request body.
#
# You CANNOT have both a JSON Pydantic body AND an UploadFile in the
# same endpoint — they use different Content-Types. So the "create"
# shape is defined inline in the router with Form() fields.
#
# What we DO define here:
#   ExamOut         → response shape for a single exam
#   ExamListResponse→ paginated list of exams
#
# CONCEPT: Serialising Python Enum → JSON string
# -----------------------------------------------
# The ORM model stores ExamStatus as a PostgreSQL ENUM.
# Pydantic sees it as a Python enum (ExamStatus.pending).
# When serialising to JSON, Pydantic v2 serialises enums as their VALUE.
# ExamStatus.pending → "pending" in the JSON response. ✓
# ============================================================

import uuid
from datetime import datetime
from typing import Optional, List

from pydantic import Field

from app.models.exam import ExamStatus
from app.schemas.base import AppResponseSchema, PaginatedResponse


# ---------------------------------------------------------------
# ExamOut — response for single exam endpoints
# ---------------------------------------------------------------
# CONCEPT: Hiding internal fields from the response
# --------------------------------------------------
# The Exam ORM model has a `file_path` column — the absolute path
# on disk (e.g. /tmp/exam_uploads/550e8400.pdf).
# We DO NOT want to expose that in the API:
#   - It leaks server directory structure
#   - It's meaningless to clients
#
# Instead we expose `file_name` (original filename) and
# `status` (so clients know if it's ready to view).
# file_path is simply not declared in ExamOut → Pydantic omits it.
# ---------------------------------------------------------------
class ExamOut(AppResponseSchema):
    """
    Exam data returned by the API.
    Excludes file_path (internal server detail).
    """

    id: uuid.UUID = Field(description="Exam's unique identifier")

    title: str = Field(
        description="Human-readable title, e.g. 'Midterm Exam 2025'"
    )

    subject: str = Field(
        description="Subject area, e.g. 'Mathematics'"
    )

    description: Optional[str] = Field(
        default=None,
        description="Optional longer instructions or context for students",
    )

    total_marks: int = Field(
        description="Maximum achievable score on this exam",
        ge=1,             # Exams must be worth at least 1 mark
    )

    # We expose the original filename but NOT the file_path
    file_name: str = Field(
        description="Original filename as uploaded, e.g. 'midterm_2025.pdf'"
    )

    status: ExamStatus = Field(
        description="Lifecycle stage: pending | processing | published | archived"
    )

    # CONCEPT: Exposing the creator ID vs the full creator object
    # ------------------------------------------------------------
    # We could expose the full creator: creator: UserOut
    # That would require a JOIN and eager-loading the relationship.
    # For list endpoints, returning just the UUID is lighter and
    # clients can fetch user details separately if needed.
    # This tradeoff is called "shallow vs deep serialisation".
    created_by: uuid.UUID = Field(
        description="UUID of the teacher who uploaded this exam"
    )

    created_at: datetime = Field(description="When the exam was uploaded")
    updated_at: datetime = Field(description="When the exam was last modified")


# ---------------------------------------------------------------
# ExamListResponse — paginated response for GET /exams
# ---------------------------------------------------------------
# CONCEPT: Why not just return List[ExamOut]?
# --------------------------------------------
# Returning a bare array is tempting but loses important metadata:
#   - The client doesn't know how many total exams exist
#   - The client can't tell if there are more pages
#   - Adding pagination fields later is a BREAKING change
#
# Always wrap list responses in a pagination envelope from day 1.
# The PaginatedResponse[ExamOut] generic automatically gives us:
#   { "items": [...], "total": 147, "skip": 0, "limit": 20 }
# ---------------------------------------------------------------
class ExamListResponse(PaginatedResponse[ExamOut]):
    """
    Paginated list of exams.
    Inherits: items (List[ExamOut]), total, skip, limit from PaginatedResponse.
    """
    # No extra fields needed — PaginatedResponse[ExamOut] has everything.
    # The generic resolves `items` to List[ExamOut] automatically.
    pass