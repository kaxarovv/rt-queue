"""
Генерация machine_slots на диапазон дат.

TODO(prod): это должно стать таблицей machine_capacity_config, редактируемой
через UI (как обсуждали в самом начале проектирования), а не читаться из
.env констант. Для демо -- достаточно.
"""

from datetime import date, time, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app.core.config import settings
from app.domains.scheduling.models import MachineSlot
from app.shared.enums import SlotStatus

SLOT_DURATION_MINUTES = 30
DAY_START = time(9, 0)


def _is_working_day(d: date) -> bool:
    # Пн-Пт для machine_working_days_per_week=5. Для демо -- просто будни;
    # TODO(prod): учитывать реальный график (напр. Пн-Сб при 6 раб.днях).
    return d.weekday() < settings.machine_working_days_per_week


def generate_slots_for_range(db: DbSession, start_date: date, end_date: date) -> int:
    """
    Создаёт MachineSlot на каждый рабочий день в диапазоне, если слотов
    на эту дату ещё нет (идемпотентно -- повторный вызов не создаст дублей).
    Возвращает количество реально созданных слотов.
    """
    created_count = 0
    current = start_date

    while current <= end_date:
        if _is_working_day(current):
            existing = db.execute(
                select(MachineSlot.id).where(MachineSlot.slot_date == current).limit(1)
            ).first()
            if not existing:
                slot_start = DAY_START
                for _ in range(settings.machine_sessions_per_day):
                    slot_end_minutes = slot_start.hour * 60 + slot_start.minute + SLOT_DURATION_MINUTES
                    slot_end = time(slot_end_minutes // 60, slot_end_minutes % 60)

                    db.add(
                        MachineSlot(
                            slot_date=current,
                            time_start=slot_start,
                            time_end=slot_end,
                            status=SlotStatus.FREE,
                        )
                    )
                    created_count += 1
                    slot_start = slot_end
        current += timedelta(days=1)

    db.commit()
    return created_count
