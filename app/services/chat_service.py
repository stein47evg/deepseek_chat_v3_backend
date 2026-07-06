"""
Сервис для работы с чатами.
"""
from sqlalchemy.orm import Session
from app.models.chat import Chat
from app.schemas.chat import ChatCreate


class ChatService:
    """Сервис для управления чатами."""

    @staticmethod
    def get_by_project(db: Session, project_id: int):
        """Получить все чаты проекта."""
        return db.query(Chat).filter(
            Chat.project_id == project_id
        ).order_by(Chat.created_at.desc()).all()

    @staticmethod
    def create(db: Session, data: ChatCreate):
        """Создать новый чат."""
        chat = Chat(
            project_id=data.project_id,
            title=data.title or "Новый чат"
        )
        db.add(chat)
        db.commit()
        db.refresh(chat)
        return chat

    @staticmethod
    def delete(db: Session, chat_id: int):
        """Удалить чат."""
        chat = db.query(Chat).filter(Chat.id == chat_id).first()
        if chat:
            db.delete(chat)
            db.commit()
