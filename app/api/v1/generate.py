"""
Главный эндпоинт для генерации кода.
"""
import json
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.config import settings
from app.schemas.generate import GenerateRequest
from app.services.generate_service import GenerateService
from app.models.chat import Chat

router = APIRouter(tags=["generate"])


@router.post("/chats/{chat_id}/generate")
async def generate(
    chat_id: int,
    request: GenerateRequest,
    db: Session = Depends(get_db)
):
    """
    Генерация кода с использованием DeepSeek.
    
    Возвращает SSE стрим с событиями:
    - data: {"content": "текст", "done": false}
    - data: {"file": {"filename": "...", "content": "..."}}
    - data: {"done": true, "message_id": 123}
    """
    # Проверяем существование чата
    chat = db.query(Chat).filter(Chat.id == chat_id).first()
    if not chat:
        raise HTTPException(status_code=404, detail=f"Чат {chat_id} не найден")

    # Проверяем наличие API ключа
    if not settings.DEEPSEEK_API_KEY:
        raise HTTPException(
            status_code=500,
            detail="DEEPSEEK_API_KEY не настроен"
        )

    # Создаём сервис и запускаем генерацию
    service = GenerateService(db, chat)

    return StreamingResponse(
        service.generate_stream(request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )
