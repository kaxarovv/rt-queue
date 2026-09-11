import uuid
from datetime import date, time

from pydantic import BaseModel, ConfigDict


class MachineSlotOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    slot_date: date
    time_start: time
    time_end: time
    status: str


class GenerateSlotsRequest(BaseModel):
    start_date: date
    end_date: date


class GenerateSlotsResponse(BaseModel):
    slots_created: int


class DisplacementCandidateOut(BaseModel):
    session_id: str
    slot_id: str
    treatment_case_id: str
    patient_name: str
    original_date: date
    proposed_new_date: date | None
    damage_score: float
    explanation: str


class ConfirmDisplacementRequest(BaseModel):
    """
    Явное подтверждение врача: какого пациента (session_id) переносим
    на какой слот (new_slot_id), и после этого -- на какой освободившийся
    слот ставим срочного пациента (urgent_case_id).
    """

    session_id_to_move: uuid.UUID
    new_slot_id_for_moved_session: uuid.UUID
    urgent_case_id: uuid.UUID
    confirmed_by_doctor: str
