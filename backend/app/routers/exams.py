# ============================================================
# routers/exams.py
# ============================================================
#
# CONCEPT: File Uploads in FastAPI
# ---------------------------------
# FastAPI handles file uploads via `UploadFile` + `File`.
# The request must be multipart/form-data (not JSON).
# You can mix UploadFile with Form() fields in the same endpoint.
#
# CONCEPT: Where do uploaded files go?
# --------------------------------------
# Option A: Local disk (simple, bad for production — dies if server restarts)
# Option B: Cloud storage — S3, GCS, Azure Blob (correct for production)
#
# We'll write to disk here for clarity, but the pattern is:
#   1. Receive the file bytes
#   2. Upload to S3 / store to disk
#   3. Save the *path/URL* to PostgreSQL (not the file itself)
#   4. The ML pipeline later reads from that path
#
# CONCEPT: Pagination
# --------------------
# GET /exams returns a list. You must paginate — never return
# unbounded lists. Standard pattern: skip + limit (offset pagination).
#   skip=0,  limit=20 → first page
#   skip=20, limit=20 → second page
# ============================================================

import os
import uuid
import aiofiles                           # async file I/O (pip install aiofiles)
from typing import Optional
from fastapi import (
    APIRouter, Depends, HTTPException,
    UploadFile, File, Form, Query,
    status,
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.database.postgres import get_db
from app.auth.dependencies import get_current_user, require_roles
from app.schemas.exams import ExamOut, ExamListResponse

router = APIRouter(prefix="/exams", tags=["exams"])

# Where uploaded exam files land on disk (override with env var in production)
UPLOAD_DIR = os.getenv("UPLOAD_DIR", "/tmp/exam_uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Allowed file types for exam papers
ALLOWED_MIME_TYPES = {"application/pdf", "image/jpeg", "image/png"}
MAX_FILE_SIZE_MB = 20


# ---------------------------------------------------------------
# POST /exams  → Upload an exam paper (teacher/admin only)
# ---------------------------------------------------------------
# CONCEPT: Form() vs Body()
# --------------------------
# When you're uploading a file, the Content-Type is multipart/form-data.
# JSON Body() doesn't work in the same request.
# Instead, use Form() for each text field alongside UploadFile.
#
# The client sends:
#   Content-Type: multipart/form-data
#   --boundary
#   name="title" ... Midterm 2025
#   --boundary
#   name="file" filename="exam.pdf" ... <bytes>
# ---------------------------------------------------------------
@router.post("/", response_model=ExamOut, status_code=status.HTTP_201_CREATED)
async def upload_exam(
    title: str = Form(...),                          # ... = required field
    subject: str = Form(...),
    description: Optional[str] = Form(None),         # None = optional
    total_marks: int = Form(...),
    file: UploadFile = File(...),                    # The actual file
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_roles("teacher", "admin")),
):
    """
    Upload an exam paper (PDF or image).
    Only teachers and admins can create exams.
    """
    from app.models.exam import Exam

    # ---- Validate file type ----
    # content_type comes from the browser/client — it can be spoofed.
    # In production, also inspect the file's magic bytes (python-magic).
    if file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"File type '{file.content_type}' not allowed. Use PDF or image.",
        )

    # ---- Read file and check size ----
    # file.read() loads the entire file into memory.
    # For very large files, stream in chunks instead.
    contents = await file.read()
    size_mb = len(contents) / (1024 * 1024)

    if size_mb > MAX_FILE_SIZE_MB:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large ({size_mb:.1f} MB). Max is {MAX_FILE_SIZE_MB} MB.",
        )

    # ---- Save file to disk ----
    # uuid4() generates a random unique name — prevents path collisions
    # and path traversal attacks (user can't name a file "../../etc/passwd")
    file_ext = file.filename.rsplit(".", 1)[-1].lower()
    unique_filename = f"{uuid.uuid4()}.{file_ext}"
    file_path = os.path.join(UPLOAD_DIR, unique_filename)

    # aiofiles: async file writes (doesn't block the event loop)
    async with aiofiles.open(file_path, "wb") as f:
        await f.write(contents)

    # ---- Persist metadata to PostgreSQL ----
    exam = Exam(
        title=title,
        subject=subject,
        description=description,
        total_marks=total_marks,
        file_path=file_path,          # Store the path, not the file
        file_name=file.filename,
        created_by=current_user.id,
        status="pending",             # ML pipeline will process it
    )

    db.add(exam)
    await db.commit()
    await db.refresh(exam)

    return exam


# ---------------------------------------------------------------
# GET /exams  → List exams with pagination and filtering
# ---------------------------------------------------------------
# CONCEPT: Query Parameters vs Path Parameters
# ---------------------------------------------
# Path param:  GET /exams/{exam_id}  → identifies a specific resource
# Query param: GET /exams?subject=math&skip=0&limit=20 → filters/pagination
#
# Query() lets you document and validate query params:
#   Query(0, ge=0)      → default=0, must be >= 0
#   Query(20, le=100)   → default=20, must be <= 100
# ---------------------------------------------------------------
@router.get("/", response_model=ExamListResponse)
async def list_exams(
    subject: Optional[str] = Query(None, description="Filter by subject"),
    status_filter: Optional[str] = Query(None, alias="status"),  # alias: status is a reserved word
    skip: int = Query(0, ge=0, description="Pagination offset"),
    limit: int = Query(20, ge=1, le=100, description="Max results per page"),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    List exams with optional subject/status filters.
    Students see only published exams; teachers see all.
    """
    from app.models.exam import Exam

    # ---- Build the query dynamically ----
    # Start with a base query, then conditionally add filters.
    # This is cleaner than building SQL strings (and safe from injection).
    query = select(Exam)

    # Students only see published exams
    if current_user.role == "student":
        query = query.where(Exam.status == "published")
    elif status_filter:
        query = query.where(Exam.status == status_filter)

    if subject:
        query = query.where(Exam.subject.ilike(f"%{subject}%"))  # case-insensitive LIKE

    # ---- Count total (for pagination metadata) ----
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar()

    # ---- Fetch paginated results ----
    result = await db.execute(query.offset(skip).limit(limit))
    exams = result.scalars().all()

    return ExamListResponse(
        items=exams,
        total=total,
        skip=skip,
        limit=limit,
    )


# ---------------------------------------------------------------
# GET /exams/{exam_id}  → Fetch single exam details
# ---------------------------------------------------------------
@router.get("/{exam_id}", response_model=ExamOut)
async def get_exam(
    exam_id: str,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Fetch a single exam by ID."""
    from app.models.exam import Exam

    result = await db.execute(
        select(Exam).where(Exam.id == uuid.UUID(exam_id))
    )
    exam = result.scalar_one_or_none()

    if not exam:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Exam {exam_id} not found",
        )

    # Students can't see unpublished exams
    if current_user.role == "student" and exam.status != "published":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This exam is not yet available",
        )

    return exam


# ---------------------------------------------------------------
# DELETE /exams/{exam_id}  → Remove exam (admin only)
# ---------------------------------------------------------------
@router.delete("/{exam_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_exam(
    exam_id: str,
    db: AsyncSession = Depends(get_db),
    _admin=Depends(require_roles("admin")),
):
    """Permanently delete an exam and its file. Admin only."""
    from app.models.exam import Exam

    result = await db.execute(select(Exam).where(Exam.id == uuid.UUID(exam_id)))
    exam = result.scalar_one_or_none()

    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")

    # Delete the file from disk too
    if exam.file_path and os.path.exists(exam.file_path):
        os.remove(exam.file_path)

    await db.delete(exam)
    await db.commit()
