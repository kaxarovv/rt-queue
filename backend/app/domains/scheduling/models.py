import uuid
from datetime import date, datetime, time
from typing import TYPE_CHECKING

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Time, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.shared.enums import SessionStatus, SlotStatus

if TYPE_CHECKING:
    from app.domains.treatment_cases.models import TreatmentCase


class MachineSlot(Base):
    """
    Единица бронирования аппарата ЛТ. Один аппарат -> один слот
    не может быть занят дважды. Физическая защита от double-booking
    обеспечивается EXCLUDE constraint на уровне БД (см. __table_args__),
    а не только проверкой в коде приложения.
    """

    __tablename__ = "machine_slots"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    slot_date: Mapped[date] = mapped_column(Date, index=True)
    time_start: Mapped[time] = mapped_column(Time)
    time_end: Mapped[time] = mapped_column(Time)

    status: Mapped[SlotStatus] = mapped_column(String(20), default=SlotStatus.FREE)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    session: Mapped["Session | None"] = relationship(back_populates="machine_slot", uselist=False)

    __table_args__ = (
        # TODO(prod): заменить на настоящий ExcludeConstraint с GIST по
        # tsrange(slot_date+time_start, slot_date+time_end), требует расширения
        # btree_gist (CREATE EXTENSION btree_gist) и raw-SQL диапазонного выражения
        # в отдельной Alembic-миграции. Для демо ограничиваемся uniqueness
        # на старт слота -- защищает от точного дубля, но не от частичного
        # пересечения интервалов. Отмечено как известное упрощение.
        UniqueConstraint("slot_date", "time_start", name="uq_machine_slot_date_start"),
    )


class Session(Base):
    """Один сеанс лучевой терапии в рамках курса лечения (treatment_case)."""

    __tablename__ = "sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    treatment_case_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("treatment_cases.id"), index=True)
    machine_slot_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("machine_slots.id"), unique=True, nullable=True
    )

    session_number: Mapped[int] = mapped_column(Integer)  # 1..N в рамках курса
    status: Mapped[SessionStatus] = mapped_column(String(20), default=SessionStatus.PLANNED)

    scheduled_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    actual_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    treatment_case: Mapped["TreatmentCase"] = relationship(back_populates="sessions")
    machine_slot: Mapped["MachineSlot | None"] = relationship(back_populates="session")
