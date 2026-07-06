"""
Точка входа FastAPI приложения.
Настройка маршрутов, CORS, инициализация БД.
Перенесён в корень проекта для упрощения запуска.
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
from app.core.config import settings
from app.core.database import init_db
from app.api.v1 import (
    projects,
    chats,
    messages,
    files,
    generate,
    snapshots,
    sync,
    system_prompts,
    stats
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Обработчик жизненного цикла приложения."""
    # Запуск: инициализация БД
    init_db()
    yield
    # Завершение: закрытие соединений


# Создание FastAPI приложения
app = FastAPI(
    title="DeepSeek Chat API",
    description="API для управления проектами, чатами и генерацией кода",
    version="1.0.0",
    lifespan=lifespan
)

# Настройка CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Подключение роутеров
app.include_router(projects.router, prefix="/api/v1")
app.include_router(chats.router, prefix="/api/v1")
app.include_router(messages.router, prefix="/api/v1")
app.include_router(files.router, prefix="/api/v1")
app.include_router(generate.router, prefix="/api/v1")
app.include_router(snapshots.router, prefix="/api/v1")
app.include_router(sync.router, prefix="/api/v1")
app.include_router(system_prompts.router, prefix="/api/v1")
app.include_router(stats.router, prefix="/api/v1")


@app.get("/")
async def root():
    """Корневой эндпоинт для проверки работы."""
    return {"status": "ok", "message": "DeepSeek Chat API работает"}


@app.get("/health")
async def health():
    """Эндпоинт для проверки здоровья сервиса."""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG
    )
