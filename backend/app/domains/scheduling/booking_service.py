"""
Happy-path бронирование: поиск N свободных слотов под курс лечения.

КЛЮЧЕВОЙ ПРИНЦИП (важный фикс после реального использования): clinical_deadline_date --
это требование к дате ПЕРВОГО сеанса ("начать лечение не позднее X"), а НЕ требование
уместить ВЕСЬ курс из N сеансов в это узкое окно. Категория IMMEDIATE даёт всего
3 дня на дедлайн -- если требовать, чтобы все 5+ сеансов курса поместились в эти
3 календарных дня (в среднем 2-3 рабочих дня), это структурно невозможно почти для
любого многосеансового курса, независимо от реальной загрузки аппарата. Раньше это
ошибочно вызывало предложение вытеснения даже при полностью свободном аппарате.

Исправленная модель: ищем достаточно слотов под ВЕСЬ курс в широком горизонте,
но проверяем только, что ПЕРВЫЙ сеанс укладывается в clinical_deadline_date.
Вытеснение имеет смысл вызывать, только если даже первый сеанс некуда поставить
в пределах дедлайна -- остальные сеансы продолжаются в обычном порядке после этого.

Упрощение для демо (см. README): вместо полноценного учёта fractions_per_week
с допустимыми gap'ами между фракциями, берём просто следующие N свободных слотов
на РАЗНЫХ рабочих днях по порядку.
"""

from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app.domains.scheduling.capacity_service import generate_slots_for_range
from app.domains.scheduling.models import MachineSlot, Session as RtSession
from app.domains.treatment_cases.models import TreatmentCase
from app.shared.enums import CaseStatus, SessionStatus, SlotStatus


def find_available_slots(
    db: DbSession, sessions_required: int, search_from: date, search_until: date
) -> list[MachineSlot]:
    """
    Возвращает до `sessions_required` свободных слотов (по одному на
    рабочий день, в хронологическом порядке) в диапазоне [search_from, search_until].
    Если слотов на этот диапазон ещё не существует в БД -- генерирует их
    автоматически (ленивая генерация, чтобы не требовать отдельного
    ручного шага "создайте расписание на год вперёд").
    """
    generate_slots_for_range(db, search_from, search_until)

    free_slots = list(
        db.execute(
            select(MachineSlot)
            .where(
                MachineSlot.slot_date >= search_from,
                MachineSlot.slot_date <= search_until,
                MachineSlot.status == SlotStatus.FREE,
            )
            .order_by(MachineSlot.slot_date, MachineSlot.time_start)
        ).scalars()
    )

    # По одному слоту на день (первый свободный в этот день), пока не наберём нужное количество
    selected: list[MachineSlot] = []
    seen_dates: set[date] = set()
    for slot in free_slots:
        if slot.slot_date in seen_dates:
            continue
        selected.append(slot)
        seen_dates.add(slot.slot_date)
        if len(selected) == sessions_required:
            break

    return selected


def compute_search_window(case: TreatmentCase) -> tuple[date, date]:
    """
    Общее окно поиска для ВСЕГО курса лечения (не только для первого сеанса).
    Специально шире, чем clinical_deadline_date -- см. пояснение в шапке модуля.
    """
    search_from = date.today()
    days_until_deadline = max((case.clinical_deadline_date - search_from).days, 0)
    # Запас под весь курс: либо ~3 календарных дня на сеанс с запасом,
    # либо минимум 14 дней -- берём большее, плюс сколько уже прошло до дедлайна.
    generous_days = max(case.sessions_required * 3, 14)
    search_until = search_from + timedelta(days=days_until_deadline + generous_days)
    return search_from, search_until


def first_session_within_deadline(slots: list[MachineSlot], case: TreatmentCase) -> bool:
    """
    Проверяет, что ПЕРВЫЙ найденный слот укладывается в клинический дедлайн.
    Это единственная проверка "успели вовремя" -- остальные сеансы курса
    могут (и в реальности почти всегда будут) выходить за пределы этого окна.
    """
    if not slots:
        return False
    return slots[0].slot_date <= case.clinical_deadline_date


def book_case(db: DbSession, case: TreatmentCase) -> list[RtSession]:
    """
    Бронирует найденные слоты под случай: создаёт Session-записи,
    помечает MachineSlot как booked, переводит case в статус SCHEDULED.
    Вызывающий код (router) отвечает за предварительную проверку через
    find_available_slots + first_session_within_deadline.
    """
    search_from, search_until = compute_search_window(case)

    slots = find_available_slots(db, case.sessions_required, search_from, search_until)
    if len(slots) < case.sessions_required:
        raise ValueError(
            f"Недостаточно свободных слотов: найдено {len(slots)} из {case.sessions_required} требуемых"
        )

    sessions = []
    for i, slot in enumerate(slots, start=1):
        slot.status = SlotStatus.BOOKED
        rt_session = RtSession(
            treatment_case_id=case.id,
            machine_slot_id=slot.id,
            session_number=i,
            status=SessionStatus.CONFIRMED,
            scheduled_date=slot.slot_date,
        )
        db.add(rt_session)
        sessions.append(rt_session)

    case.status = CaseStatus.SCHEDULED
    db.commit()
    for s in sessions:
        db.refresh(s)
    return sessions