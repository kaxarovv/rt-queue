import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core import model_registry  # noqa: F401 -- регистрирует все ORM-модели при старте
from app.domains.documents.router import router as documents_router
from app.domains.documents.storage_service import storage_service
from app.domains.patients.router import router as patients_router
from app.domains.scheduling.router import router as scheduling_router
from app.domains.treatment_cases.router import router as cases_router

logger = logging.getLogger("rtq")

app = FastAPI(
    title="RT Queue Management API",
    description="Платформа умного управления очередями на лучевую терапию",
    version="0.1.0",
)

# Для демо разрешаем всё; в проде -- явный allowlist origin'ов фронтенда.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(patients_router)
app.include_router(documents_router)
app.include_router(cases_router)
app.include_router(scheduling_router)


@app.on_event("startup")
def on_startup() -> None:
    # Гарантируем, что bucket для загруженных PDF существует. Если MinIO
    # временно недоступен (контейнер не поднят, сеть барахлит) -- не роняем
    # весь сервер: остальные эндпоинты (patients, cases, scheduling) от этого
    # не зависят и должны продолжать работать. Ошибка проявится позже,
    # конкретно на upload -- так проще диагностировать, что именно не так.
    try:
        storage_service.ensure_bucket()
    except Exception as exc:
        logger.warning(
            "Не удалось подключиться к объектному хранилищу (MinIO) при старте: %s. "
            "Эндпоинты /api/documents/upload будут недоступны, пока MinIO не поднимется. "
            "Проверьте: docker compose ps",
            exc,
        )


@app.get("/api/health")
def health_check() -> dict:
    return {"status": "ok"}