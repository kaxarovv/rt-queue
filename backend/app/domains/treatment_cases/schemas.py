import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.shared.enums import CaseStatus, ClinicalPathway, PriorityCategory, TreatmentModality


class TreatmentCaseCreate(BaseModel):
    """
    Создание случая лечения -- это происходит ПОСЛЕ того, как врач подтвердил
    (или скорректировал) данные, извлечённые LLM/regex на предыдущем шаге.
    priority_category здесь обязателен и приходит от врача явно -- даже если
    LLM не нашла конфликта, финальное решение по приоритету принимает система
    только когда нет конфликта; при конфликте -- решение обязано быть ручным
    (см. conflict_detection.py). Для API это выглядит одинаково: категория
    всегда приходит извне, чтобы не плодить два разных пути создания случая.
    """

    patient_id: uuid.UUID
    source_document_id: uuid.UUID | None = None

    diagnosis_text: str
    icd10_code: str | None = None
    treatment_modality: TreatmentModality = TreatmentModality.UNKNOWN
    clinical_pathway: ClinicalPathway | None = None
    urgency_signals: dict = Field(default_factory=dict)

    priority_category: PriorityCategory
    has_signal_conflict: bool = False

    sessions_required: int
    fractions_per_week: int | None = None

    confirmed_by_doctor: str


class TreatmentCaseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    patient_id: uuid.UUID
    diagnosis_text: str
    icd10_code: str | None
    treatment_modality: str
    clinical_pathway: str | None
    urgency_signals: dict
    priority_category: str | None
    priority_score: float | None
    has_signal_conflict: bool
    sessions_required: int
    sessions_completed: int
    fractions_per_week: int | None
    status: str
    clinical_deadline_date: date | None
    planned_start_date: date | None
    confirmed_by_doctor: str | None
    confirmed_at: datetime | None
    created_at: datetime


class SuggestedDateOut(BaseModel):
    date: date
    month_occupied: int
    month_capacity: int
    within_clinical_deadline: bool


class ConfirmStartDateRequest(BaseModel):
    planned_start_date: date


class UpdatePriorityRequest(BaseModel):
    priority_category: PriorityCategory


class QueueByPriorityOut(BaseModel):
    category: str
    count: int


class CapacityByMonthOut(BaseModel):
    year: int
    month: int
    occupied: int
    capacity: int


class AvgWaitByPriorityOut(BaseModel):
    category: str
    avg_days: float | None
    sample_size: int


class DashboardStatsOut(BaseModel):
    queue_by_priority: list[QueueByPriorityOut]
    capacity_by_month: list[CapacityByMonthOut]
    avg_wait_by_priority: list[AvgWaitByPriorityOut]


class BookingResultOut(BaseModel):
    """
    Результат попытки бронирования: либо случай успешно поставлен в расписание,
    либо (при нехватке слотов для наивысшего приоритета) система предлагает
    кандидатов на вытеснение -- НЕ применяя их автоматически.
    """

    booked: bool
    treatment_case: TreatmentCaseOut
    booked_session_ids: list[uuid.UUID] = Field(default_factory=list)
    displacement_candidates: list[dict] = Field(default_factory=list)
    message: str
