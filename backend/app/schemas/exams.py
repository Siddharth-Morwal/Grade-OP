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
    description: Optional[str] = None
    total_marks: int
    file_name: str
    status: ExamStatus
    created_by: uuid.UUID
    created_at: datetime
    updated_at: datetime

    # Tells Pydantic to read data from SQLAlchemy model
    model_config = {"from_attributes": True}