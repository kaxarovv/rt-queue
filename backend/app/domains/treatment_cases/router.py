import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app.core.config import settings
from app.core.database import get_db
from app.domains.treatment_cases.models import TreatmentCase
from app.domains.treatment_cases.priority_engine import compute_clinical_deadline, compute_priority_score
from app.domains.treatment_cases.queue_service import (
    count_planned_in_month,
    get_dashboard_stats,
    suggest_start_dates,
)
from app.domains.treatment_cases.schemas import (
    ConfirmStartDateRequest,
    DashboardStatsOut,
    SuggestedDateOut,
    TreatmentCaseCreate,
    TreatmentCaseOut,
    UpdatePriorityRequest,
)
from app.shared.enums import CaseStatus

router = APIRouter(prefix="/api/cases", tags=["treatment_cases"])


@router.post("", response_model=TreatmentCaseOut, status_code=201)
def create_case(payload: TreatmentCaseCreate, db: DbSession = Depends(get_db)) -> TreatmentCase:
    """
    Создание случая лечения. Вызывается ПОСЛЕ того, как врач подтвердил данные
    на review-экране (или ввёл их вручную, если LLM недоступна/документа нет).
    priority_category приходит явно -- это финальное решение, которое либо
    совпадает с llm-предложением (если конфликта не было), либо было скорректировано
    врачом (если detect_signal_conflict() что-то нашёл).
    """
    case = TreatmentCase(
        **payload.model_dump(exclude={"confirmed_by_doctor"}),
        confirmed_by_doctor=payload.confirmed_by_doctor,
        confirmed_at=datetime.now(timezone.utc),
        status=CaseStatus.PENDING_REVIEW,
    )
    db.add(case)
    db.flush()  # created_at заполняется через server_default только после INSERT;
    # priority_engine на него опирается, поэтому flush обязателен до расчёта score.
    case.priority_score = compute_priority_score(case)
    case.clinical_deadline_date = compute_clinical_deadline(case)

    db.commit()
    db.refresh(case)
    return case


@router.get("", response_model=list[TreatmentCaseOut])
def list_cases(db: DbSession = Depends(get_db)) -> list[TreatmentCase]:
    """
    Список случаев, отсортированный по приоритету (наивысший -- первым).

    ВАЖНО: сортируем по ЖИВОМУ compute_priority_score(), а не по сохранённому
    в БД TreatmentCase.priority_score. Сохранённое значение считается один
    раз при создании case, когда aging-бонус ещё нулевой (см. priority_engine.py),
    и больше никогда не пересчитывается -- если сортировать по нему, случаи,
    давно ждущие своей очереди, никогда не поднимутся выше свежесозданных
    той же категории. Живой расчёт учитывает реальное время ожидания на
    каждый запрос.
    """
    cases = list(db.execute(select(TreatmentCase)).scalars())
    cases.sort(key=lambda c: compute_priority_score(c) if c.priority_category else -1, reverse=True)
    return cases


@router.get("/stats/dashboard", response_model=DashboardStatsOut)
def get_dashboard(db: DbSession = Depends(get_db)) -> DashboardStatsOut:
    """
    Агрегированная статистика для дэшборда очереди: состав очереди по
    приоритету, загрузка месячной ёмкости на 6 месяцев вперёд, среднее
    время ожидания (от создания case до подтверждённой planned_start_date)
    по категориям приоритета.
    """
    stats = get_dashboard_stats(db)
    return DashboardStatsOut(
        queue_by_priority=[vars(x) for x in stats.queue_by_priority],
        capacity_by_month=[vars(x) for x in stats.capacity_by_month],
        avg_wait_by_priority=[vars(x) for x in stats.avg_wait_by_priority],
    )


@router.get("/{case_id}", response_model=TreatmentCaseOut)
def get_case(case_id: uuid.UUID, db: DbSession = Depends(get_db)) -> TreatmentCase:
    case = db.get(TreatmentCase, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Случай не найден")
    return case


@router.get("/{case_id}/suggested-dates", response_model=list[SuggestedDateOut])
def get_suggested_dates(case_id: uuid.UUID, db: DbSession = Depends(get_db)) -> list[SuggestedDateOut]:
    """
    Предлагает до 3 дат старта лечения с учётом месячной ёмкости очереди
    (settings.monthly_patient_capacity). Ничего не резервирует -- только
    показывает варианты, врач подтверждает выбор через /confirm-date.
    """
    case = db.get(TreatmentCase, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Случай не найден")
    suggestions = suggest_start_dates(db, case)
    return [SuggestedDateOut(**vars(s)) for s in suggestions]


@router.post("/{case_id}/confirm-date", response_model=TreatmentCaseOut)
def confirm_start_date(
    case_id: uuid.UUID, payload: ConfirmStartDateRequest, db: DbSession = Depends(get_db)
) -> TreatmentCase:
    """
    Фиксирует выбранную врачом дату старта лечения. Пере-проверяет ёмкость
    месяца в момент записи (а не полагается на то, что было показано в
    /suggested-dates) -- защита от гонки, если два врача одновременно
    подтверждают места в почти заполненном месяце.
    """
    case = db.get(TreatmentCase, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Случай не найден")

    target = payload.planned_start_date
    occupied = count_planned_in_month(db, target.year, target.month)
    if occupied >= settings.monthly_patient_capacity:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Месяц {target.year}-{target.month:02d} уже заполнен "
                f"({occupied}/{settings.monthly_patient_capacity}). Обновите список предложений."
            ),
        )

    case.planned_start_date = target
    db.commit()
    db.refresh(case)
    return case


@router.post("/{case_id}/cancel", response_model=TreatmentCaseOut)
def cancel_case(case_id: uuid.UUID, db: DbSession = Depends(get_db)) -> TreatmentCase:
    """
    Отменяет case. planned_start_date намеренно не очищаем -- остаётся как
    исторический след, что случай собирался начаться в такую-то дату.
    queue_service.count_planned_in_month уже фильтрует status != CANCELLED,
    поэтому место в месячной ёмкости освобождается автоматически.
    """
    case = db.get(TreatmentCase, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Случай не найден")

    case.status = CaseStatus.CANCELLED
    db.commit()
    db.refresh(case)
    return case


@router.patch("/{case_id}/priority", response_model=TreatmentCaseOut)
def update_priority(
    case_id: uuid.UUID, payload: UpdatePriorityRequest, db: DbSession = Depends(get_db)
) -> TreatmentCase:
    """
    Меняет категорию приоритета уже созданного случая (переоценка врачом) и
    пересчитывает clinical_deadline_date под новую категорию. Уже
    подтверждённую planned_start_date не трогаем -- врач увидит новый дедлайн
    на карточке и при необходимости сам запросит новые suggested-dates.
    """
    case = db.get(TreatmentCase, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Случай не найден")

    case.priority_category = payload.priority_category
    case.clinical_deadline_date = compute_clinical_deadline(case)
    db.commit()
    db.refresh(case)
    return case
