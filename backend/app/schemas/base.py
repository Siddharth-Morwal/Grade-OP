from pydantic import BaseModel, ConfigDict

# A simple base class so Pydantic knows to read from SQLAlchemy objects.
class AppResponseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)