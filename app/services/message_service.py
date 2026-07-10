"""
Сервис для работы с сообщениями.
"""
import os
import logging
from sqlalchemy.orm import Session, joinedload
from fastapi import HTTPException
from app.models.message import Message
from app.models.file_version import FileVersion
from app.models.project import Project
from app.models.chat import Chat
from app.services.snapshot_service import SnapshotService
from app.utils.file_utils import safe_join
from app.schemas.message import ApplyFilesResponse, ApplyFileResult

logger = logging.getLogger(__name__)


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
    def apply_files(db: Session, message_id: int) -> ApplyFilesResponse:
        """
        Применить все файлы из сообщения на диск.
        """
        # 1. Находим сообщение
        message = db.query(Message).filter(Message.id == message_id).first()
        if not message:
            raise HTTPException(status_code=404, detail=f"Сообщение {message_id} не найдено")

        # 2. Получаем файлы сообщения
        files = db.query(FileVersion).filter(
            FileVersion.message_id == message_id
        ).all()

        if not files:
            raise HTTPException(
                status_code=404,
                detail=f"Нет файлов для применения в сообщении {message_id}"
            )

        # 3. Находим чат и проект
        chat = db.query(Chat).filter(Chat.id == message.chat_id).first()
        if not chat:
            raise HTTPException(status_code=404, detail=f"Чат {message.chat_id} не найден")

        project = db.query(Project).filter(Project.id == chat.project_id).first()
        if not project:
            raise HTTPException(status_code=404, detail=f"Проект {chat.project_id} не найден")

        if not os.path.exists(project.folder_path):
            raise HTTPException(
                status_code=404,
                detail=f"Папка проекта {project.folder_path} не существует"
            )

        # 4. Применяем каждый файл
        applied_files = []
        failed_files = []
        manifest = {}

        for version in files:
            try:
                # Записываем на диск
                full_path = safe_join(project.folder_path, version.filename)
                os.makedirs(os.path.dirname(full_path), exist_ok=True)
                with open(full_path, "w", encoding="utf-8") as f:
                    f.write(version.content)

                # Обновляем статус
                db.query(FileVersion).filter(
                    FileVersion.chat_id == chat.id,
                    FileVersion.filename == version.filename
                ).update({"is_current": False})

                version.is_current = True
                version.applied = True
                manifest[version.filename] = version.content_hash
                
                applied_files.append({
                    "filename": version.filename,
                    "status": "success"
                })
                
                logger.info(f"Файл применён: {version.filename} (ID: {version.id})")

            except Exception as e:
                error_msg = str(e)
                failed_files.append({
                    "filename": version.filename,
                    "status": "failed",
                    "error": error_msg
                })
                logger.error(f"Ошибка применения файла {version.filename}: {error_msg}")

        # 5. Создаём снимок состояния
        snapshot_id = None
        if applied_files:
            try:
                snapshot = SnapshotService.create(
                    db=db,
                    project_id=project.id,
                    snapshot_type="apply",
                    level=2,
                    name=f"Применены файлы из сообщения #{message_id}",
                    files_manifest=manifest
                )
                snapshot_id = snapshot.id
                logger.info(f"Создан снимок {snapshot_id} для сообщения {message_id}")
            except Exception as e:
                logger.error(f"Ошибка создания снимка: {e}")

        # 6. Сохраняем изменения
        db.commit()

        # 7. Формируем ответ
        return ApplyFilesResponse(
            status="completed" if applied_files and not failed_files else "partial",
            message_id=message_id,
            files_applied=len(applied_files),
            files_failed=len(failed_files),
            snapshot_id=snapshot_id,
            files=applied_files + failed_files
        )

    @staticmethod
    def delete(db: Session, message_id: int):
        """Удалить сообщение (каскадно удаляются файлы)."""
        message = db.query(Message).filter(Message.id == message_id).first()
        if message:
            db.delete(message)
            db.commit()
