import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app.core.database import get_db
from app.domains.scheduling.booking_service import (
    book_case,
    compute_search_window,
    find_available_slots,
    first_session_within_deadline,
)
from app.domains.scheduling.capacity_service import generate_slots_for_range
from app.domains.scheduling.displacement_engine import find_displacement_candidates
from app.domains.scheduling.models import MachineSlot, Session as RtSession
from app.domains.scheduling.schemas import (
    ConfirmDisplacementRequest,
    DisplacementCandidateOut,
    GenerateSlotsRequest,
    GenerateSlotsResponse,
    MachineSlotOut,
)
from app.domains.treatment_cases.models import TreatmentCase
from app.domains.treatment_cases.schemas import BookingResultOut, TreatmentCaseOut
from app.shared.enums import CaseStatus, SessionStatus, SlotStatus

router = APIRouter(prefix="/api/schedule", tags=["scheduling"])


@router.post("/generate-slots", response_model=GenerateSlotsResponse)
def generate_slots(payload: GenerateSlotsRequest, db: DbSession = Depends(get_db)) -> GenerateSlotsResponse:
    """
    Административная утилита: создать слоты аппарата на диапазон дат.
    Идемпотентно -- повторный вызов на те же даты не создаст дублей.
    Обычно не нужна вручную -- booking_service вызывает генерацию лениво,
    но полезна, чтобы заранее увидеть календарь на несколько месяцев вперёд.
    """
    created = generate_slots_for_range(db, payload.start_date, payload.end_date)
    return GenerateSlotsResponse(slots_created=created)


@router.get("/slots", response_model=list[MachineSlotOut])
def list_slots(
    start_date: date, end_date: date, db: DbSession = Depends(get_db)
) -> list[MachineSlot]:
    """Календарь слотов на диапазон дат -- то, что показывается на смарт-календаре."""
    return list(
        db.execute(
            select(MachineSlot)
            .where(MachineSlot.slot_date >= start_date, MachineSlot.slot_date <= end_date)
            .order_by(MachineSlot.slot_date, MachineSlot.time_start)
        ).scalars()
    )


@router.post("/cases/{case_id}/book", response_model=BookingResultOut)
def attempt_booking(case_id: uuid.UUID, db: DbSession = Depends(get_db)) -> BookingResultOut:
    """
    Happy-path + автоматический переход к предложению вытеснения при нехватке слотов.

    1. Ищем sessions_required свободных слотов в окне [сегодня, clinical_deadline_date].
    2. Если нашли достаточно -- бронируем, возвращаем booked=True.
    3. Если НЕТ -- ищем кандидатов на вытеснение через displacement_engine
       и возвращаем их в ответе. НИЧЕГО не применяется автоматически --
       врач должен явно вызвать /confirm-displacement.
    """
    case = db.get(TreatmentCase, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Случай не найден")
    if case.status != CaseStatus.PENDING_REVIEW:
        raise HTTPException(
            status_code=409, detail=f"Случай в статусе '{case.status}', бронирование недоступно"
        )

    # ВАЖНО: ищем слоты под ВЕСЬ курс в широком окне (compute_search_window),
    # а не только внутри clinical_deadline_date -- дедлайн проверяется ОТДЕЛЬНО,
    # и только для ПЕРВОГО сеанса (см. подробное объяснение в booking_service.py).
    # Курс из 5+ сеансов не обязан целиком поместиться в 3-дневное окно IMMEDIATE.
    search_from, search_until = compute_search_window(case)
    slots_full_course = find_available_slots(db, case.sessions_required, search_from, search_until)

    enough_slots = len(slots_full_course) >= case.sessions_required
    starts_on_time = first_session_within_deadline(slots_full_course, case)

    if enough_slots and starts_on_time:
        sessions = book_case(db, case)
        db.refresh(case)
        return BookingResultOut(
            booked=True,
            treatment_case=TreatmentCaseOut.model_validate(case),
            booked_session_ids=[s.id for s in sessions],
            displacement_candidates=[],
            message=(
                f"Забронировано {len(sessions)} сеансов, первый -- "
                f"{sessions[0].scheduled_date} (в пределах дедлайна {case.clinical_deadline_date})."
            ),
        )

    # Дефицит: либо не хватает слотов вообще на весь курс, либо (чаще) первый
    # сеанс не укладывается в дедлайн -- ищем, кого сдвинуть, чтобы освободить
    # место ИМЕННО в пределах дедлайна (не произвольные 14 дней).
    deadline_window_days = max((case.clinical_deadline_date - date.today()).days, 1)
    candidates = find_displacement_candidates(db, case, target_window_days=deadline_window_days)
    candidates_out = [
        DisplacementCandidateOut(
            session_id=c.session_id,
            slot_id=c.slot_id,
            treatment_case_id=c.treatment_case_id,
            patient_name=c.patient_name,
            original_date=c.original_date,
            proposed_new_date=c.proposed_new_date,
            proposed_new_slot_id=c.proposed_new_slot_id,
            damage_score=c.damage_score,
            explanation=c.explanation,
        )
        for c in candidates
    ]

    reason = (
        "первый сеанс не укладывается в дедлайн" if enough_slots and not starts_on_time
        else "недостаточно свободных слотов даже с учётом широкого горизонта поиска"
    )
    return BookingResultOut(
        booked=False,
        treatment_case=TreatmentCaseOut.model_validate(case),
        booked_session_ids=[],
        displacement_candidates=[c.model_dump() for c in candidates_out],
        message=(
            f"Не удалось начать лечение в пределах дедлайна ({case.clinical_deadline_date}): "
            f"{reason}. Найдено кандидатов на вытеснение: {len(candidates)}. Требуется решение врача."
        ),
    )


@router.post("/confirm-displacement", response_model=BookingResultOut)
def confirm_displacement(
    payload: ConfirmDisplacementRequest, db: DbSession = Depends(get_db)
) -> BookingResultOut:
    """
    Явное подтверждение врача: выполняет транзакционно два действия --
    (1) переносит сеанс occupant'а на новый слот, (2) освободившийся слот
    отдаёт срочному случаю. Это ЕДИНСТВЕННОЕ место в системе, где сдвиг
    расписания реально применяется -- и оно требует явного вызова с
    указанием confirmed_by_doctor, не срабатывает автоматически.
    """
    session_to_move = db.get(RtSession, payload.session_id_to_move)
    if not session_to_move:
        raise HTTPException(status_code=404, detail="Сеанс для переноса не найден")

    old_slot = db.get(MachineSlot, session_to_move.machine_slot_id)
    new_slot_for_moved = db.get(MachineSlot, payload.new_slot_id_for_moved_session)
    if not new_slot_for_moved or new_slot_for_moved.status != SlotStatus.FREE:
        raise HTTPException(status_code=409, detail="Предложенный новый слот больше не свободен")

    urgent_case = db.get(TreatmentCase, payload.urgent_case_id)
    if not urgent_case:
        raise HTTPException(status_code=404, detail="Срочный случай не найден")

    # 1. Переносим occupant'а на новый слот
    old_slot.status = SlotStatus.FREE
    new_slot_for_moved.status = SlotStatus.BOOKED
    session_to_move.machine_slot_id = new_slot_for_moved.id
    session_to_move.scheduled_date = new_slot_for_moved.slot_date
    session_to_move.status = SessionStatus.RESCHEDULED

    # 2. Освободившийся старый слот отдаём срочному случаю (бронируем его курс целиком)
    db.flush()  # чтобы find_available_slots увидел свежий FREE-статус old_slot
    sessions = book_case(db, urgent_case)
    db.refresh(urgent_case)

    return BookingResultOut(
        booked=True,
        treatment_case=TreatmentCaseOut.model_validate(urgent_case),
        booked_session_ids=[s.id for s in sessions],
        displacement_candidates=[],
        message=(
            f"Подтверждено врачом {payload.confirmed_by_doctor}: сеанс пациента "
            f"перенесён на {new_slot_for_moved.slot_date}, срочный случай забронирован."
        ),
    )