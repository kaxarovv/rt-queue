import io
import re

import pdfplumber

# Заголовки секций, которые встречаются в реальных медкартах формы №001/у.
# Порядок важен: эпикриз содержит финальные, уже проверенные врачом данные
# и должен иметь приоритет над черновыми промежуточными записями.
EPICRISIS_MARKERS = [
    "Выписной эпикриз",
    "ВЫПИСНОЙЭПИКРИЗ",
    "ВЫПИСНОЙ ЭПИКРИЗ",
]


def extract_text_from_pdf(file_bytes: bytes) -> str:
    """
    Извлекает текст из PDF. Работает для PDF с текстовым слоем
    (какие и присылает мед. учреждение из своей МИС) без OCR.
    Если текстовый слой пуст (скан) -- вернёт пустую строку,
    и вызывающий код должен будет откатиться на OCR-пайплайн
    (Tesseract/PaddleOCR), см. TODO в documents/router.py.
    """
    text_parts: list[str] = []
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text() or ""
            text_parts.append(page_text)
    return "\n".join(text_parts)


def extract_epicrisis_section(full_text: str) -> str | None:
    """
    Пытается вырезать секцию "Выписной эпикриз" из полного текста документа.
    Именно она содержит консолидированный, проверенный врачом финальный
    диагноз и план лечения -- в отличие от черновых дневниковых записей,
    которые могут содержать промежуточные/предварительные формулировки.

    Возвращает None, если секция не найдена -- тогда LLM-промпт будет
    работать с полным текстом документа, но явно предупреждён об этом.
    """
    for marker in EPICRISIS_MARKERS:
        idx = full_text.find(marker)
        if idx != -1:
            # Берём от начала секции до конца документа (эпикриз обычно в конце)
            return full_text[idx:]
    return None


def clean_text_for_llm(text: str, max_chars: int = 12000) -> str:
    """
    Лёгкая нормализация текста перед отправкой в LLM:
    - схлопывает повторяющиеся пробелы/переносы (частый артефакт pdfplumber
      на многоколоночных формах вроде температурных листов)
    - обрезает до разумной длины, чтобы не упереться в контекст модели
      на длинных картах с множеством дневниковых записей
    """
    normalized = re.sub(r"[ \t]+", " ", text)
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)
    return normalized[:max_chars]
