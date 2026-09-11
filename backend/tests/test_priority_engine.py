from datetime import date, datetime, timedelta, timezone

import pytest

from app.domains.treatment_cases.models import TreatmentCase
from app.domains.treatment_cases.priority_engine import (
    AGING_WEIGHT_PER_DAY,
    MAX_AGING_BONUS,
    compute_clinical_deadline,
    compute_priority_score,
)
from app.shared.enums import PriorityCategory


def make_case(priority_category, created_days_ago: int = 0) -> TreatmentCase:
    """Собирает TreatmentCase в памяти, без похода в БД -- чистым функциям это не нужно."""
    case = TreatmentCase()
    case.priority_category = priority_category
    case.created_at = datetime.now(timezone.utc) - timedelta(days=created_days_ago)
    return case


def test_base_score_matches_category_without_waiting():
    case = make_case(PriorityCategory.URGENT_1_2_WEEKS, created_days_ago=0)
    score = compute_priority_score(case, as_of=case.created_at.date())
    assert score == PriorityCategory.URGENT_1_2_WEEKS.base_score


def test_aging_bonus_grows_with_wait_time():
    case = make_case(PriorityCategory.LOW_3_MONTHS, created_days_ago=0)
    as_of = case.created_at.date() + timedelta(days=10)
    score = compute_priority_score(case, as_of=as_of)
    assert score == PriorityCategory.LOW_3_MONTHS.base_score + 10 * AGING_WEIGHT_PER_DAY


def test_aging_bonus_is_capped():
    case = make_case(PriorityCategory.LOW_3_MONTHS, created_days_ago=0)
    as_of = case.created_at.date() + timedelta(days=1000)
    score = compute_priority_score(case, as_of=as_of)
    assert score == PriorityCategory.LOW_3_MONTHS.base_score + MAX_AGING_BONUS


def test_aging_never_lets_low_priority_overtake_immediate():
    old_low = make_case(PriorityCategory.LOW_3_MONTHS, created_days_ago=0)
    fresh_immediate = make_case(PriorityCategory.IMMEDIATE, created_days_ago=0)
    as_of = old_low.created_at.date() + timedelta(days=1000)

    low_score = compute_priority_score(old_low, as_of=as_of)
    immediate_score = compute_priority_score(fresh_immediate, as_of=as_of)

    assert low_score < immediate_score


def test_missing_priority_category_raises():
    case = make_case(None)
    with pytest.raises(ValueError):
        compute_priority_score(case)


def test_clinical_deadline_uses_category_max_wait_days():
    case = make_case(PriorityCategory.IMMEDIATE, created_days_ago=0)
    deadline = compute_clinical_deadline(case)
    assert deadline == case.created_at.date() + timedelta(days=PriorityCategory.IMMEDIATE.max_wait_days)
