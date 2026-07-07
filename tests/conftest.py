import os
import sys
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import settings
from app.core.database import Base, get_db
from app.main import app
from app.services.prompt_service import PromptService

# !!! ВАЖНО: ЯВНО импортируем ВСЕ модели, чтобы они зарегистрировались в Base.metadata
from app.models import Project, Chat, Message, FileVersion, Snapshot, SystemPrompt

# Тестовая БД
TEST_DATABASE_URL = f"mysql+pymysql://{settings.DB_USER}:{settings.DB_PASSWORD}@{settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}_test"

engine = create_engine(
    TEST_DATABASE_URL,
    echo=settings.DEBUG,
    pool_pre_ping=True,
    pool_recycle=3600,
)

TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
def db_session():
    # Создаём таблицы
    Base.metadata.create_all(bind=engine)

    db = TestingSessionLocal()
    try:
        PromptService.seed_defaults(db)
        yield db
    finally:
        db.rollback()
        db.close()

    # Удаляем таблицы после теста
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db_session):
    def _get_db_override():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = _get_db_override

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def test_project_data():
    return {"name": "TestProject", "folder_path": "C:/Projects/TestProject"}


@pytest.fixture(scope="function")
def test_chat_data():
    return {"project_id": 1, "title": "Тестовый чат"}
