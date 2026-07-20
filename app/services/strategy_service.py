"""
Сервис для управления стратегиями генерации.
"""
from typing import Dict, List, Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException
from app.models.chat import Chat


class StrategyService:
    """Сервис для работы со стратегиями генерации."""

    STRATEGIES = ["full_history", "no_history", "flexible"]

    @staticmethod
    def get_chat_strategy(db: Session, chat_id: int) -> dict:
        """Получает стратегию чата."""
        chat = db.query(Chat).filter(Chat.id == chat_id).first()
        if not chat:
            raise HTTPException(
                status_code=404,
                detail=f"Чат {chat_id} не найден"
            )
        return {
            "chat_id": chat.id,
            "generation_strategy": chat.generation_strategy
        }

    @staticmethod
    def set_chat_strategy(db: Session, chat_id: int, strategy: str) -> dict:
        """Устанавливает стратегию чата."""
        if strategy not in StrategyService.STRATEGIES:
            raise HTTPException(
                status_code=400,
                detail=f"Неизвестная стратегия: {strategy}"
            )

        chat = db.query(Chat).filter(Chat.id == chat_id).first()
        if not chat:
            raise HTTPException(
                status_code=404,
                detail=f"Чат {chat_id} не найден"
            )

        chat.generation_strategy = strategy
        db.commit()
        db.refresh(chat)
        
        return {
            "chat_id": chat.id,
            "generation_strategy": chat.generation_strategy,
            "message": f"Стратегия изменена на '{strategy}'"
        }
