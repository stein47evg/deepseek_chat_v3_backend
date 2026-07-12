"""
Точка входа FastAPI приложения.
"""
from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import (
    chats,
    files,
    generate,
    messages,
    projects,
    snapshots,
    stats,
    sync,
    system_prompts,
)
from app.core.config import settings
from app.core.database import init_db

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Обработчик жизненного цикла приложения."""
    init_db()
    yield


# Создание FastAPI приложения
app = FastAPI(
    title="DeepSeek Chat API",
    description="API для управления проектами, чатами и генерацией кода",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)


# Глобальный обработчик ошибок
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """
    Превращает все неперехваченные исключения в красивые JSON-ответы.
    """
    logger.error(f"Ошибка: {exc}")

    # Если это HTTPException — FastAPI уже обработает
    # Для всех остальных — возвращаем 500 с деталями
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": str(exc),
            "code": 500,
            "type": exc.__class__.__name__,
            "timestamp": datetime.now().isoformat()
        }
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
        host="127.0.0.1",
        port=8000,
        reload=settings.DEBUG
    )
