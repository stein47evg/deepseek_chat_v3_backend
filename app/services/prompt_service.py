"""
Сервис для управления системными промптами.
"""
from sqlalchemy.orm import Session
from app.models.system_prompt import SystemPrompt
from app.schemas.system_prompt import PromptCreate, PromptUpdate
from app.utils.constants import DEFAULT_PROMPTS


class PromptService:
    """Сервис для управления системными промптами."""

    @staticmethod
    def get_all(db: Session):
        """Получить все промпты."""
        return db.query(SystemPrompt).order_by(
            SystemPrompt.is_default.desc(),
            SystemPrompt.name.asc()
        ).all()

    @staticmethod
    def get_quick(db: Session):
        """Получить промпты для быстрого выбора."""
        return db.query(SystemPrompt).filter(
            SystemPrompt.is_quick == True
        ).order_by(SystemPrompt.is_default.desc()).all()

    @staticmethod
    def create(db: Session, data: PromptCreate):
        """Создать пользовательский промпт."""
        prompt = SystemPrompt(
            name=data.name,
            content=data.content,
            is_default=False,
            is_custom=True,
            is_quick=data.is_quick
        )
        db.add(prompt)
        db.commit()
        db.refresh(prompt)
        return prompt

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
        if data.is_quick is not None:
            prompt.is_quick = data.is_quick

        db.commit()
        db.refresh(prompt)
        return prompt

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
        for prompt_data in DEFAULT_PROMPTS:
            existing = db.query(SystemPrompt).filter(
                SystemPrompt.name == prompt_data["name"]
            ).first()

            if not existing:
                prompt = SystemPrompt(
                    name=prompt_data["name"],
                    content=prompt_data["content"],
                    is_default=prompt_data["is_default"],
                    is_custom=False,
                    is_quick=prompt_data["is_quick"]
                )
                db.add(prompt)

        db.commit()
