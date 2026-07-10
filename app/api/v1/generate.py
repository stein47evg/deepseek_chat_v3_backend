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
    chat = db.query(Chat).filter(Chat.id == chat_id).first()
    if not chat:
        raise HTTPException(status_code=404, detail=f"Чат {chat_id} не найден")

    if not settings.DEEPSEEK_API_KEY:
        raise HTTPException(
            status_code=500,
            detail="DEEPSEEK_API_KEY не настроен"
        )

    service = GenerateService(db, chat_id=chat.id, project_id=chat.project_id)

    max_tokens = getattr(request, 'max_tokens', settings.DEFAULT_MAX_TOKENS)
    use_stream = getattr(request, 'use_stream', True)

    return StreamingResponse(
        service.generate_stream(request, max_tokens=max_tokens, use_stream=use_stream),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )
