"""
Сервис для управления системными промптами.
"""
from typing import List, Dict, Optional
from sqlalchemy.orm import Session
from app.models.system_prompt import SystemPrompt
from app.schemas.system_prompt import PromptCreate, PromptUpdate
from app.utils.constants import DEFAULT_PROMPTS, STRATEGY_PROMPTS
from app.services.token_counter import count_tokens


class PromptService:
    """Сервис для управления системными промптами."""

    @staticmethod
    def get_all(db: Session):
        """Получить все промпты с подсчётом токенов."""
        prompts = db.query(SystemPrompt).order_by(
            SystemPrompt.is_default.desc(),
            SystemPrompt.is_custom.asc(),
            SystemPrompt.name.asc()
        ).all()
        
        result = []
        for p in prompts:
            result.append({
                "id": p.id,
                "name": p.name,
                "content": p.content,
                "reminder": p.reminder,
                "strategy": p.strategy,
                "is_default": p.is_default,
                "is_custom": p.is_custom,
                "is_quick": p.is_quick,
                "created_at": p.created_at,
                "token_count": count_tokens(p.content)
            })
        return result

    @staticmethod
    def get_by_strategy(db: Session, strategy: str) -> Optional[Dict]:
        """Получить системный промпт по стратегии."""
        prompt = db.query(SystemPrompt).filter(
            SystemPrompt.strategy == strategy,
            SystemPrompt.is_custom == False
        ).first()
        
        if not prompt:
            return None
        
        return {
            "id": prompt.id,
            "name": prompt.name,
            "content": prompt.content,
            "reminder": prompt.reminder,
            "strategy": prompt.strategy,
            "is_default": prompt.is_default,
            "is_custom": prompt.is_custom,
            "is_quick": prompt.is_quick,
            "created_at": prompt.created_at,
            "token_count": count_tokens(prompt.content)
        }

    @staticmethod
    def get_strategy_prompt(db: Session, strategy: str) -> str:
        """Получить только текст промпта по стратегии."""
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
    def get_all_strategies(db: Session) -> List[Dict]:
        """Получить все системные промпты для стратегий."""
        prompts = db.query(SystemPrompt).filter(
            SystemPrompt.is_custom == False
        ).all()
        
        return [
            {
                "id": p.id,
                "name": p.name,
                "strategy": p.strategy,
                "content": p.content,
                "reminder": p.reminder,
                "is_default": p.is_default
            }
            for p in prompts
        ]

    @staticmethod
    def get_quick(db: Session):
        """Получить промпты для быстрого выбора с подсчётом токенов."""
        prompts = db.query(SystemPrompt).filter(
            SystemPrompt.is_quick == True
        ).order_by(SystemPrompt.is_default.desc()).all()
        
        result = []
        for p in prompts:
            result.append({
                "id": p.id,
                "name": p.name,
                "content": p.content,
                "reminder": p.reminder,
                "strategy": p.strategy,
                "is_default": p.is_default,
                "is_custom": p.is_custom,
                "is_quick": p.is_quick,
                "created_at": p.created_at,
                "token_count": count_tokens(p.content)
            })
        return result

    @staticmethod
    def create(db: Session, data: PromptCreate):
        """Создать пользовательский промпт."""
        prompt = SystemPrompt(
            name=data.name,
            content=data.content,
            reminder=data.reminder,
            strategy=data.strategy or "flexible",
            is_default=False,
            is_custom=True,
            is_quick=data.is_quick
        )
        db.add(prompt)
        db.commit()
        db.refresh(prompt)
        
        return {
            "id": prompt.id,
            "name": prompt.name,
            "content": prompt.content,
            "reminder": prompt.reminder,
            "strategy": prompt.strategy,
            "is_default": prompt.is_default,
            "is_custom": prompt.is_custom,
            "is_quick": prompt.is_quick,
            "created_at": prompt.created_at,
            "token_count": count_tokens(prompt.content)
        }

    @staticmethod
    def update(db: Session, prompt_id: int, data: PromptUpdate):
        """Обновить пользовательский промпт."""
        prompt = db.query(SystemPrompt).filter(SystemPrompt.id == prompt_id).first()
        if not prompt:
            raise ValueError(f"Промпт {prompt_id} не найден")

        if not prompt.is_custom:
            raise ValueError("Нельзя редактировать предустановленный промпт")

        if data.name is not None:
            prompt.name = data.name
        if data.content is not None:
            prompt.content = data.content
        if data.reminder is not None:
            prompt.reminder = data.reminder
        if data.strategy is not None:
            prompt.strategy = data.strategy
        if data.is_quick is not None:
            prompt.is_quick = data.is_quick

        db.commit()
        db.refresh(prompt)
        
        return {
            "id": prompt.id,
            "name": prompt.name,
            "content": prompt.content,
            "reminder": prompt.reminder,
            "strategy": prompt.strategy,
            "is_default": prompt.is_default,
            "is_custom": prompt.is_custom,
            "is_quick": prompt.is_quick,
            "created_at": prompt.created_at,
            "token_count": count_tokens(prompt.content)
        }

    @staticmethod
    def delete(db: Session, prompt_id: int):
        """Удалить пользовательский промпт."""
        prompt = db.query(SystemPrompt).filter(SystemPrompt.id == prompt_id).first()
        if not prompt:
            return

        if not prompt.is_custom:
            raise ValueError("Нельзя удалять предустановленный промпт")

        db.delete(prompt)
        db.commit()

    @staticmethod
    def seed_defaults(db: Session):
        """
        Добавляет предустановленные промпты в базу.
        Вызывается при инициализации.
        """
        # Добавляем стратегические промпты
        for prompt_data in STRATEGY_PROMPTS:
            existing = db.query(SystemPrompt).filter(
                SystemPrompt.strategy == prompt_data["strategy"],
                SystemPrompt.is_custom == False
            ).first()

            if not existing:
                prompt = SystemPrompt(
                    name=prompt_data["name"],
                    content=prompt_data["content"],
                    reminder=prompt_data.get("reminder"),
                    strategy=prompt_data["strategy"],
                    is_default=prompt_data.get("is_default", False),
                    is_custom=False,
                    is_quick=prompt_data.get("is_quick", False)
                )
                db.add(prompt)

        # Добавляем обычные промпты
        for prompt_data in DEFAULT_PROMPTS:
            existing = db.query(SystemPrompt).filter(
                SystemPrompt.name == prompt_data["name"],
                SystemPrompt.is_custom == False
            ).first()

            if not existing:
                prompt = SystemPrompt(
                    name=prompt_data["name"],
                    content=prompt_data["content"],
                    reminder=prompt_data.get("reminder"),
                    strategy="flexible",
                    is_default=prompt_data.get("is_default", False),
                    is_custom=False,
                    is_quick=prompt_data.get("is_quick", False)
                )
                db.add(prompt)

        db.commit()
