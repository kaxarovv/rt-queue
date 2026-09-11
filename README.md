# RT Queue — платформа управления очередью на лучевую терапию

Демо-версия backend. Реализовано и протестировано на ваших двух реальных
обезличенных документах:

- Модель БД: `patients`, `treatment_cases`, `machine_slots`, `sessions`, `source_documents`
- CRUD пациентов
- Upload PDF → извлечение текста (pdfplumber) → regex (ИИН с чек-суммой, МКБ-10, даты)
- Приоритизация секции "Выписной эпикриз" над черновыми дневниковыми записями
- JSON-schema + промпт для LLM-экстракции (LM Studio) с разделением
  `treatment_modality` / `clinical_pathway` / `urgency_signals`
- Детекция конфликта сигналов (кейс "SRT ≠ автоматически наивысший приоритет")

**Не реализовано в этой версии** (сознательно отложено для демо, см. чат):
Celery/Redis, OCR для сканов, шифрование ИИН, аутентификация, audit_log,
алгоритм вытеснения, смарт-календарь, frontend.

---

## Что вам нужно установить

- Docker + Docker Compose
- Python 3.11+
- LM Studio с загруженной моделью (рекомендация: Qwen2.5-32B-Instruct, GGUF Q4_K_M)

## Запуск

### 1. Поднять инфраструктуру (Postgres + MinIO)

```bash
docker compose up -d
```

Проверить: `docker compose ps` — оба контейнера должны быть healthy.

### 2. Настроить и запустить backend

```bash
cd backend
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# откройте .env и проверьте LLM_MODEL_NAME — должно совпадать с именем модели,
# которое показывает LM Studio в своём API-логе

alembic upgrade head            # применит схему БД
uvicorn app.main:app --reload --port 8000
```

Проверка: `curl http://localhost:8000/api/health` → `{"status":"ok"}`

Интерактивная документация API (Swagger): http://localhost:8000/docs

### 3. Запустить LM Studio

1. В LM Studio загрузите модель (Qwen2.5-32B-Instruct, квант Q4_K_M или выше)
2. Вкладка "Developer" → "Start Server" (порт по умолчанию 1234)
3. Важно: включите "Structured Output" / JSON-schema grammar в настройках сервера —
   без этого LLM может вернуть невалидный JSON
4. Проверьте, что `LLM_MODEL_NAME` в `.env` совпадает с именем модели в LM Studio

## Проверка на ваших документах

```bash
# 1. Загрузить документ
curl -X POST http://localhost:8000/api/documents/upload \
  -F "file=@/путь/к/вашей/карте.pdf;type=application/pdf"

# Ответ содержит "id" документа и regex-результаты (ИИН, МКБ-10, кол-во дат)

# 2. Запустить LLM-экстракцию (требует запущенного LM Studio)
curl -X POST http://localhost:8000/api/documents/{id}/extract

# Ответ содержит извлечённые клинические поля, confidence, и conflict_info
# (не null, если сработала детекция конфликта SRT/plannned pathway)
```

## Известные упрощения (см. TODO-комментарии в коде)

- `app/domains/scheduling/models.py`: защита от double-booking слотов —
  временный `UNIQUE(slot_date, time_start)` вместо полноценного `EXCLUDE`
  constraint с GIST по диапазону времени. `btree_gist` extension нужно
  включить в Postgres перед доработкой (`CREATE EXTENSION btree_gist;`).
- ИИН хранится в открытом виде в БД — для прода нужен pgcrypto.
- OCR для сканированных PDF не реализован — только PDF с текстовым слоем.

## Структура проекта

```
backend/
├── app/
│   ├── core/           # config, database, model_registry
│   ├── domains/
│   │   ├── patients/     # CRUD пациентов
│   │   ├── documents/     # upload, OCR-заглушка, regex, LLM extraction, conflict detection
│   │   ├── treatment_cases/  # модель клинического случая (приоритизация — следующий шаг)
│   │   └── scheduling/         # модели слотов и сеансов (booking/displacement — следующий шаг)
│   └── shared/
│       └── enums.py       # матрица приоритизации, статусы
├── alembic/              # миграции БД
└── requirements.txt
```
