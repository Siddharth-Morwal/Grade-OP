import uuid
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.database.mongo import get_mongo_db
from app.database.postgres import get_db
from app.auth.dependencies import get_current_user, require_roles
from app.schemas.questions import QuestionCreate, QuestionOut, QuestionUpdate

router = APIRouter(tags=["questions"])
COLLECTION = "questions"

async def _verify_exam_exists(exam_id: str, db) -> None:
    from app.models.exam import Exam
    from sqlalchemy import select

    result = await db.execute(select(Exam).where(Exam.id == uuid.UUID(exam_id)))
    if not result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Exam '{exam_id}' does not exist",
        )

@router.get("/{exam_id}", response_model=List[QuestionOut])
async def list_questions(
    exam_id: str,
    question_type: Optional[str] = Query(None, description="Filter by: mcq, essay, code"),
    db=Depends(get_db),
    mongo: AsyncIOMotorDatabase = Depends(get_mongo_db),
    current_user=Depends(get_current_user),
):
    """Return all questions for a given exam."""
    await _verify_exam_exists(exam_id, db)

    mongo_filter = {"exam_id": exam_id}
    if question_type:
        mongo_filter["type"] = question_type

    cursor = mongo[COLLECTION].find(mongo_filter).sort("order", 1)
    raw_docs = await cursor.to_list(length=500)

    questions = []
    for doc in raw_docs:
        doc["_id"] = str(doc["_id"])
        questions.append(doc)

    return questions

@router.post("/{exam_id}", response_model=QuestionOut, status_code=status.HTTP_201_CREATED)
async def create_question(
    exam_id: str,
    payload: QuestionCreate,
    db=Depends(get_db),
    mongo: AsyncIOMotorDatabase = Depends(get_mongo_db),
    current_user=Depends(require_roles("teacher", "admin")),
):
    """Add a question to an exam. Teachers and admins only."""
    await _verify_exam_exists(exam_id, db)

    doc = {
        "id": str(uuid.uuid4()),
        "exam_id": exam_id,
        "created_by": str(current_user.id),
        **payload.model_dump(),
    }

    result = await mongo[COLLECTION].insert_one(doc)
    doc["_id"] = str(result.inserted_id)

    return doc

@router.patch("/{exam_id}/{question_id}", response_model=QuestionOut)
async def update_question(
    exam_id: str,
    question_id: str,
    payload: QuestionUpdate,
    mongo: AsyncIOMotorDatabase = Depends(get_mongo_db),
    current_user=Depends(require_roles("teacher", "admin")),
):
    """Partially update a question. Teachers and admins only."""
    update_data = payload.model_dump(exclude_unset=True)

    if not update_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields provided for update",
        )

    result = await mongo[COLLECTION].update_one(
        {"id": question_id, "exam_id": exam_id},
        {"$set": update_data},
    )

    if result.matched_count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Question '{question_id}' not found in exam '{exam_id}'",
        )

    updated = await mongo[COLLECTION].find_one({"id": question_id})
    updated["_id"] = str(updated["_id"])
    return updated

@router.delete("/{exam_id}/{question_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_question(
    exam_id: str,
    question_id: str,
    mongo: AsyncIOMotorDatabase = Depends(get_mongo_db),
    _teacher=Depends(require_roles("teacher", "admin")),
):
    """Delete a single question. Teachers and admins only."""
    result = await mongo[COLLECTION].delete_one(
        {"id": question_id, "exam_id": exam_id}
    )

    if result.deleted_count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Question not found",
        )
