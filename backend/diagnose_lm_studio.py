"""
Диагностика проблем с LM Studio: запустите на машине, где крутится LM Studio.

    python diagnose_lm_studio.py

Проверяет по шагам:
1. Доступен ли сервер вообще (GET /v1/models)
2. Работает ли простой chat completion БЕЗ structured output
3. Работает ли chat completion СО structured output (наша JSON-schema)

Если шаг 2 падает -- проблема не в схеме, а в самом подключении/модели.
Если шаг 2 работает, а шаг 3 падает -- проблема именно в JSON-schema
(вероятно, LM Studio/llama.cpp не поддерживает какую-то часть схемы).
"""

import json
import sys

import httpx

BASE_URL = "http://localhost:1234/v1"
MODEL_NAME = "qwen2.5-7b-instruct-1m"  # поправьте, если используете другую модель


def step1_check_models():
    print("=== Шаг 1: GET /v1/models ===")
    try:
        r = httpx.get(f"{BASE_URL}/models", timeout=10)
        r.raise_for_status()
        models = [m["id"] for m in r.json().get("data", [])]
        print(f"OK. Доступно моделей: {len(models)}")
        if MODEL_NAME not in models:
            print(f"ВНИМАНИЕ: '{MODEL_NAME}' нет в списке! Доступные: {models}")
        return True
    except Exception as exc:
        print(f"ОШИБКА: {exc}")
        return False


def step2_simple_completion():
    print("\n=== Шаг 2: простой chat completion БЕЗ structured output ===")
    payload = {
        "model": MODEL_NAME,
        "messages": [{"role": "user", "content": "Ответь одним словом: сколько будет 2+2?"}],
        "temperature": 0.1,
        "max_tokens": 50,
    }
    try:
        r = httpx.post(f"{BASE_URL}/chat/completions", json=payload, timeout=60)
        print(f"HTTP статус: {r.status_code}")
        print(f"Тело ответа: {r.text[:1000]}")
        r.raise_for_status()
        print("OK. Базовый chat completion работает.")
        return True
    except Exception as exc:
        print(f"ОШИБКА: {exc}")
        return False


def step3_structured_output():
    print("\n=== Шаг 3: chat completion СО structured output (упрощённая схема) ===")
    # Намеренно простая схема без вложенных nullable-полей -- чтобы проверить,
    # держит ли LM Studio structured output вообще, до того как тестировать
    # нашу полную боевую схему.
    simple_schema = {
        "type": "json_schema",
        "json_schema": {
            "name": "simple_test",
            "strict": True,
            "schema": {
                "type": "object",
                "properties": {
                    "answer": {"type": "string"},
                    "number": {"type": "integer"},
                },
                "required": ["answer", "number"],
                "additionalProperties": False,
            },
        },
    }
    payload = {
        "model": MODEL_NAME,
        "messages": [
            {
                "role": "user",
                "content": "Сколько будет 2+2? Ответь в JSON с полями answer (текст) и number (число).",
            }
        ],
        "response_format": simple_schema,
        "temperature": 0.1,
        "max_tokens": 100,
    }
    try:
        r = httpx.post(f"{BASE_URL}/chat/completions", json=payload, timeout=60)
        print(f"HTTP статус: {r.status_code}")
        print(f"Тело ответа: {r.text[:2000]}")
        r.raise_for_status()
        print("OK. Structured output работает с простой схемой.")
        return True
    except Exception as exc:
        print(f"ОШИБКА: {exc}")
        return False


def step4_nullable_field_type_array():
    print("\n=== Шаг 4a: nullable-поле через 'type': ['string', 'null'] ===")
    schema = {
        "type": "json_schema",
        "json_schema": {
            "name": "nullable_test_type_array",
            "strict": True,
            "schema": {
                "type": "object",
                "properties": {
                    "answer": {"type": "string"},
                    "optional_field": {"type": ["string", "null"]},
                },
                "required": ["answer", "optional_field"],
                "additionalProperties": False,
            },
        },
    }
    payload = {
        "model": MODEL_NAME,
        "messages": [{"role": "user", "content": "Ответь: answer='тест', optional_field=null"}],
        "response_format": schema,
        "temperature": 0.1,
        "max_tokens": 100,
    }
    try:
        r = httpx.post(f"{BASE_URL}/chat/completions", json=payload, timeout=60)
        print(f"HTTP статус: {r.status_code}")
        print(f"Тело ответа: {r.text[:1500]}")
        r.raise_for_status()
        print("OK.")
        return True
    except Exception as exc:
        print(f"ОШИБКА: {exc}")
        return False


