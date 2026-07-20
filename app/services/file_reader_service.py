"""
Сервис для чтения файлов.
"""
from sqlalchemy.orm import Session
from fastapi import HTTPException
from app.models.chat import Chat
from app.models.file_version import FileVersion
from typing import List


class FileReaderService:
    """Сервис для чтения файлов из БД."""

    @staticmethod
    def get_by_chat(db: Session, chat_id: int) -> List[FileVersion]:
        """Получить все файлы чата."""
        return db.query(FileVersion).filter(
            FileVersion.chat_id == chat_id
        ).order_by(FileVersion.filename, FileVersion.created_at.desc()).all()

    @staticmethod
    def get_by_project(db: Session, project_id: int) -> List[FileVersion]:
        """Получить все текущие версии файлов проекта."""
        return db.query(FileVersion).join(
            Chat, FileVersion.chat_id == Chat.id
        ).filter(
            Chat.project_id == project_id,
            FileVersion.is_current == True
        ).order_by(FileVersion.filename.asc()).all()

    @staticmethod
    def get_by_id(db: Session, file_id: int) -> FileVersion:
        """Получить версию файла по ID."""
        version = db.query(FileVersion).filter(FileVersion.id == file_id).first()
        if not version:
            raise HTTPException(status_code=404, detail="Файл не найден")
        return version
