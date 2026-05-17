import uuid
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel

from app.models.grade import ReviewStatus

class QuestionScore(BaseModel):
    question_id: str
    topic: Optional[str] = None
    score: int
    max_score: int
    feedback: Optional[str] = None
    is_correct: Optional[bool] = None

class GradeCreate(BaseModel):
    student_id: str
    exam_id: str
    score: int
    max_score: int
    confidence_score: float
    flagged_for_review: bool = False
    ml_model_version: Optional[str] = None
    overall_justification: Optional[str] = None
    per_question_breakdown: Optional[List[QuestionScore]] = None

class ManualGradeCreate(BaseModel):
    student_name: str
    roll_number: str
    score: int
    exam_id: str

class GradeOut(BaseModel):
    id: uuid.UUID
    student_id: uuid.UUID
    student_name: Optional[str] = None
    student_roll: Optional[str] = None
    exam_id: uuid.UUID
    
    score: int
    max_score: int
    confidence_score: float
    ml_model_version: Optional[str] = None
    overall_justification: Optional[str] = None
    per_question_breakdown: Optional[List[QuestionScore]] = None
    
    flagged_for_review: bool
    review_status: ReviewStatus
    
    reviewed_by: Optional[uuid.UUID] = None
    reviewed_at: Optional[datetime] = None
    original_ml_score: Optional[int] = None
    override_reason: Optional[str] = None
    
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
