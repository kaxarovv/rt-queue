"""
Расчёт priority_score: базовая категория (см. PriorityCategory.base_score
в shared/enums.py) + aging-бонус за время ожидания.

Aging нужен, чтобы низкоприоритетный, но давно ждущий случай постепенно
поднимался в очереди -- классический паттерн weighted priority queue with
aging из планирования ОС, адаптированный под клинический контекст (см.
обсуждение в самом начале проектирования). Без aging случай из категории
LOW_3_MONTHS теоретически может годами уступать место каждому новому
IMMEDIATE-случаю, даже если объективно уже давно ждёт своей очереди.
"""

from datetime import date, timedelta

from app.domains.treatment_cases.models import TreatmentCase
from app.shared.enums import PriorityCategory

# Вес aging: сколько очков добавляется к score за каждый день ожидания.
# Подобран так, чтобы случай не мог "перепрыгнуть" в категорию выше на
# коротких сроках (у категорий разрыв base_score минимум 250 очков),
# но чтобы очень долгое ожидание (месяцы) всё же ощутимо поднимало приоритет
# внутри своей и соседних категорий. TODO(prod): вынести в БД-конфиг,
# сейчас константа для демо.
AGING_WEIGHT_PER_DAY = 3.0

# Верхний предел aging-бонуса, чтобы очень старый случай не начал обгонять
# IMMEDIATE-категорию только за счёт времени ожидания -- это было бы клинически
# неверно (боль/кровотечение всегда должны оставаться наверху).
MAX_AGING_BONUS = 200.0


def compute_priority_score(case: TreatmentCase, as_of: date | None = None) -> float:
    """
    Возвращает итоговый priority_score. Выше -- срочнее.

    as_of передаётся явно (а не берётся из date.today() внутри) для
    тестируемости -- можно посчитать score "как будто сегодня другая дата"
    без монки-патчинга времени.
    """
    if case.priority_category is None:
        raise ValueError(
            f"Невозможно посчитать priority_score: case {case.id} не имеет priority_category. "
            "Категория должна быть выставлена врачом на шаге review до создания случая."
        )

    category = PriorityCategory(case.priority_category)
    today = as_of or date.today()

    days_waiting = (today - case.created_at.date()).days
    aging_bonus = min(days_waiting * AGING_WEIGHT_PER_DAY, MAX_AGING_BONUS)

    return category.base_score + aging_bonus


def compute_clinical_deadline(case: TreatmentCase, as_of: date | None = None) -> date:
    """
    Крайний срок начала лечения = дата создания случая + max_wait_days
    категории приоритета. Используется booking_service, чтобы понять,
    укладывается ли найденный слот в клинически допустимое окно.
    """
    if case.priority_category is None:
        raise ValueError(f"Case {case.id} не имеет priority_category")

    category = PriorityCategory(case.priority_category)
    base_date = as_of or case.created_at.date()

    return base_date + timedelta(days=category.max_wait_days)
