"""
Эндпоинты для управления чатами.
"""
import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from app.core.database import get_db
from app.models.chat import Chat
from app.schemas.chat import ChatCreate, ChatResponse, ChatUpdate
from app.services.chat_service import ChatService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/chats", tags=["chats"])


@router.get("/", response_model=List[ChatResponse])
def get_chats(project_id: int, db: Session = Depends(get_db)):
    """Получить список чатов в проекте."""
    return ChatService.get_by_project(db, project_id)


@router.post("/", response_model=ChatResponse, status_code=status.HTTP_201_CREATED)
def create_chat(data: ChatCreate, db: Session = Depends(get_db)):
    """Создать новый чат в проекте."""
    return ChatService.create(db, data)


@router.put("/{chat_id}", response_model=ChatResponse)
def update_chat(chat_id: int, data: ChatUpdate, db: Session = Depends(get_db)):
    """Обновить чат."""
    chat = db.query(Chat).filter(Chat.id == chat_id).first()
    if not chat:
        raise HTTPException(status_code=404, detail=f"Чат {chat_id} не найден")
    
    if data.title is not None:
        chat.title = data.title
    
    db.commit()
    db.refresh(chat)
    return chat


@router.get("/{chat_id}", response_model=ChatResponse)
def get_chat_by_id(chat_id: int, db: Session = Depends(get_db)):
    """Получить чат по ID."""
    chat = db.query(Chat).filter(Chat.id == chat_id).first()
    if not chat:
        raise HTTPException(status_code=404, detail=f"Чат {chat_id} не найден")
    return chat


@router.delete("/{chat_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_chat(chat_id: int, db: Session = Depends(get_db)):
    """Удалить чат."""
    ChatService.delete(db, chat_id)
