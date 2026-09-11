import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class PatientCreate(BaseModel):
    iin: str
    full_name: str
    birth_date: date | None = None


class PatientOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    iin: str
    full_name: str
    birth_date: date | None
    created_at: datetime
