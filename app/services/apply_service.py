"""
Сервис для применения файлов через единый механизм снимков.
"""

import logging
from sqlalchemy.orm import Session
from fastapi import HTTPException
from app.models.file_version import FileVersion
from app.models.message import Message
from app.models.chat import Chat
from app.models.project import Project
from app.services.snapshot_service import SnapshotService

logger = logging.getLogger(__name__)


class ApplyService:
    """Сервис для применения файлов."""

    @staticmethod
    def apply_file(db: Session, file_id: int) -> dict:
        """
        Применить версию файла на диск.
        Использует единый механизм create_future + restore.
        """
        version = db.query(FileVersion).filter(FileVersion.id == file_id).first()
        if not version:
            raise HTTPException(status_code=404, detail="Версия не найдена")

        chat = db.query(Chat).filter(Chat.id == version.chat_id).first()
        if not chat:
            raise HTTPException(status_code=404, detail="Чат не найден")

        project = db.query(Project).filter(Project.id == chat.project_id).first()
        if not project:
            raise HTTPException(status_code=404, detail="Проект не найден")

        # Создаём снимок будущего состояния
        future = SnapshotService.create_future(
            db=db,
            project_id=project.id,
            snapshot_type="apply",
            level=2,
            name=f"Применена версия {version.filename}",
            new_files={version.filename: version.content_hash},
        )

        # Применяем снимок (записывает на диск)
        SnapshotService.restore(db, future.id)

        return {"status": "applied", "version_id": version.id}

    @staticmethod
    def apply_message_files(db: Session, message_id: int) -> dict:
        """
        Применить все файлы из сообщения.
        Использует единый механизм create_future + restore.
        """
        message = db.query(Message).filter(Message.id == message_id).first()
        if not message:
            raise HTTPException(
                status_code=404, detail=f"Сообщение {message_id} не найдено"
            )

        files = db.query(FileVersion).filter(FileVersion.message_id == message_id).all()

        if not files:
            raise HTTPException(
                status_code=404,
                detail=f"Нет файлов для применения в сообщении {message_id}",
            )

        chat = db.query(Chat).filter(Chat.id == message.chat_id).first()
        if not chat:
            raise HTTPException(
                status_code=404, detail=f"Чат {message.chat_id} не найден"
            )

        project = db.query(Project).filter(Project.id == chat.project_id).first()
        if not project:
            raise HTTPException(
                status_code=404, detail=f"Проект {chat.project_id} не найден"
            )

        # Собираем новые файлы
        new_files = {}
        for version in files:
            if version.file_type in ["uploaded", "synced"]:
                continue
            new_files[version.filename] = version.content_hash

        if not new_files:
            return {"status": "skipped", "message": "Нет файлов для применения"}

        # Создаём снимок будущего состояния
        logger.info(f"Создаем снимок будущего состояния")
        future = SnapshotService.create_future(
            db=db,
            project_id=project.id,
            snapshot_type="apply",
            level=2,
            name=f"Применены файлы из сообщения #{message_id}",
            new_files=new_files,
        )

        logger.info(f"Применяем снимок будущего состояния. Snapshot.id = {future.id}")
        # Применяем снимок (записывает на диск)
        result = SnapshotService.restore(db, future.id, strategy="overwrite")
        logger.info(f"restore() вернул: {result}")
        return {
            "status": "completed",
            "message_id": message_id,
            "snapshot_id": future.id,
            "files_applied": len(new_files),
        }
