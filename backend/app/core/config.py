from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Централизованная конфигурация приложения.
    Все параметры, которые могут меняться между окружениями (dev/staging/prod)
    или которые клиника захочет настраивать сама, идут сюда, а не хардкодятся
    по коду.
    """

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Database
    database_url: str = "postgresql+psycopg://rtq:rtq_dev_password@localhost:5432/rtq_db"

    @field_validator("database_url")
    @classmethod
    def _normalize_database_url(cls, value: str) -> str:
        """
        Хостинги БД (Railway, Render, Heroku и т.п.) обычно выдают DATABASE_URL
        в виде "postgresql://..." или "postgres://..." -- без явного драйвера.
        SQLAlchemy в этом случае попытается взять psycopg2 (не установлен,
        в requirements.txt только psycopg3), и упадёт. Нормализуем схему сюда,
        а не заставляем каждый раз руками править значение при вставке в
        переменные окружения хостинга.
        """
        if value.startswith("postgresql+psycopg://"):
            return value
        if value.startswith("postgres://"):
            return "postgresql+psycopg://" + value[len("postgres://") :]
        if value.startswith("postgresql://"):
            return "postgresql+psycopg://" + value[len("postgresql://") :]
        return value

    # Object storage: любое S3-совместимое хранилище (MinIO локально, Cloudflare
    # R2 в облаке) -- код не меняется, только эти значения. R2 требует region_name
    # "auto"; MinIO region игнорирует, так что дефолт безопасен для обоих.
    s3_endpoint_url: str = "http://localhost:9000"
    s3_access_key: str = "rtq_minio"
    s3_secret_key: str = "rtq_minio_password"
    s3_bucket_name: str = "source-documents"
    s3_region: str = "auto"

    # LLM -- любой OpenAI-совместимый эндпоинт (/v1/chat/completions +
    # response_format с json_schema): по умолчанию локальный LM Studio,
    # но можно переключить на облачного провайдера (напр. Groq) без
    # изменений кода -- просто заменить эти три значения в .env.
    # llm_api_key пустой = заголовок Authorization не отправляется (LM Studio
    # его не требует); для облачного провайдера -- задать реальный ключ.
    llm_base_url: str = "http://localhost:1234/v1"
    llm_model_name: str = "qwen2.5-32b-instruct"
    llm_api_key: str = ""
    llm_timeout_seconds: int = 120

    # Ёмкость аппарата ЛТ — стартовые дефолты.
    # ВАЖНО: в проде это переезжает в таблицу machine_capacity_config,
    # редактируемую через UI, а не в .env. Здесь — только для MVP/демо.
    machine_sessions_per_day: int = 8
    machine_working_days_per_week: int = 5

    # Ёмкость МДГ-очереди: сколько пациентов в календарный месяц отделение
    # может принять на лечение (по дате СТАРТА лечения, а не по дате создания
    # случая). Это отдельный ресурс-пул от machine_sessions_per_day -- тот
    # считает сеансы аппарата в день (уровень "дневного стационара"), этот --
    # людей в месяц (уровень МДГ, где сейчас решается приоритизация).
    # ВАЖНО: в проде -- переезжает в БД-конфиг, редактируемый через UI.
    monthly_patient_capacity: int = 60

    # App
    app_env: str = "development"
    debug: bool = True


settings = Settings()
