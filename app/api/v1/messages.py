"""
Эндпоинты для работы с сообщениями.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from app.core.database import get_db
from app.models.message import Message
from app.models.chat import Chat
from app.schemas.message import MessageResponse
from app.services.message_service import MessageService
from app.services.generate_service import GenerateService
from app.api.dependencies import get_chat
from fastapi.responses import StreamingResponse

router = APIRouter(prefix="/messages", tags=["messages"])


@router.get("/{chat_id}", response_model=List[MessageResponse])
def get_messages(chat_id: int, db: Session = Depends(get_db)):
    """
    Получить историю сообщений чата.
    
    Возвращает все сообщения чата с информацией о полноте.
    Для неполных сообщений доступны поля:
    - is_complete: False
    - partial_content: сырой нераспарсенный ответ
    - context_data: контекст запроса
    """
    return MessageService.get_by_chat(db, chat_id)


@router.get("/{message_id}", response_model=MessageResponse)
def get_message_by_id(message_id: int, db: Session = Depends(get_db)):
    """
    Получить сообщение по ID с его файлами.
    """
    return MessageService.get_with_files(db, message_id)


@router.post("/{message_id}/continue")
async def continue_generation(
    message_id: int,
    db: Session = Depends(get_db)
):
    """
    Продолжить обрезанную генерацию.
    
    Используется когда генерация достигла лимита токенов (8192).
    Восстанавливает контекст из неполного сообщения и продолжает генерацию.
    
    Требования:
    - Сообщение должно существовать
    - Сообщение должно быть неполным (is_complete = False)
    - Сообщение должно иметь context_data с контекстом запроса
    
    Возвращает SSE стрим с продолжением генерации.
    """
    # 1. Находим неполное сообщение
    message = db.query(Message).filter(
        Message.id == message_id,
        Message.is_complete == False
    ).first()
    
    if not message:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Неполное сообщение не найдено"
        )
    
    # 2. Проверяем наличие контекста
    if not message.context_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Контекст для продолжения не найден"
        )
    
    # 3. Получаем чат
    chat = db.query(Chat).filter(Chat.id == message.chat_id).first()
    if not chat:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Чат не найден"
        )
    
    # 4. Восстанавливаем запрос из контекста
    from app.schemas.generate import GenerateRequest
    context_data = message.context_data
    
    continue_request = GenerateRequest(
        query=context_data.get("query", "Продолжи генерацию"),
        selected_files=context_data.get("selected_files", []),
        system_prompt_id=context_data.get("system_prompt_id"),
        model=context_data.get("model", "flash"),
        temperature=context_data.get("temperature", 0.7),
        max_tokens=context_data.get("max_tokens", 8192)
    )
    
    # 5. Создаём сервис и запускаем продолжение
    service = GenerateService(db, chat_id=chat.id, project_id=chat.project_id)
    
    return StreamingResponse(
        service.continue_stream(message_id, continue_request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


@router.delete("/{message_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_message(message_id: int, db: Session = Depends(get_db)):
    """Удалить сообщение."""
    MessageService.delete(db, message_id)
