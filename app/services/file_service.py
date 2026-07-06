"""
Сервис для работы с файлами.
"""
import os
from typing import List, Optional
from fastapi import UploadFile, HTTPException
from sqlalchemy.orm import Session
from app.models.project import Project
from app.models.chat import Chat
from app.models.file_version import FileVersion
from app.models.snapshot import Snapshot
from app.schemas.file_version import FileVersionResponse
from app.utils.file_utils import safe_join, validate_file_size, is_allowed_file
from app.utils.hash_utils import compute_hash
from app.services.snapshot_service import SnapshotService


class FileService:
    """Сервис для управления файлами."""

    @staticmethod
    def get_by_chat(db: Session, chat_id: int):
        """Получить все файлы чата."""
        return db.query(FileVersion).filter(
            FileVersion.chat_id == chat_id
        ).order_by(FileVersion.filename, FileVersion.created_at.desc()).all()

    @staticmethod
    def get_by_id(db: Session, file_id: int) -> Optional[FileVersion]:
        """Получить версию файла по ID."""
        return db.query(FileVersion).filter(FileVersion.id == file_id).first()

    @staticmethod
    async def upload(db: Session, project_id: int, files: List[UploadFile]) -> List[FileVersion]:
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
