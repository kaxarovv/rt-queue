import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.shared.enums import DocumentStatus


class SourceDocument(Base):
    """
    Загруженный PDF и результат его обработки на каждом шаге пайплайна:
    Upload -> Text extraction -> LLM extraction -> Doctor review.
    Храним извлечённые сущности прямо здесь (JSONB) до момента,
    пока врач их не подтвердит и не создастся TreatmentCase.
    """

    __tablename__ = "source_documents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    file_path: Mapped[str] = mapped_column(String(500))          # ключ объекта в MinIO
    original_filename: Mapped[str] = mapped_column(String(255))

    status: Mapped[DocumentStatus] = mapped_column(String(20), default=DocumentStatus.PENDING)

    raw_text: Mapped[str | None] = mapped_column(nullable=True)              # текст после pdfplumber
    extracted_entities: Mapped[dict] = mapped_column(JSONB, default=dict)     # результат LLM-экстракции
    confidence_scores: Mapped[dict] = mapped_column(JSONB, default=dict)       # confidence по каждому полю
    conflict_info: Mapped[dict | None] = mapped_column(JSONB, nullable=True)    # detect_signal_conflict()

    error_message: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    reviewed_by_doctor: Mapped[str | None] = mapped_column(String(255), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