def step4b_nullable_field_anyof():
    print("\n=== Шаг 4b: то же самое, но через 'anyOf': [{'type': 'string'}, {'type': 'null'}] ===")
    schema = {
        "type": "json_schema",
        "json_schema": {
            "name": "nullable_test_anyof",
            "strict": True,
            "schema": {
                "type": "object",
                "properties": {
                    "answer": {"type": "string"},
                    "optional_field": {"anyOf": [{"type": "string"}, {"type": "null"}]},
                },
                "required": ["answer", "optional_field"],
                "additionalProperties": False,
            },
        },
    }
    payload = {
        "model": MODEL_NAME,
        "messages": [{"role": "user", "content": "Ответь: answer='тест', optional_field=null"}],
        "response_format": schema,
        "temperature": 0.1,
        "max_tokens": 100,
    }
    try:
        r = httpx.post(f"{BASE_URL}/chat/completions", json=payload, timeout=60)
        print(f"HTTP статус: {r.status_code}")
        print(f"Тело ответа: {r.text[:1500]}")
        r.raise_for_status()
        print("OK.")
        return True
    except Exception as exc:
        print(f"ОШИБКА: {exc}")
        return False


def step5_full_schema_short_text():
    print("\n=== Шаг 5: БОЕВАЯ схема extraction_schema.py, но с коротким тестовым текстом ===")
    sys.path.insert(0, ".")
    from app.domains.documents.extraction_schema import EXTRACTION_JSON_SCHEMA, SYSTEM_PROMPT

    short_text = (
        "Выписной эпикриз. Заключительный диагноз: (C70.0) Злокачественное "
        "новообразование оболочек головного мозга. Состояние после операции. "
        "Планируется курс SRT 5 сеансов на область головного мозга, РОД 4,6 Гр, "
        "СОД 23 Гр. ECOG 1. Жалобы на головные боли в течение 15 лет (хронические)."
    )
    payload = {
        "model": MODEL_NAME,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": short_text},
        ],
        "response_format": EXTRACTION_JSON_SCHEMA,
        "temperature": 0.1,
    }
    try:
        r = httpx.post(f"{BASE_URL}/chat/completions", json=payload, timeout=90)
        print(f"HTTP статус: {r.status_code}")
        print(f"Тело ответа: {r.text[:3000]}")
        r.raise_for_status()
        print("OK. Боевая схема работает на коротком тексте!")
        return True
    except Exception as exc:
        print(f"ОШИБКА: {exc}")
        return False


def step6_full_schema_long_text():
    print("\n=== Шаг 6: БОЕВАЯ схема + длинный текст (~12000 символов, как реальный эпикриз) ===")
    sys.path.insert(0, ".")
    from app.domains.documents.extraction_schema import EXTRACTION_JSON_SCHEMA, SYSTEM_PROMPT

    long_text = (
        "Выписной эпикриз. Заключительный диагноз: (C70.0) Злокачественное "
        "новообразование оболочек головного мозга. "
    ) * 200  # ~12000+ символов повторяющегося текста -- имитация длины реального документа
    payload = {
        "model": MODEL_NAME,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": long_text},
        ],
        "response_format": EXTRACTION_JSON_SCHEMA,
        "temperature": 0.1,
    }
    print(f"Длина текста: {len(long_text)} символов")
    try:
        r = httpx.post(f"{BASE_URL}/chat/completions", json=payload, timeout=120)
        print(f"HTTP статус: {r.status_code}")
        print(f"Тело ответа: {r.text[:1500]}")
        r.raise_for_status()
        print("OK.")
        return True
    except Exception as exc:
        print(f"ОШИБКА: {exc}")
        return False


if __name__ == "__main__":
    ok1 = step1_check_models()
    if not ok1:
        print("\nСервер недоступен -- проверьте, что LM Studio запущен и сервер стартован.")
        sys.exit(1)

    ok2 = step2_simple_completion()
    if not ok2:
        print("\nБазовый chat completion не работает -- проблема не в JSON-schema.")
        sys.exit(1)

    ok3 = step3_structured_output()
    if not ok3:
        print(
            "\nБазовый chat работает, но structured output -- нет. "
            "Проблема именно в response_format/JSON-schema."
        )
        sys.exit(1)

    ok4a = step4_nullable_field_type_array()
    ok4b = step4b_nullable_field_anyof()

    ok5 = step5_full_schema_short_text()
    ok6 = None
    if ok5:
        ok6 = step6_full_schema_long_text()

    print("\n=== ИТОГ ===")
    print(f"'type': ['string', 'null']       -> {'OK' if ok4a else 'ОШИБКА'}")
    print(f"'anyOf': [...]                   -> {'OK' if ok4b else 'ОШИБКА'}")
    print(f"Боевая схема, короткий текст     -> {'OK' if ok5 else 'ОШИБКА'}")
    if ok6 is not None:
        print(f"Боевая схема, длинный текст       -> {'OK' if ok6 else 'ОШИБКА'}")

    if not ok5:
        print("\nБоевая схема падает даже на коротком тексте -- проблема в сложности "
              "самой схемы (много enum + вложенные объекты одновременно). Будем упрощать.")
    elif ok5 and ok6 is False:
        print("\nПодтверждено: схема нормальная, проблема в РАЗМЕРЕ КОНТЕКСТА. "
              "Нужно увеличить 'Context Length' для модели в настройках LM Studio "
              "(вкладка Developer -> настройки модели -> Context Length, "
              "поставьте 8192 или больше).")
    elif ok5 and ok6:
        print("\nВсё работает на всех уровнях! Проблема была где-то ещё "
              "(возможно, уже исправлена предыдущими шагами) -- пробуем боевой /extract.")
