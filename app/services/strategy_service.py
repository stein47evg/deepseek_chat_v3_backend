"""
Сервис для управления стратегиями генерации.
"""
from typing import Dict, List, Optional
from sqlalchemy.orm import Session
from app.models.chat import Chat
from app.models.message import Message
from app.models.file_version import FileVersion
from app.services.prompt_factory import PromptFactory


class StrategyService:
    """Сервис для работы со стратегиями генерации."""

    STRATEGIES = ["full_history", "no_history", "flexible"]

    @staticmethod
    def get_chat_strategy(db: Session, chat_id: int) -> str:
        """Получает стратегию чата."""
        chat = db.query(Chat).filter(Chat.id == chat_id).first()
        return chat.generation_strategy if chat else "flexible"

    @staticmethod
    def set_chat_strategy(db: Session, chat_id: int, strategy: str) -> Chat:
        """Устанавливает стратегию чата."""
        if strategy not in StrategyService.STRATEGIES:
            raise ValueError(f"Неизвестная стратегия: {strategy}. Доступны: {', '.join(StrategyService.STRATEGIES)}")

        chat = db.query(Chat).filter(Chat.id == chat_id).first()
        if not chat:
            raise ValueError(f"Чат {chat_id} не найден")

        chat.generation_strategy = strategy
        db.commit()
        db.refresh(chat)
        return chat

    @staticmethod
    def get_strategy_prompt(db: Session, strategy: str) -> str:
        """Получает системный промпт для стратегии."""
        return PromptFactory.get_prompt(db, strategy)

    @staticmethod
    def get_available_strategies(db: Session) -> List[Dict]:
        """Возвращает список доступных стратегий с их промптами."""
        result = []
        for strategy in StrategyService.STRATEGIES:
            prompt = PromptFactory.get_prompt(db, strategy)
            result.append({
                "name": strategy,
                "prompt": prompt
            })
        return result

    @staticmethod
    def should_reset_context(request_strategy: str, has_selected_files: bool) -> bool:
        """
        Определяет, нужно ли сбрасывать контекст для гибкой стратегии.
        """
        if request_strategy == "no_history":
            return True
        if request_strategy == "full_history":
            return False
        # flexible: сброс если есть приложенные файлы
        return has_selected_files
