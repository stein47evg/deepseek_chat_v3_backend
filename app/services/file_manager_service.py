"""
Сервис для файлового менеджера.
"""

import hashlib
import logging
import os
from typing import Any

from sqlalchemy.orm import Session

from app.models.chat import Chat
from app.models.file_version import FileVersion
from app.models.project import Project
from app.models.snapshot import Snapshot
from app.services.snapshot_service import SnapshotService
from app.utils.file_utils import (
    is_allowed_file,
    safe_join,
    scan_directory_for_disk,
)

logger = logging.getLogger(__name__)


class FileManagerService:
    """Сервис для управления файлами через файловый менеджер."""

    @staticmethod
    def get_disk_files(
        db: Session, project: Project, show_ignored: bool = False
    ) -> list[dict[str, Any]]:
        """
        Получить файлы с диска с дополнительными флагами.
        """
        # 1. Сканируем диск
        disk_files = scan_directory_for_disk(project.folder_path, show_ignored)

        # 2. Получаем чат проекта
        chat = db.query(Chat).filter(Chat.project_id == project.id).first()

        # 3. Собираем пути файлов из БД (is_current = True)
        db_paths: set[str] = set()
        file_ids: dict[str, int] = {}
        if chat:
            versions = (
                db.query(FileVersion)
                .filter(FileVersion.chat_id == chat.id, FileVersion.is_current == True)
                .all()
            )
            for v in versions:
                normalized = v.filename.replace("\\", "/")
                db_paths.add(normalized)
                file_ids[normalized] = v.id

        # 4. Формируем ответ
        result = []
        for file in disk_files:
            normalized_path = file["path"].replace("\\", "/")
            is_in_db = normalized_path in db_paths
            full_path = safe_join(project.folder_path, normalized_path)

            result.append(
                {
                    **file,
                    "id": file_ids.get(normalized_path),
                    "isInDatabase": is_in_db,
                    "isAllowed": is_allowed_file(full_path),
                }
            )

        return result

    @staticmethod
    def soft_delete_file(
        db: Session, project: Project, filename: str
    ) -> dict[str, Any]:
        """
        Мягкое удаление: файл удаляется с диска, но остаётся в БД (is_current = False).
        """
        chat = db.query(Chat).filter(Chat.project_id == project.id).first()
        if not chat:
            raise ValueError(f"У проекта {project.id} нет чатов")

        # 1. Находим текущую версию
        version = (
            db.query(FileVersion)
            .filter(
                FileVersion.chat_id == chat.id,
                FileVersion.filename == filename,
                FileVersion.is_current == True,
            )
            .first()
        )

        was_in_db = version is not None

        # 2. Удаляем файл с диска
        full_path = os.path.join(project.folder_path, filename)
        if os.path.exists(full_path):
            os.remove(full_path)

        # 3. Обновляем статус в БД
        if version:
            version.is_current = False
            version.applied = False
            db.commit()

        # 4. Создаём снимок
        manifest = FileManagerService._get_current_manifest(db, chat.id)
        SnapshotService.create(
            db=db,
            project_id=project.id,
            snapshot_type="sync",
            level=2,
            name=f"Удалён файл с диска: {filename}",
            files_manifest=manifest,
        )

        db.commit()

        return {
            "status": "soft_deleted",
            "path": filename,
            "was_in_database": was_in_db,
            "message": "Файл удалён с диска, но остался в БД",
        }

    @staticmethod
    def hard_delete_file(
        db: Session, project: Project, filename: str
    ) -> dict[str, Any]:
        """
        Полное удаление: файл удаляется с диска и из БД (все версии).
        """
        chat = db.query(Chat).filter(Chat.project_id == project.id).first()
        if not chat:
            raise ValueError(f"У проекта {project.id} нет чатов")

        # 1. Находим все версии файла
        versions = (
            db.query(FileVersion)
            .filter(FileVersion.chat_id == chat.id, FileVersion.filename == filename)
            .all()
        )

        was_in_db = len(versions) > 0

        # 2. Удаляем файл с диска
        full_path = os.path.join(project.folder_path, filename)
        if os.path.exists(full_path):
            os.remove(full_path)

        # 3. Удаляем все версии из БД
        for version in versions:
            db.delete(version)
        db.commit()

        # 4. Создаём снимок
        manifest = FileManagerService._get_current_manifest(db, chat.id)
        SnapshotService.create(
            db=db,
            project_id=project.id,
            snapshot_type="sync",
            level=2,
            name=f"Полностью удалён файл: {filename}",
            files_manifest=manifest,
        )

        db.commit()

        return {
            "status": "hard_deleted",
            "path": filename,
            "was_in_database": was_in_db,
            "versions_deleted": len(versions),
            "message": "Файл полностью удалён (с диска и из БД)",
        }

    @staticmethod
    def sync_disk_to_db(db: Session, project: Project) -> dict[str, Any]:
        """
        Синхронизировать файлы с диска в БД.
        """
        chat = db.query(Chat).filter(Chat.project_id == project.id).first()
        if not chat:
            raise ValueError(f"У проекта {project.id} нет чатов")

        # Сканируем диск
        disk_files = scan_directory_for_disk(project.folder_path, show_ignored=False)

        created = 0
        updated = 0

        for file_info in disk_files:
            filename = file_info["path"].replace("\\", "/")

            # Проверяем, есть ли уже такая версия в БД
            existing = (
                db.query(FileVersion)
                .filter(
                    FileVersion.chat_id == chat.id,
                    FileVersion.filename == filename,
                    FileVersion.is_current == True,
                )
                .first()
            )

            if existing:
                # Обновляем существующую
                existing.is_current = True
                existing.applied = True
                updated += 1
            else:
                # Создаём новую версию
                try:
                    with open(
                        os.path.join(project.folder_path, filename),
                        encoding="utf-8",
                    ) as f:
                        content = f.read()
                except (OSError, UnicodeDecodeError):
                    continue

                version = FileVersion(
                    chat_id=chat.id,
                    filename=filename,
                    content=content,
                    content_hash=hashlib.sha256(content.encode()).hexdigest(),
                    file_type="synced",
                    is_current=True,
                    applied=True,
                )
                db.add(version)
                created += 1

        db.commit()

        # Создаём снимок
        manifest = FileManagerService._get_current_manifest(db, chat.id)
        SnapshotService.create(
            db=db,
            project_id=project.id,
            snapshot_type="sync",
            level=2,
            name="Синхронизация с диска",
            files_manifest=manifest,
        )

        db.commit()

        return {
            "status": "synced",
            "created": created,
            "updated": updated,
            "message": f"Создано {created} файлов, обновлено {updated} файлов",
        }

    @staticmethod
    def flatten_history(db: Session, project: Project) -> dict[str, Any]:
        """
        Сбросить историю состояний.
        Удаляет все старые снимки и неактуальные версии файлов.
        """
        chat = db.query(Chat).filter(Chat.project_id == project.id).first()
        if not chat:
            raise ValueError(f"У проекта {project.id} нет чатов")

        # 1. Получаем текущий снимок
        current = (
            db.query(Snapshot)
            .filter(Snapshot.project_id == project.id, Snapshot.is_current == True)
            .first()
        )

        if not current:
            raise ValueError("Нет текущего состояния")

        # 2. Сохраняем текущие файлы
        current_files = (
            db.query(FileVersion)
            .filter(FileVersion.chat_id == chat.id, FileVersion.is_current == True)
            .all()
        )

        # 3. Сохраняем мэнифест
        manifest = {}
        for f in current_files:
            manifest[f.filename] = f.content_hash

        # 4. Удаляем все неактуальные версии
        deleted_versions = (
            db.query(FileVersion)
            .filter(FileVersion.chat_id == chat.id, FileVersion.is_current == False)
            .delete()
        )

        # 5. Удаляем все старые снимки
        deleted_snapshots = (
            db.query(Snapshot).filter(Snapshot.project_id == project.id).delete()
        )

        # 6. Создаём новый снимок как initial
        new_snapshot = Snapshot(
            project_id=project.id,
            prev_id=None,
            sequence_number=1,
            level=1,
            type="initial",
            name="История сброшена",
            description="Все предыдущие состояния и версии удалены",
            files_manifest=manifest,
            is_current=True,
        )
        db.add(new_snapshot)

        # 7. Очищаем message_id у текущих файлов
        for f in current_files:
            f.message_id = None

        db.commit()

        return {
            "status": "flattened",
            "new_snapshot_id": new_snapshot.id,
            "deleted_snapshots": deleted_snapshots,
            "deleted_versions": deleted_versions,
            "preserved_files": len(current_files),
            "message": f"Удалено {deleted_snapshots} снимков и {deleted_versions} версий файлов",
        }

    @staticmethod
    def _get_current_manifest(db: Session, chat_id: int) -> dict[str, str]:
        """Собирает мэнифест текущих файлов чата."""
        manifest = {}
        current_files = (
            db.query(FileVersion)
            .filter(FileVersion.chat_id == chat_id, FileVersion.is_current == True)
            .all()
        )

        for version in current_files:
            manifest[version.filename] = version.content_hash

        return manifest
