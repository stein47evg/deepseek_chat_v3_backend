"""
Эндпоинты для работы с сообщениями.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from app.core.database import get_db
from app.models.message import Message
from app.schemas.message import MessageResponse, ApplyFilesResponse
from app.services.message_service import MessageService
from app.api.dependencies import get_chat

router = APIRouter(prefix="/messages", tags=["messages"])


@router.get("/{chat_id}", response_model=List[MessageResponse])
def get_messages(chat_id: int, db: Session = Depends(get_db)):
    """Получить историю сообщений чата."""
    return MessageService.get_by_chat(db, chat_id)


@router.get("/{message_id}", response_model=MessageResponse)
def get_message_by_id(message_id: int, db: Session = Depends(get_db)):
    """Получить сообщение по ID с его файлами."""
    return MessageService.get_with_files(db, message_id)


@router.post("/{message_id}/apply", response_model=ApplyFilesResponse)
def apply_message_files(message_id: int, db: Session = Depends(get_db)):
    """
    Применить все файлы из сообщения на диск.
    
    - Находит все файлы, связанные с сообщением
    - Записывает их на диск
    - Делает их текущими версиями
    - Создаёт снимок состояния
    """
    return MessageService.apply_files(db, message_id)


@router.delete("/{message_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_message(message_id: int, db: Session = Depends(get_db)):
    """Удалить сообщение."""
    MessageService.delete(db, message_id)
