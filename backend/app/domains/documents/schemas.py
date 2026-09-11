import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class SourceDocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    original_filename: str
    status: str
    extracted_entities: dict
    confidence_scores: dict
    conflict_info: dict | None
    error_message: str | None
    created_at: datetime
    case_id: uuid.UUID | None = None
