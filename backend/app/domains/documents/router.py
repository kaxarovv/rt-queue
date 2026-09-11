import uuid

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app.core.database import get_db
from app.domains.documents.conflict_detection import detect_signal_conflict
from app.domains.documents.llm_extraction_service import LLMExtractionError, extract_entities_via_llm
from app.domains.documents.models import SourceDocument
from app.domains.documents.regex_extraction_service import (
    extract_dates,
    extract_iin_candidates,
    extract_icd10_codes,
)
from app.domains.documents.schemas import SourceDocumentOut
from app.domains.documents.storage_service import storage_service
from app.domains.documents.text_extraction_service import (
    clean_text_for_llm,
    extract_epicrisis_section,
    extract_text_from_pdf,
)
from app.domains.treatment_cases.models import TreatmentCase
from app.shared.enums import DocumentStatus

router = APIRouter(prefix="/api/documents", tags=["documents"])


@router.post("/upload", response_model=SourceDocumentOut, status_code=201)
async def upload_document(file: UploadFile, db: DbSession = Depends(get_db)) -> SourceDocument:
    """
    Шаг 1 пайплайна: Upload -> Text extraction (+ regex для детерминированных полей).
    LLM-экстракция запускается отдельным вызовом (POST /{id}/extract), не здесь --
    так врач может увидеть regex-результаты и текст сразу, не дожидаясь LLM.

    NB: OCR (Tesseract/PaddleOCR) для сканов НЕ реализован в этой версии -- документы
    Алматинского онкоцентра, на которых тестировали, содержат текстовый слой (не сканы),
    поэтому pdfplumber справляется напрямую. Если raw_text окажется пустым -- это сигнал,
    что документ является сканом и нужен OCR-фоллбек (TODO).
    """
    if file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="Ожидается файл в формате PDF")

    file_bytes = await file.read()

    object_key = storage_service.upload_file(file_bytes, file.filename or "document.pdf")

    raw_text = extract_text_from_pdf(file_bytes)

    doc = SourceDocument(
        file_path=object_key,
        original_filename=file.filename or "document.pdf",
        raw_text=raw_text,
    )

    if not raw_text.strip():
        doc.status = DocumentStatus.FAILED
        doc.error_message = (
            "Текстовый слой пуст -- вероятно, это скан. OCR-пайплайн для сканов "
            "в этой версии не реализован (см. TODO в router.py)."
        )
    else:
        doc.status = DocumentStatus.TEXT_EXTRACTED
        # Детерминированные поля -- сразу, не дожидаясь LLM
        doc.extracted_entities = {
            "regex": {
                "iin_candidates": extract_iin_candidates(raw_text),
                "icd10_codes": extract_icd10_codes(raw_text),
                "dates_found_count": len(extract_dates(raw_text)),
            }
        }

    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc


@router.post("/{document_id}/extract", response_model=SourceDocumentOut)
def run_llm_extraction(document_id: uuid.UUID, db: DbSession = Depends(get_db)) -> SourceDocument:
    """
    Шаг 2 пайплайна: LLM-экстракция клинических полей через локальный LM Studio.

    Требует запущенного LM Studio на машине, где выполняется backend
    (см. LLM_BASE_URL в .env). Если LM Studio недоступен -- документ помечается
    NEEDS_REVIEW с понятной ошибкой, врач может ввести поля вручную (fallback).
    """
    doc = db.get(SourceDocument, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Документ не найден")
    if doc.status not in (DocumentStatus.TEXT_EXTRACTED, DocumentStatus.NEEDS_REVIEW):
        raise HTTPException(
            status_code=409,
            detail=f"Документ в статусе '{doc.status}', LLM-экстракция недоступна",
        )

    epicrisis = extract_epicrisis_section(doc.raw_text or "")
    epicrisis_clean = clean_text_for_llm(epicrisis) if epicrisis else None
    fallback_clean = clean_text_for_llm(doc.raw_text or "")

    try:
        llm_result = extract_entities_via_llm(epicrisis_clean, fallback_clean)
    except LLMExtractionError as exc:
        doc.status = DocumentStatus.NEEDS_REVIEW
        doc.error_message = str(exc)
        db.commit()
        db.refresh(doc)
        return doc

    conflict = detect_signal_conflict(
        treatment_modality=llm_result.get("treatment_modality", "unknown"),
        clinical_pathway=llm_result.get("clinical_pathway"),
        urgency_signals=llm_result.get("urgency_signals", {}),
    )

    # Сохраняем regex-результаты, полученные на шаге upload, и добавляем llm-часть
    merged_entities = dict(doc.extracted_entities or {})
    merged_entities["llm"] = llm_result
    doc.extracted_entities = merged_entities
    doc.confidence_scores = llm_result.get("confidence", {})
    doc.conflict_info = conflict
    doc.error_message = None  # очищаем "хвост" от возможной предыдущей неудачной попытки
    doc.status = DocumentStatus.NEEDS_REVIEW if conflict else DocumentStatus.LLM_PROCESSED

    db.commit()
    db.refresh(doc)
    return doc


@router.get("", response_model=list[SourceDocumentOut])
def list_documents(db: DbSession = Depends(get_db)) -> list[SourceDocumentOut]:
    """
    Список всех загруженных документов, новые сверху -- удобно найти id без похода в БД.
    Дополнительно подмешиваем case_id -- по какому документу уже создан case лечения
    (если создан), чтобы в UI было видно, что с документом уже сделано, а не только
    сам факт загрузки.
    """
    docs = list(db.execute(select(SourceDocument).order_by(SourceDocument.created_at.desc())).scalars())
    if not docs:
        return []

    case_by_doc_id = dict(
        db.execute(
            select(TreatmentCase.source_document_id, TreatmentCase.id).where(
                TreatmentCase.source_document_id.in_([d.id for d in docs])
            )
        ).all()
    )
    return [
        SourceDocumentOut.model_validate(doc).model_copy(
            update={"case_id": case_by_doc_id.get(doc.id)}
        )
        for doc in docs
    ]


@router.get("/{document_id}/file")
def get_document_file(document_id: uuid.UUID, db: DbSession = Depends(get_db)) -> Response:
    """Отдаёт бинарный PDF из хранилища -- используется фронтендом для split-screen просмотра."""
    doc = db.get(SourceDocument, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Документ не найден")
    file_bytes = storage_service.download_file(doc.file_path)
    return Response(content=file_bytes, media_type="application/pdf")


@router.get("/{document_id}", response_model=SourceDocumentOut)
def get_document(document_id: uuid.UUID, db: DbSession = Depends(get_db)) -> SourceDocument:
    doc = db.get(SourceDocument, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Документ не найден")
    return doc