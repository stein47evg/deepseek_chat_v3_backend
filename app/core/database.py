from sqlalchemy import create_engine, inspect
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.core.config import settings

Base = declarative_base()

engine = create_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    pool_pre_ping=True,
    pool_recycle=3600,
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    # Проверяем, существуют ли таблицы
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    
    # Если таблиц нет, создаём их
    if not tables:
        Base.metadata.create_all(bind=engine)
    else:
        # Если таблицы есть, проверяем, что все нужные таблицы существуют
        required_tables = ['projects', 'chats', 'messages', 'file_versions', 'snapshots', 'system_prompts']
        missing_tables = [t for t in required_tables if t not in tables]
        if missing_tables:
            # Создаём недостающие таблицы
            Base.metadata.create_all(bind=engine)
