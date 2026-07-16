"""
Главный эндпоинт для генерации кода.
"""
import json
import asyncio
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.config import settings
from app.schemas.generate import GenerateRequest
from app.services.generate_service import GenerateService
from app.services.generation_manager import generation_manager
from app.models.chat import Chat

router = APIRouter(tags=["generate"])


@router.post("/chats/{chat_id}/generate")
async def generate(
    chat_id: int,
    request: GenerateRequest,
    db: Session = Depends(get_db)
):
    # Генерация кода с использованием DeepSeek
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

    # Создаём задачу и оборачиваем генератор
    async def generate_with_cleanup():
        task_id = None
        try:
            async for chunk in service.generate_stream(
                request, 
                max_tokens=max_tokens, 
                use_stream=use_stream
            ):
                # Если это первое событие с task_id, регистрируем задачу
                if not task_id:
                    try:
                        data = json.loads(chunk.replace("data: ", "").strip())
                        if data.get("task_id"):
                            task_id = data["task_id"]
                    except:
                        pass
                
                yield chunk
                
        except asyncio.CancelledError:
            # Задача отменена пользователем
            if task_id:
                generation_manager.remove_task(task_id)
            # Отправляем финальное событие об отмене
            yield f"data: {json.dumps({'status': 'cancelled', 'done': True})}\n\n"
        except Exception as e:
            if task_id:
                generation_manager.remove_task(task_id)
            raise
        finally:
            if task_id:
                generation_manager.remove_task(task_id)
            # Гарантируем завершение стрима
            yield f"data: {json.dumps({'done': True})}\n\n"
    
    # Создаём потоковый ответ
    return StreamingResponse(
        generate_with_cleanup(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )
