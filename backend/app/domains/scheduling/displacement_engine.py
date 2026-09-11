"""
Алгоритм вытеснения (Urgent Override): реализация раздела 4.3 из
исходного архитектурного обсуждения.

КРИТИЧЕСКИ ВАЖНО: этот модуль только НАХОДИТ и РАНЖИРУЕТ кандидатов
на сдвиг. Он никогда не применяет изменения сам -- это ответственность
router-эндпоинта, который требует явного подтверждения врача
(см. treatment_cases/router.py -> confirm-displacement).

Упрощение для демо (см. README): полноценная таблица reschedule_proposals
с историей предложений/решений не реализована -- кандидаты возвращаются
прямо в ответе API и не сохраняются между запросами. Для прода это нужно
доделать, чтобы иметь аудируемую историю решений врача.
"""

from dataclasses import dataclass, field
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app.domains.scheduling.models import MachineSlot, Session as RtSession
from app.domains.treatment_cases.models import TreatmentCase
from app.shared.enums import SessionStatus, SlotStatus

# Веса факторов ущерба -- см. calculate_damage(). Подобраны эмпирически для
# демо, в проде должны калиброваться вместе с клиническим отделом (см. наше
# обсуждение: чем сдвиг ощутимее для пациента, тем выше штраф).
WEIGHT_CONTINUITY = 10.0
WEIGHT_DEADLINE_PROXIMITY = 500.0
WEIGHT_FAIRNESS = 50.0


@dataclass
class DisplacementCandidate:
    session_id: str
    slot_id: str
    treatment_case_id: str
    patient_name: str
    original_date: date
    proposed_new_date: date | None
    damage_score: float
    explanation: str


def _find_alternative_slot(
    db: DbSession, occupant_case: TreatmentCase, exclude_slot_id
) -> MachineSlot | None:
    """Ищет ближайший свободный слот для пациента, которого предлагается сдвинуть."""
    candidate = db.execute(
        select(MachineSlot)
        .where(
            MachineSlot.status == SlotStatus.FREE,
            MachineSlot.id != exclude_slot_id,
            MachineSlot.slot_date >= date.today(),
        )
        .order_by(MachineSlot.slot_date, MachineSlot.time_start)
        .limit(1)
    ).scalar_one_or_none()
    return candidate


def _calculate_damage(
    occupant_case: TreatmentCase, alternative_slot: MachineSlot | None, original_date: date
) -> tuple[float, str]:
    """
    Считает "ущерб" от сдвига конкретного пациента. Возвращает (score, explanation).
    Ниже -- лучше (меньше ущерб для пациента).
    """
    if alternative_slot is None:
        # Нет альтернативы вообще -- максимальный штраф, такого кандидата
        # практически невозможно выбрать лучшим вариантом.
        return 1_000_000.0, "Нет доступного альтернативного слота для переноса"

    gap_days = (alternative_slot.slot_date - original_date).days
    continuity_risk = abs(gap_days) * WEIGHT_CONTINUITY

    deadline_score = 0.0
    if occupant_case.clinical_deadline_date:
        days_left = (occupant_case.clinical_deadline_date - alternative_slot.slot_date).days
        if days_left < 0:
            # Перенос вывел бы пациента ЗА пределы его собственного дедлайна -- тяжёлый штраф
            deadline_score = WEIGHT_DEADLINE_PROXIMITY * 3
        else:
            deadline_score = WEIGHT_DEADLINE_PROXIMITY / max(days_left, 1)

    # TODO(prod): учитывать реальное количество предыдущих переносов пациента
    # (нужна колонка reschedule_count в treatment_cases или таблица истории).
    # Для демо -- всегда 0, штраф за справедливость не применяется.
    fairness_penalty = 0.0

    total = continuity_risk + deadline_score + fairness_penalty
    explanation = (
        f"Сдвиг на {gap_days} дн. (риск непрерывности: {continuity_risk:.0f}), "
        f"дедлайн-давление: {deadline_score:.0f}"
    )
    return total, explanation


def find_displacement_candidates(
    db: DbSession, urgent_case: TreatmentCase, target_window_days: int = 7, top_n: int = 3
) -> list[DisplacementCandidate]:
    """
    Ищет до top_n кандидатов на вытеснение среди уже забронированных сеансов
    в ближайшие target_window_days, чей случай имеет более низкий priority_score,
    чем у urgent_case. Возвращает отсортированными по возрастанию damage_score
    (первый кандидат -- наименьший ущерб, наилучший выбор).
    """
    window_end = date.today() + timedelta(days=target_window_days)

    booked_sessions = list(
        db.execute(
            select(RtSession)
            .join(MachineSlot, RtSession.machine_slot_id == MachineSlot.id)
            .where(
                MachineSlot.slot_date >= date.today(),
                MachineSlot.slot_date <= window_end,
                RtSession.status == SessionStatus.CONFIRMED,
            )
        ).scalars()
    )

    candidates: list[DisplacementCandidate] = []
    for rt_session in booked_sessions:
        occupant_case = db.get(TreatmentCase, rt_session.treatment_case_id)
        if occupant_case is None or occupant_case.id == urgent_case.id:
            continue
        if (occupant_case.priority_score or 0) >= (urgent_case.priority_score or 0):
            continue  # вытесняем только тех, чей приоритет объективно ниже

        slot = db.get(MachineSlot, rt_session.machine_slot_id)
        alt_slot = _find_alternative_slot(db, occupant_case, exclude_slot_id=slot.id)
        damage, explanation = _calculate_damage(occupant_case, alt_slot, slot.slot_date)

        candidates.append(
            DisplacementCandidate(
                session_id=str(rt_session.id),
                slot_id=str(slot.id),
                treatment_case_id=str(occupant_case.id),
                patient_name=occupant_case.patient.full_name if occupant_case.patient else "?",
                original_date=slot.slot_date,
                proposed_new_date=alt_slot.slot_date if alt_slot else None,
                damage_score=damage,
                explanation=explanation,
            )
        )

    candidates.sort(key=lambda c: c.damage_score)
    return candidates[:top_n]
