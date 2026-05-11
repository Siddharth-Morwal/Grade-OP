from typing import Optional, List
from pydantic import BaseModel

# A single, simple schema for all question types.
# Depending on the "type" (mcq, essay, code), you just leave the other fields blank.
class QuestionCreate(BaseModel):
    text: str
    marks: int
    order: int
    type: str  # "mcq", "essay", or "code"
    
    # MCQ Fields
    options: Optional[List[str]] = None
    correct_answer: Optional[str] = None
    explanation: Optional[str] = None
    
    # Essay Fields
    word_limit: Optional[int] = None
    rubric: Optional[dict] = None
    sample_answer: Optional[str] = None
    
    # Code Fields
    language: Optional[str] = None
    starter_code: Optional[str] = None
    test_cases: Optional[List[dict]] = None
    time_limit_seconds: Optional[int] = None

class QuestionUpdate(BaseModel):
    text: Optional[str] = None
    marks: Optional[int] = None
    order: Optional[int] = None
    options: Optional[List[str]] = None
    correct_answer: Optional[str] = None
    explanation: Optional[str] = None
    word_limit: Optional[int] = None
    rubric: Optional[dict] = None
    sample_answer: Optional[str] = None
    language: Optional[str] = None
    starter_code: Optional[str] = None
    test_cases: Optional[List[dict]] = None
    time_limit_seconds: Optional[int] = None

# What MongoDB returns to the frontend
class QuestionOut(BaseModel):
    id: str  # MongoDB UUID as string
    exam_id: str
    created_by: str
    
    text: str
    marks: int
    order: int
    type: str
    
    options: Optional[List[str]] = None
    correct_answer: Optional[str] = None
    explanation: Optional[str] = None
    word_limit: Optional[int] = None
    rubric: Optional[dict] = None
    sample_answer: Optional[str] = None
    language: Optional[str] = None
    starter_code: Optional[str] = None
    test_cases: Optional[List[dict]] = None
    time_limit_seconds: Optional[int] = None
