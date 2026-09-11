import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.shared.enums import CaseStatus, ClinicalPathway, PriorityCategory, TreatmentModality

if TYPE_CHECKING:
    from app.domains.patients.models import Patient
    from app.domains.scheduling.models import Session as RtSession


class TreatmentCase(Base):
    """
    Один "случай лечения" = один курс ЛТ для пациента.
    Именно эта сущность несёт приоритет и клинический контекст,
    а не пациент напрямую — у одного пациента в перспективе
    может быть несколько курсов лечения в разное время.
    """

    __tablename__ = "treatment_cases"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    patient_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("patients.id"), index=True)
    source_document_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("source_documents.id"), nullable=True
    )

    diagnosis_text: Mapped[str] = mapped_column(String(1000))
    icd10_code: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # --- Разделение сигналов, см. shared/enums.py ---
    # Метод лечения (SRT/SRS/EBRT/...) — метаданные, НЕ определяют приоритет напрямую.
    treatment_modality: Mapped[TreatmentModality] = mapped_column(
        String(20), default=TreatmentModality.UNKNOWN
    )
    # Клинический путь — то, что реально определяет срочность.
    clinical_pathway: Mapped[ClinicalPathway | None] = mapped_column(String(30), nullable=True)
    # Сырые сигналы срочности из текста документа — для отображения врачу при конфликте.
    urgency_signals: Mapped[dict] = mapped_column(JSONB, default=dict)

    # Финальная категория приоритета — либо выставлена автоматически (нет конфликта,
    # высокий confidence), либо врачом вручную при конфликте/низком confidence.
    priority_category: Mapped[PriorityCategory | None] = mapped_column(String(20), nullable=True)
    priority_score: Mapped[float | None] = mapped_column(nullable=True)
    has_signal_conflict: Mapped[bool] = mapped_column(default=False)

    sessions_required: Mapped[int] = mapped_column(Integer)
    sessions_completed: Mapped[int] = mapped_column(Integer, default=0)
    fractions_per_week: Mapped[int | None] = mapped_column(Integer, nullable=True)

    status: Mapped[CaseStatus] = mapped_column(String(20), default=CaseStatus.PENDING_REVIEW)
    clinical_deadline_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    # Дата старта лечения, подтверждённая врачом из списка предложенных
    # queue_service.suggest_start_dates() вариантов. НЕ путать с
    # clinical_deadline_date (максимально допустимый срок) и с
    # scheduling.Session.scheduled_date (посуточное бронирование аппарата --
    # отдельный, пока не реализуемый уровень "дневного стационара").
    planned_start_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    confirmed_by_doctor: Mapped[str | None] = mapped_column(String(255), nullable=True)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    patient: Mapped["Patient"] = relationship(back_populates="treatment_cases")
    # NB: строка "Session" -- это реальное имя класса в SQLAlchemy registry
    # (app.domains.scheduling.models.Session), а не локальный алиас RtSession,
    # который существует только под TYPE_CHECKING для читаемости типов.
    sessions: Mapped[list["RtSession"]] = relationship(
        "Session", back_populates="treatment_case"
    )
