import os
import uuid
import aiofiles
from typing import Optional, List
from fastapi import (
    APIRouter, Depends, HTTPException,
    UploadFile, File, Form, Query,
    status,
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database.postgres import get_db
from app.auth.dependencies import get_current_user, require_roles
from app.schemas.exams import ExamOut
import random
from app.models.grade import Grade, ReviewStatus
from app.models.user import User, UserRole

router = APIRouter(tags=["exams"])

UPLOAD_DIR = os.getenv("UPLOAD_DIR", "/tmp/exam_uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

ALLOWED_MIME_TYPES = {"application/pdf", "image/jpeg", "image/png"}
MAX_FILE_SIZE_MB = 20

@router.post("/", response_model=ExamOut, status_code=status.HTTP_201_CREATED)
async def upload_exam(
    title: str = Form(...),
    course_code: str = Form(...),
    subject: str = Form(""),
    description: Optional[str] = Form(None),
    total_marks: int = Form(...),
    file: UploadFile = File(...),
    answer_key: Optional[UploadFile] = File(None),
    student_scripts: Optional[UploadFile] = File(None),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_roles("teacher", "admin")),
):
    """Upload an exam paper (PDF or image). Only teachers and admins can create exams."""
    from app.models.exam import Exam

    if file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"File type '{file.content_type}' not allowed. Use PDF or image.",
        )

    contents = await file.read()
    size_mb = len(contents) / (1024 * 1024)

    if size_mb > MAX_FILE_SIZE_MB:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large ({size_mb:.1f} MB). Max is {MAX_FILE_SIZE_MB} MB.",
        )

    async def save_upload(u_file: UploadFile) -> str:
        contents = await u_file.read()
        f_ext = u_file.filename.rsplit(".", 1)[-1].lower()
        u_name = f"{uuid.uuid4()}.{f_ext}"
        path = os.path.join(UPLOAD_DIR, u_name)
        async with aiofiles.open(path, "wb") as f_out:
            await f_out.write(contents)
        return path

    file_path = await save_upload(file)
    answer_key_path = await save_upload(answer_key) if answer_key else None
    student_scripts_path = await save_upload(student_scripts) if student_scripts else None

    exam = Exam(
        title=title,
        course_code=course_code,
        subject=subject or course_code,
        description=description,
        total_marks=total_marks,
        file_path=file_path,
        file_name=file.filename,
        answer_key_path=answer_key_path,
        student_script_path=student_scripts_path,
        created_by=current_user.id,
        status="processing" if student_scripts else "pending",
    )

    db.add(exam)
    await db.commit()
    await db.refresh(exam)

    # Mock ML pipeline evaluation if student scripts are provided
    if student_scripts:
        # Generate some dummy students and grades
        for i in range(1, 6):
            dummy_email = f"student{i}_{exam.id}@mock.com"
            dummy_student = User(
                email=dummy_email,
                full_name=f"Mock Student {i}",
                roll_number=f"MOCK-26-{100+i}",
                hashed_password="mock",
                role=UserRole.student,
            )
            db.add(dummy_student)
            await db.commit()
            await db.refresh(dummy_student)
            
            score = random.randint(int(total_marks * 0.4), total_marks)
            grade = Grade(
                student_id=dummy_student.id,
                exam_id=exam.id,
                score=score,
                max_score=total_marks,
                confidence_score=random.uniform(0.7, 0.99),
                flagged_for_review=(score < total_marks * 0.6),
                review_status=ReviewStatus.pending,
            )
            db.add(grade)
        
        exam.status = "published"
        db.add(exam)
        await db.commit()

    return exam

@router.get("/", response_model=List[ExamOut])
async def list_exams(
    subject: Optional[str] = Query(None, description="Filter by subject"),
    status_filter: Optional[str] = Query(None, alias="status"),
    skip: int = Query(0, ge=0, description="Pagination offset"),
    limit: int = Query(20, ge=1, le=100, description="Max results per page"),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """List exams with optional subject/status filters."""
    from app.models.exam import Exam

    query = select(Exam)

    if current_user.role == "student":
        query = query.where(Exam.status == "published")
    elif status_filter:
        query = query.where(Exam.status == status_filter)

    if subject:
        query = query.where(Exam.subject.ilike(f"%{subject}%"))

    result = await db.execute(query.offset(skip).limit(limit))
    exams = result.scalars().all()

    return exams

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

    if current_user.role == "student" and exam.status != "published":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This exam is not yet available",
        )

    return exam

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

    if exam.file_path and os.path.exists(exam.file_path):
        os.remove(exam.file_path)

    await db.delete(exam)
    await db.commit()
