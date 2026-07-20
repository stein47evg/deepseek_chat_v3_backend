"""
Сервис для синхронизации диска и базы данных.
"""
import os
import logging
from fastapi import HTTPException
from sqlalchemy.orm import Session
from app.models.project import Project
from app.models.chat import Chat
from app.models.file_version import FileVersion
from app.utils.file_utils import scan_directory, safe_join
from app.utils.hash_utils import compute_hash
from app.services.snapshot_service import SnapshotService

logger = logging.getLogger(__name__)


class SyncService:
    """Сервис для синхронизации диск ↔ база."""

    @staticmethod
    def explicit_sync(db: Session, project_id: int) -> dict:
        """
        Явная синхронизация: сканирует всю папку проекта и обновляет БД.
        """
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise HTTPException(status_code=404, detail=f"Проект {project_id} не найден")

        chat = db.query(Chat).filter(Chat.project_id == project_id).first()
        if not chat:
            raise HTTPException(status_code=404, detail=f"У проекта {project_id} нет чатов")

        if not os.path.exists(project.folder_path):
            raise HTTPException(status_code=404, detail=f"Папка {project.folder_path} не существует")

        # Сканируем диск
        files = scan_directory(project.folder_path)
        changes = []

        for filename, content in files:
            content_hash = compute_hash(content)

            # Проверяем, есть ли уже такая версия
            existing = db.query(FileVersion).filter(
                FileVersion.chat_id == chat.id,
                FileVersion.filename == filename,
                FileVersion.content_hash == content_hash
            ).first()

            if existing:
                existing.is_current = True
                existing.applied = True
                changes.append({"filepath": filename, "action": "updated"})
            else:
                version = FileVersion(
                    chat_id=chat.id,
                    filename=filename,
                    content=content,
                    content_hash=content_hash,
                    file_type="synced",
                    is_current=True,
                    applied=True
                )
                db.add(version)
                changes.append({"filepath": filename, "action": "created"})

        # ✅ Создаём снимок текущего состояния (манифест собирается автоматически)
        snapshot = SnapshotService.create(
            db=db,
            project_id=project_id,
            snapshot_type="sync",
            level=2,
            name="Синхронизация",
            make_current=True
        )

        return {
            "changes": changes,
            "snapshot_id": snapshot.id
        }

    @staticmethod
    def quiet_sync(db: Session, project_id: int) -> dict:
        """
        Тихая синхронизация: проверяет текущие файлы на изменения/удаления.
        """
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise HTTPException(status_code=404, detail=f"Проект {project_id} не найден")

        chat = db.query(Chat).filter(Chat.project_id == project_id).first()
        if not chat:
            raise HTTPException(status_code=404, detail=f"У проекта {project_id} нет чатов")

        if not os.path.exists(project.folder_path):
            raise HTTPException(status_code=404, detail=f"Папка {project.folder_path} не существует")

        # Получаем все текущие версии
        current_versions = db.query(FileVersion).filter(
            FileVersion.chat_id == chat.id,
            FileVersion.is_current == True
        ).all()

        changes = []

        for version in current_versions:
            full_path = safe_join(project.folder_path, version.filename)

            if not os.path.exists(full_path):
                version.is_current = False
                version.applied = False
                changes.append({"filepath": version.filename, "action": "deleted"})
            else:
                with open(full_path, "r", encoding="utf-8") as f:
                    content = f.read()

                new_hash = compute_hash(content)

                if version.content_hash != new_hash:
                    new_version = FileVersion(
                        chat_id=chat.id,
                        filename=version.filename,
                        content=content,
                        content_hash=new_hash,
                        file_type="synced",
                        is_current=True,
                        applied=True
                    )
                    db.add(new_version)
                    version.is_current = False
                    changes.append({"filepath": version.filename, "action": "modified"})

        # ✅ Если есть изменения, создаём снимок текущего состояния
        snapshot_id = None
        if changes:
            snapshot = SnapshotService.create(
                db=db,
                project_id=project_id,
                snapshot_type="sync",
                level=2,
                name="Тихая синхронизация",
                make_current=True
            )
            snapshot_id = snapshot.id

        return {
            "changes": changes,
            "snapshot_id": snapshot_id
        }
