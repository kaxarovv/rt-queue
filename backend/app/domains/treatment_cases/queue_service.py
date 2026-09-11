"""
Предложение дат старта лечения с учётом месячной ёмкости МДГ-очереди.

Сознательно не связано с domains/scheduling (MachineSlot/Session/booking_service) --
тот модуль моделирует посуточное бронирование аппарата ("дневной стационар"),
это отдельный, пока не реализуемый уровень. Здесь ёмкость считается в людях
в месяц (см. settings.monthly_patient_capacity), без привязки к конкретным
слотам аппарата -- ровно то, что попросили врачи для этой части системы.

Система только ПРЕДЛАГАЕТ даты -- ничего не резервирует заранее. Подтверждение
(confirm_start_date в router.py) пере-проверяет ёмкость месяца в момент записи,
чтобы не потерять место в гонке двух одновременных подтверждений.
"""

from dataclasses import dataclass
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session as DbSession

from app.core.config import settings
from app.domains.treatment_cases.models import TreatmentCase
from app.domains.treatment_cases.priority_engine import compute_clinical_deadline
from app.shared.enums import CaseStatus, PriorityCategory


@dataclass
class SuggestedDate:
    date: date
    month_occupied: int
    month_capacity: int
    within_clinical_deadline: bool


def _month_bounds(year: int, month: int) -> tuple[date, date]:
    start = date(year, month, 1)
    end = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
    return start, end


def count_planned_in_month(db: DbSession, year: int, month: int) -> int:
    """
    Сколько случаев уже занимают место в этом месяце по дате СТАРТА лечения
    (planned_start_date), исключая отменённые. PENDING_REVIEW-случаи с уже
    подтверждённой датой считаются занимающими место -- именно они и есть
    "очередь", ещё не дошедшая до реального бронирования аппарата.
    """
    start, end = _month_bounds(year, month)
    return db.execute(
        select(func.count())
        .select_from(TreatmentCase)
        .where(
            TreatmentCase.planned_start_date >= start,
            TreatmentCase.planned_start_date < end,
            TreatmentCase.status != CaseStatus.CANCELLED,
        )
    ).scalar_one()


def _working_days_in_month(year: int, month: int) -> list[date]:
    start, end = _month_bounds(year, month)
    days = []
    current = start
    while current < end:
        if current.weekday() < 5:  # Пн-Пт
            days.append(current)
        current = date.fromordinal(current.toordinal() + 1)
    return days


def _add_month(year: int, month: int) -> tuple[int, int]:
    return (year + 1, 1) if month == 12 else (year, month + 1)


def suggest_start_dates(
    db: DbSession, case: TreatmentCase, months_ahead: int = 6, options: int = 3
) -> list[SuggestedDate]:
    """
    Ищет первый месяц (начиная с сегодняшнего), где ещё есть место в рамках
    monthly_patient_capacity, и предлагает до `options` дат внутри него,
    равномерно распределённых по рабочим дням месяца (без привязки к
    конкретным слотам аппарата -- см. пояснение в шапке модуля).

    Возвращает пустой список, если свободного места не нашлось в пределах
    months_ahead месяцев -- это сигнал врачу, что нужно эскалировать вручную
    (в скоуп этой задачи автоматическая эскалация/вытеснение не входит).
    """
    capacity = settings.monthly_patient_capacity
    deadline = compute_clinical_deadline(case)

    today = date.today()
    year, month = today.year, today.month

    for _ in range(months_ahead):
        occupied = count_planned_in_month(db, year, month)
        if occupied < capacity:
            working_days = [d for d in _working_days_in_month(year, month) if d >= today]
            if working_days:
                remaining_slots = capacity - occupied
                spread = min(options, len(working_days), remaining_slots) or 1
                step = max(len(working_days) // spread, 1)
                chosen = working_days[::step][:spread]

                return [
                    SuggestedDate(
                        date=d,
                        month_occupied=occupied,
                        month_capacity=capacity,
                        within_clinical_deadline=d <= deadline,
                    )
                    for d in chosen
                ]
        year, month = _add_month(year, month)

    return []


@dataclass
class QueueByPriority:
    category: str
    count: int


@dataclass
class CapacityByMonth:
    year: int
    month: int
    occupied: int
    capacity: int


@dataclass
class AvgWaitByPriority:
    category: str
    avg_days: float | None
    sample_size: int


@dataclass
class DashboardStats:
    queue_by_priority: list[QueueByPriority]
    capacity_by_month: list[CapacityByMonth]
    avg_wait_by_priority: list[AvgWaitByPriority]


def _queue_by_priority(db: DbSession) -> list[QueueByPriority]:
    """
    Состав текущей очереди (case в статусе PENDING_REVIEW -- то же условие,
    что использует QueueScreen на фронте) по категориям приоритета. Отдаём
    все 4 категории всегда, даже с нулём, чтобы фронту не пришлось
    достраивать недостающие бары самому.
    """
    # priority_category хранится как plain String в БД (не Enum-тип колонки,
    # см. models.py) -- Core-select возвращает обычные str-ключи ('immediate', ...),
    # но PriorityCategory(str, Enum) хэшируется и сравнивается как str, так что
    # прямой lookup по enum-члену работает без явного .value.
    rows = dict(
        db.execute(
            select(TreatmentCase.priority_category, func.count())
            .where(TreatmentCase.status == CaseStatus.PENDING_REVIEW)
            .group_by(TreatmentCase.priority_category)
        ).all()
    )
    return [QueueByPriority(category=cat.value, count=rows.get(cat, 0)) for cat in PriorityCategory]


def _capacity_by_month(db: DbSession, months_ahead: int = 6) -> list[CapacityByMonth]:
    """Занятость ёмкости на ближайшие months_ahead месяцев, начиная с текущего."""
    today = date.today()
    year, month = today.year, today.month
    result = []
    for _ in range(months_ahead):
        occupied = count_planned_in_month(db, year, month)
        result.append(
            CapacityByMonth(
                year=year, month=month, occupied=occupied, capacity=settings.monthly_patient_capacity
            )
        )
        year, month = _add_month(year, month)
    return result


def _avg_wait_by_priority(db: DbSession) -> list[AvgWaitByPriority]:
    """
    Среднее число дней от создания case до подтверждённой planned_start_date,
    по категориям приоритета. Считаем только case, где дата уже подтверждена --
    для ещё не подтверждённых "время ожидания" не определено.
    """
    cases = list(
        db.execute(
            select(TreatmentCase).where(TreatmentCase.planned_start_date.is_not(None))
        ).scalars()
    )

    by_category: dict[PriorityCategory, list[int]] = {cat: [] for cat in PriorityCategory}
    for case in cases:
        if case.priority_category is None:
            continue
        wait_days = (case.planned_start_date - case.created_at.date()).days
        by_category[PriorityCategory(case.priority_category)].append(wait_days)

    return [
        AvgWaitByPriority(
            category=cat.value,
            avg_days=(sum(days) / len(days)) if days else None,
            sample_size=len(days),
        )
        for cat, days in by_category.items()
    ]


def get_dashboard_stats(db: DbSession, months_ahead: int = 6) -> DashboardStats:
    return DashboardStats(
        queue_by_priority=_queue_by_priority(db),
        capacity_by_month=_capacity_by_month(db, months_ahead),
        avg_wait_by_priority=_avg_wait_by_priority(db),
    )
