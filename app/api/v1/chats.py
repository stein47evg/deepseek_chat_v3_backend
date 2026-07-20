"""
Эндпоинты для управления чатами.
"""
import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from app.core.database import get_db
from app.schemas.chat import ChatCreate, ChatResponse, ChatUpdate, StrategyUpdate
from app.services.chat_service import ChatService
from app.services.strategy_service import StrategyService

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
    return ChatService.update(db, chat_id, data.title)


@router.get("/{chat_id}", response_model=ChatResponse)
def get_chat_by_id(chat_id: int, db: Session = Depends(get_db)):
    """Получить чат по ID."""
    return ChatService.get_by_id(db, chat_id)


@router.delete("/{chat_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_chat(chat_id: int, db: Session = Depends(get_db)):
    """Удалить чат."""
    ChatService.delete(db, chat_id)


@router.put("/{chat_id}/strategy")
def set_chat_strategy(chat_id: int, data: StrategyUpdate, db: Session = Depends(get_db)):
    """Установить стратегию генерации для чата."""
    return StrategyService.set_chat_strategy(db, chat_id, data.strategy)


@router.get("/{chat_id}/strategy")
def get_chat_strategy(chat_id: int, db: Session = Depends(get_db)):
    """Получить стратегию генерации чата."""
    return StrategyService.get_chat_strategy(db, chat_id)
