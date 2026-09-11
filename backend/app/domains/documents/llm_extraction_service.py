import json

import httpx

from app.core.config import settings
from app.domains.documents.extraction_schema import (
    EXTRACTION_JSON_SCHEMA,
    SYSTEM_PROMPT,
    build_user_prompt,
)


class LLMExtractionError(Exception):
    pass


def extract_entities_via_llm(epicrisis_text: str | None, full_text_fallback: str) -> dict:
    """
    Вызывает LLM через любой OpenAI-совместимый эндпоинт /v1/chat/completions
    со structured output через response_format -- по умолчанию локальный
    LM Studio, но settings.llm_base_url/llm_api_key можно направить на
    облачного провайдера (напр. Groq) без изменений этой функции, см. .env.

    Локальный LM Studio не проверяется в CI/песочнице разработчика, так как
    требует реально запущенного процесса с загруженной моделью на машине,
    где выполняется backend. Логика построения промпта и парсинга ответа
    протестирована отдельно на синтетических данных.
    """
    user_prompt = build_user_prompt(epicrisis_text, full_text_fallback)

    payload = {
        "model": settings.llm_model_name,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        "response_format": EXTRACTION_JSON_SCHEMA,
        "temperature": 0.1,  # низкая температура -- извлечение фактов, не творчество
    }
    headers = {"Authorization": f"Bearer {settings.llm_api_key}"} if settings.llm_api_key else {}

    try:
        response = httpx.post(
            f"{settings.llm_base_url}/chat/completions",
            json=payload,
            headers=headers,
            timeout=settings.llm_timeout_seconds,
        )
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        # Важно: тело ответа обычно содержит точную причину отказа
        # (например, провайдер не смог скомпилировать json_schema в grammar
        # для конкретной модели, либо модель не поддерживает structured output) --
        # это критично для диагностики.
        raise LLMExtractionError(
            f"LLM-провайдер вернул ошибку {exc.response.status_code} по адресу "
            f"{settings.llm_base_url}. Тело ответа: {exc.response.text}"
        ) from exc
    except httpx.HTTPError as exc:
        raise LLMExtractionError(
            f"Не удалось получить ответ от LLM-провайдера по адресу {settings.llm_base_url}. "
            f"Убедитесь, что сервер запущен (LM Studio) или ключ/URL облачного провайдера верны, "
            f"и модель '{settings.llm_model_name}' доступна. Исходная ошибка: {exc}"
        ) from exc

    data = response.json()
    try:
        content = data["choices"][0]["message"]["content"]
        return json.loads(content)
    except (KeyError, IndexError, json.JSONDecodeError) as exc:
        raise LLMExtractionError(
            f"Ответ LLM не соответствует ожидаемому формату: {exc}. Сырой ответ: {data}"
        ) from exc
