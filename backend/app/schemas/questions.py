# ============================================================
# schemas/questions.py
# ============================================================

import uuid
from datetime import datetime
from typing import Optional, List, Any, Union, Annotated, Literal

from pydantic import BaseModel, Field, field_validator, ConfigDict

from app.schemas.base import AppResponseSchema


class QuestionBase(BaseModel):
    """Fields shared by all question types."""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        populate_by_name=True,
    )

    text: str = Field(
        ...,
        min_length=5,
        description="The question prompt shown to students",
        examples=["What is Newton's second law of motion?"],
    )

    marks: int = Field(
        ...,
        ge=1,
        le=100,
        description="Points awarded for a correct answer",
    )

    order: int = Field(
        ...,
        ge=1,
        description="Display order of this question within the exam (1-indexed)",
    )


class MCQCreate(QuestionBase):
    """Multiple choice question — requires options and a correct answer."""

    type: Literal["mcq"] = Field(
        description="Question type discriminator — must be 'mcq'"
    )

    options: List[str] = Field(
        ...,
        min_length=2,
        max_length=6,
        description="Answer choices. Minimum 2, maximum 6.",
        examples=[["Newton's First Law", "F = ma", "E = mc²", "Ohm's Law"]],
    )

    correct_answer: str = Field(
        ...,
        description="The exact string from `options` that is the correct answer",
    )

    @field_validator("correct_answer", mode="after")
    @classmethod
    def correct_answer_must_be_an_option(cls, v: str, info) -> str:
        options = info.data.get("options", [])
        if options and v not in options:
            raise ValueError(
                f"correct_answer '{v}' must be one of the provided options"
            )
        return v

    explanation: Optional[str] = Field(
        default=None,
        description="Optional explanation shown after the student answers",
    )


class EssayCreate(QuestionBase):
    """Open-ended essay question with a word limit and optional rubric."""

    type: Literal["essay"] = Field(
        description="Question type discriminator — must be 'essay'"
    )

    word_limit: Optional[int] = Field(
        default=None,
        ge=50,
        le=5000,
        description="Maximum word count for the answer. None = no limit.",
    )

    rubric: Optional[dict[str, Any]] = Field(
        default=None,
        description="Marking rubric. Free-form JSON — the ML model reads this.",
    )

    sample_answer: Optional[str] = Field(
        default=None,
        description="Optional model answer used by the ML grader as reference",
    )


class CodeCreate(QuestionBase):
    """Programming question with test cases for automated evaluation."""

    type: Literal["code"] = Field(
        description="Question type discriminator — must be 'code'"
    )

    language: str = Field(
        ...,
        description="Programming language: 'python', 'javascript', 'java', etc.",
        examples=["python"],
    )

    starter_code: Optional[str] = Field(
        default=None,
        description="Boilerplate code the student starts with",
    )

    test_cases: List[dict[str, Any]] = Field(
        default_factory=list,
        description="Input/output pairs used to verify the student's solution",
    )

    time_limit_seconds: Optional[int] = Field(
        default=5,
        ge=1,
        le=30,
        description="Max execution time before the submission is rejected",
    )


QuestionCreate = Annotated[
    Union[MCQCreate, EssayCreate, CodeCreate],
    Field(discriminator="type"),
]


class QuestionUpdate(BaseModel):
    """
    Partial update for any question type.
    Only include fields you want to change.
    Type cannot be changed after creation.
    """
    model_config = ConfigDict(str_strip_whitespace=True)

    text: Optional[str]            = Field(default=None, min_length=5)
    marks: Optional[int]           = Field(default=None, ge=1, le=100)
    order: Optional[int]           = Field(default=None, ge=1)
    # MCQ fields
    options: Optional[List[str]]   = Field(default=None, min_length=2)
    correct_answer: Optional[str]  = Field(default=None)
    explanation: Optional[str]     = Field(default=None)
    # Essay fields
    word_limit: Optional[int]      = Field(default=None, ge=50)
    rubric: Optional[dict]         = Field(default=None)
    sample_answer: Optional[str]   = Field(default=None)
    # Code fields
    language: Optional[str]        = Field(default=None)
    starter_code: Optional[str]    = Field(default=None)
    test_cases: Optional[List[dict]] = Field(default=None)
    time_limit_seconds: Optional[int] = Field(default=None, ge=1, le=30)


class QuestionOut(BaseModel):
    """
    Question document returned from MongoDB.
    Used as the response schema for all question endpoints.
    """
    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(description="Question's UUID (stored as string in MongoDB)")
    exam_id: str = Field(description="UUID of the exam this question belongs to")
    created_by: str = Field(description="UUID of the teacher who created this question")

    type: str = Field(description="Question type: mcq | essay | code")
    text: str = Field(description="The question prompt")
    marks: int = Field(description="Points for correct answer")
    order: int = Field(description="Display order within the exam")

    options: Optional[List[str]]  = Field(default=None)
    correct_answer: Optional[str] = Field(default=None)
    explanation: Optional[str]    = Field(default=None)
    word_limit: Optional[int]     = Field(default=None)
    rubric: Optional[dict]        = Field(default=None)
    sample_answer: Optional[str]  = Field(default=None)
    language: Optional[str]       = Field(default=None)
    starter_code: Optional[str]   = Field(default=None)
    test_cases: Optional[List[dict]] = Field(default=None)
    time_limit_seconds: Optional[int] = Field(default=None)
