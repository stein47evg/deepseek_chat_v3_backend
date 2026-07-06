"""
Сервис для работы с сообщениями.
"""
from sqlalchemy.orm import Session, joinedload
from app.models.message import Message
from app.models.file_version import FileVersion


class MessageService:
    """Сервис для управления сообщениями."""

    @staticmethod
    def get_by_chat(db: Session, chat_id: int):
        """Получить все сообщения чата."""
        return db.query(Message).filter(
            Message.chat_id == chat_id
        ).order_by(Message.created_at.asc()).all()

    @staticmethod
    def get_with_files(db: Session, message_id: int):
        """Получить сообщение с его файлами."""
        return db.query(Message).options(
            joinedload(Message.file_versions)
        ).filter(Message.id == message_id).first()

    @staticmethod
    def delete(db: Session, message_id: int):
        """Удалить сообщение (каскадно удаляются файлы)."""
        message = db.query(Message).filter(Message.id == message_id).first()
        if message:
            db.delete(message)
            db.commit()
