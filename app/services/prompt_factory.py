"""
Фабрика системных промптов для стратегий генерации.
"""
from typing import Dict, Optional
from sqlalchemy.orm import Session
from app.models.system_prompt import SystemPrompt


class PromptFactory:
    """Фабрика для получения системных промптов по стратегии."""

    @staticmethod
    def get_prompt(db: Session, strategy: str) -> str:
        """Получает системный промпт из БД по стратегии."""
        prompt = db.query(SystemPrompt).filter(
            SystemPrompt.strategy == strategy,
            SystemPrompt.is_custom == False
        ).first()

        if prompt:
            return prompt.content

        # Fallback: промпт по умолчанию
        default = db.query(SystemPrompt).filter(
            SystemPrompt.is_default == True
        ).first()

        return default.content if default else "Ты — полезный ассистент."

    @staticmethod
    def get_prompt_with_reminder(db: Session, strategy: str) -> Dict[str, str]:
        """Получает промпт и напоминание по стратегии."""
        prompt = db.query(SystemPrompt).filter(
            SystemPrompt.strategy == strategy,
            SystemPrompt.is_custom == False
        ).first()

        if prompt:
            return {
                "content": prompt.content,
                "reminder": prompt.reminder
            }

        default = db.query(SystemPrompt).filter(
            SystemPrompt.is_default == True
        ).first()

        return {
            "content": default.content if default else "Ты — полезный ассистент.",
            "reminder": default.reminder if default else None
        }
