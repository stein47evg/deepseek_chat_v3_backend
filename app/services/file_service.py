"""
Сервис для работы с файлами.
"""
import os

from fastapi import HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.models.chat import Chat
from app.models.file_version import FileVersion
from app.models.project import Project
from app.services.snapshot_service import SnapshotService
from app.utils.file_utils import is_allowed_file, safe_join, validate_file_size
from app.utils.hash_utils import compute_hash
from typing import List


class FileService:
    """Сервис для управления файлами."""

    @staticmethod
    def get_by_chat(db: Session, chat_id: int):
        """Получить все файлы чата."""
        return db.query(FileVersion).filter(
            FileVersion.chat_id == chat_id
        ).order_by(FileVersion.filename, FileVersion.created_at.desc()).all()

    @staticmethod
    def get_by_project(db: Session, project_id: int) -> List[FileVersion]:
        """
        Получить все текущие версии файлов для проекта.
        """
        # Находим чат проекта
        chat = db.query(Chat).filter(Chat.project_id == project_id).first()
        if not chat:
            return []
        
        # Получаем все текущие версии файлов чата
        return db.query(FileVersion).filter(
            FileVersion.chat_id == chat.id,
            FileVersion.is_current == True
        ).order_by(FileVersion.filename.asc()).all()

    @staticmethod
    def get_by_id(db: Session, file_id: int) -> FileVersion | None:
        """Получить версию файла по ID."""
        return db.query(FileVersion).filter(FileVersion.id == file_id).first()

    @staticmethod
    async def upload(db: Session, project_id: int, files: list[UploadFile]) -> list[FileVersion]:
        """
        Загрузить файлы в проект.
        Файлы сразу записываются на диск и создаются версии.
        """
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise HTTPException(status_code=404, detail="Проект не найден")

        chat = db.query(Chat).filter(Chat.project_id == project_id).first()
        if not chat:
            raise HTTPException(status_code=404, detail="У проекта нет чатов")

        created_versions = []
        manifest = {}

        for uploaded_file in files:
            # Валидация
            if not is_allowed_file(uploaded_file.filename):
                raise HTTPException(
                    status_code=415,
                    detail=f"Неподдерживаемый тип файла: {uploaded_file.filename}"
                )

            content = await uploaded_file.read()
            validate_file_size(content)

            # Декодируем содержимое
            try:
                content_str = content.decode("utf-8")
            except UnicodeDecodeError:
                raise HTTPException(
                    status_code=400,
                    detail=f"Файл {uploaded_file.filename} должен быть в UTF-8"
                )

            # Записываем на диск
            full_path = safe_join(project.folder_path, uploaded_file.filename)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            with open(full_path, "w", encoding="utf-8") as f:
                f.write(content_str)

            # Создаём версию в БД
            version = FileVersion(
                chat_id=chat.id,
                filename=uploaded_file.filename,
                content=content_str,
                content_hash=compute_hash(content_str),
                file_type="uploaded",
                is_current=True,
                applied=True
            )
            db.add(version)
            db.flush()
            created_versions.append(version)
            manifest[uploaded_file.filename] = version.content_hash

        # Создаём снимок
        SnapshotService.create(
            db=db,
            project_id=project_id,
            snapshot_type="upload",
            level=2,
            name=f"Загрузка {len(files)} файлов",
            files_manifest=manifest
        )

        db.commit()
        return created_versions

    @staticmethod
    def sync_by_filename(db: Session, project_id: int, filenames: list[str]) -> list[FileVersion]:
        """
        Синхронизировать файлы по их именам (путям) с диска в БД.
        """
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise HTTPException(status_code=404, detail="Проект не найден")

        chat = db.query(Chat).filter(Chat.project_id == project_id).first()
        if not chat:
            raise HTTPException(status_code=404, detail="У проекта нет чатов")

        created_versions = []
        manifest = {}

        for filename in filenames:
            normalized_path = filename.replace("\\", "/")
            full_path = safe_join(project.folder_path, normalized_path)

            if not os.path.exists(full_path):
                continue

            if not is_allowed_file(normalized_path):
                continue

            # Читаем содержимое
            try:
                with open(full_path, "r", encoding="utf-8") as f:
                    content_str = f.read()
            except UnicodeDecodeError:
                continue

            # Проверяем, есть ли уже такая версия
            existing = db.query(FileVersion).filter(
                FileVersion.chat_id == chat.id,
                FileVersion.filename == normalized_path,
                FileVersion.is_current == True
            ).first()

            if existing:
                # Обновляем существующую
                existing.content = content_str
                existing.content_hash = compute_hash(content_str)
                existing.is_current = True
                existing.applied = True
                created_versions.append(existing)
            else:
                # Создаём новую версию
                version = FileVersion(
                    chat_id=chat.id,
                    filename=normalized_path,
                    content=content_str,
                    content_hash=compute_hash(content_str),
                    file_type="synced",
                    is_current=True,
                    applied=True
                )
                db.add(version)
                db.flush()
                created_versions.append(version)

            manifest[normalized_path] = compute_hash(content_str)

        # Создаём снимок
        SnapshotService.create(
            db=db,
            project_id=project_id,
            snapshot_type="sync",
            level=2,
            name=f"Синхронизация {len(filenames)} файлов",
            files_manifest=manifest
        )

        db.commit()
        return created_versions

    @staticmethod
    def apply(db: Session, file_id: int) -> dict:
        """
        Применить версию файла на диск.
        Версия становится текущей (is_current=True).
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

        # Создаём снимок
        manifest = FileService._get_current_manifest(db, chat.id)
        SnapshotService.create(
            db=db,
            project_id=project.id,
            snapshot_type="apply",
            level=2,
            name=f"Применена версия {version.filename}",
            files_manifest=manifest
        )

        db.commit()
        return {"status": "applied", "version_id": version.id}

    @staticmethod
    def make_current(db: Session, file_id: int) -> dict:
        """
        Сделать версию текущей (выбор индивидуальной версии).
        Создаётся автоматический снимок (уровень 3).
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

        # Создаём автоматический снимок (уровень 3)
        manifest = FileService._get_current_manifest(db, chat.id)
        SnapshotService.create(
            db=db,
            project_id=project.id,
            snapshot_type="auto",
            level=3,
            name=f"Выбрана версия {version.filename}",
            files_manifest=manifest
        )

        db.commit()
        return {"status": "current", "version_id": version.id}

    @staticmethod
    def delete(db: Session, file_id: int):
        """Удалить версию файла."""
        version = db.query(FileVersion).filter(FileVersion.id == file_id).first()
        if version:
            db.delete(version)
            db.commit()

    @staticmethod
    def _get_current_manifest(db: Session, chat_id: int) -> dict:
        """Собирает мэнифест текущих файлов чата."""
        manifest = {}
        current_files = db.query(FileVersion).filter(
            FileVersion.chat_id == chat_id,
            FileVersion.is_current == True
        ).all()

        for version in current_files:
            manifest[version.filename] = version.content_hash

        return manifest
