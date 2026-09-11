import uuid

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app.core.database import get_db
from app.domains.patients.models import Patient
from app.domains.patients.schemas import PatientCreate, PatientOut
from app.domains.treatment_cases.models import TreatmentCase
from app.domains.treatment_cases.schemas import TreatmentCaseOut

router = APIRouter(prefix="/api/patients", tags=["patients"])


@router.post("", response_model=PatientOut)
def create_patient(payload: PatientCreate, response: Response, db: DbSession = Depends(get_db)) -> Patient:
    """
    Создаёт пациента, либо -- если пациент с таким ИИН уже есть -- возвращает
    существующую запись (200 вместо 409). Повторная загрузка карты того же
    пациента (второй курс лечения) -- нормальный сценарий, а не ошибка;
    ничего не перезаписываем в найденной записи, чтобы опечатка при повторном
    вводе не затёрла корректные данные.
    """
    existing = db.execute(select(Patient).where(Patient.iin == payload.iin)).scalar_one_or_none()
    if existing:
        response.status_code = 200
        return existing

    response.status_code = 201
    patient = Patient(**payload.model_dump())
    db.add(patient)
    db.commit()
    db.refresh(patient)
    return patient


@router.get("", response_model=list[PatientOut])
def list_patients(db: DbSession = Depends(get_db)) -> list[Patient]:
    return list(db.execute(select(Patient).order_by(Patient.created_at.desc())).scalars())


@router.get("/{patient_id}", response_model=PatientOut)
def get_patient(patient_id: uuid.UUID, db: DbSession = Depends(get_db)) -> Patient:
    patient = db.get(Patient, patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Пациент не найден")
    return patient


@router.get("/{patient_id}/cases", response_model=list[TreatmentCaseOut])
def list_patient_cases(patient_id: uuid.UUID, db: DbSession = Depends(get_db)) -> list[TreatmentCase]:
    """
    История случаев лечения пациента -- новые сверху. Профиль пациента
    существует именно для этого: с починенным дедупом по ИИН один пациент
    теперь может иметь несколько курсов лечения (повторные обращения),
    и без этого эндпоинта их негде увидеть вместе.
    """
    patient = db.get(Patient, patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Пациент не найден")
    return list(
        db.execute(
            select(TreatmentCase)
            .where(TreatmentCase.patient_id == patient_id)
            .order_by(TreatmentCase.created_at.desc())
        ).scalars()
    )
