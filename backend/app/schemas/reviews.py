from pydantic import BaseModel
from typing import Optional
from app.schemas.grades import GradeOut

class OverridePayload(BaseModel):
    new_score: int
    override_reason: str

# A review is just a grade, so we can inherit from GradeOut
class ReviewOut(GradeOut):
    # If you want to add extra display fields for reviews later, you can put them here.
    pass
