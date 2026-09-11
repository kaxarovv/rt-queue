import random
from datetime import date

from app.core.config import settings
from app.domains.patients.models import Patient
from app.domains.treatment_cases.models import TreatmentCase
from app.domains.treatment_cases.priority_engine import compute_clinical_deadline
from app.domains.treatment_cases.queue_service import count_planned_in_month, suggest_start_dates
from app.shared.enums import CaseStatus, PriorityCategory


def make_patient(db) -> Patient:
    patient = Patient(iin="".join(random.choices("0123456789", k=12)), full_name="Test Patient")
    db.add(patient)
    db.flush()
    return patient


def make_case(db, patient, priority_category=PriorityCategory.PLANNED_1_2_MONTHS, planned_start_date=None,
              status=CaseStatus.PENDING_REVIEW) -> TreatmentCase:
    case = TreatmentCase(
        patient_id=patient.id,
        diagnosis_text="test",
        priority_category=priority_category,
        sessions_required=3,
        status=status,
        planned_start_date=planned_start_date,
    )
    db.add(case)
    db.flush()
    case.clinical_deadline_date = compute_clinical_deadline(case)
    db.flush()
    return case


def next_month_first_day(d: date) -> date:
    return date(d.year + 1, 1, 1) if d.month == 12 else date(d.year, d.month + 1, 1)


def test_count_planned_in_month_excludes_cancelled(db):
    today = date.today()
    baseline = count_planned_in_month(db, today.year, today.month)

    patient = make_patient(db)
    make_case(db, patient, planned_start_date=today, status=CaseStatus.PENDING_REVIEW)
    make_case(db, patient, planned_start_date=today, status=CaseStatus.CANCELLED)

    count = count_planned_in_month(db, today.year, today.month)
    assert count == baseline + 1


def test_count_planned_in_month_only_counts_target_month(db):
    today = date.today()
    other_month = next_month_first_day(today)
    baseline_current = count_planned_in_month(db, today.year, today.month)
    baseline_other = count_planned_in_month(db, other_month.year, other_month.month)

    patient = make_patient(db)
    make_case(db, patient, planned_start_date=other_month)

    assert count_planned_in_month(db, today.year, today.month) == baseline_current
    assert count_planned_in_month(db, other_month.year, other_month.month) == baseline_other + 1


def test_suggest_start_dates_skips_full_month(db, monkeypatch):
    monkeypatch.setattr(settings, "monthly_patient_capacity", 1)
    patient = make_patient(db)
    today = date.today()
    # Заполняем текущий месяц единственным доступным местом.
    make_case(db, patient, planned_start_date=today)

    urgent_case = make_case(db, patient, priority_category=PriorityCategory.PLANNED_1_2_MONTHS)
    suggestions = suggest_start_dates(db, urgent_case)

    assert len(suggestions) > 0
    assert all(s.date.month != today.month or s.date.year != today.year for s in suggestions)
    assert all(s.month_occupied == 0 for s in suggestions)


def test_suggest_start_dates_flags_dates_past_deadline(db):
    patient = make_patient(db)
    urgent_case = make_case(db, patient, priority_category=PriorityCategory.IMMEDIATE)
    deadline = compute_clinical_deadline(urgent_case)

    suggestions = suggest_start_dates(db, urgent_case)

    assert len(suggestions) > 0
    for s in suggestions:
        assert s.within_clinical_deadline == (s.date <= deadline)
