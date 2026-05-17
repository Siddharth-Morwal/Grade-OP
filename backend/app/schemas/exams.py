import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel

from app.models.exam import ExamStatus

# The API response for an exam (excludes the file_path)
class ExamOut(BaseModel):
    id: uuid.UUID
    title: str
    subject: str
    course_code: str
    description: Optional[str] = None
    total_marks: int
    file_name: str
    answer_key_path: Optional[str] = None
    student_script_path: Optional[str] = None
    status: ExamStatus
    created_by: uuid.UUID
    created_at: datetime
    updated_at: datetime

    # Tells Pydantic to read data from SQLAlchemy model
    model_config = {"from_attributes": True}