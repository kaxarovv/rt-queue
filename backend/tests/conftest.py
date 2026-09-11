import pytest

from app.core import model_registry  # noqa: F401 -- регистрирует все ORM-модели
from app.core.database import SessionLocal, engine


@pytest.fixture
def db():
    """
    Сессия БД, обёрнутая в транзакцию с rollback после теста -- изменения
    никогда не попадают в реальную dev-БД из docker-compose. Отдельную
    тестовую БД не поднимаем, тесты идут против того же Postgres, что и
    обычный запуск (см. README).
    """
    connection = engine.connect()
    transaction = connection.begin()
    session = SessionLocal(bind=connection)
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()
