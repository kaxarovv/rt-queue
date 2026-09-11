import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Date, DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.domains.treatment_cases.models import TreatmentCase


class Patient(Base):
    __tablename__ = "patients"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # NB: для демо храним как обычный текст. В проде — column-level encryption
    # (pgcrypto) + отдельный hash-индекс для поиска без расшифровки.
    iin: Mapped[str] = mapped_column(String(12), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(255))
    birth_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Строковая ссылка ("TreatmentCase") — маппер резолвится лениво,
    # реальный импорт класса происходит в app/core/model_registry.py,
    # который явно импортирует все модели один раз при старте приложения.
    treatment_cases: Mapped[list["TreatmentCase"]] = relationship(back_populates="patient")
