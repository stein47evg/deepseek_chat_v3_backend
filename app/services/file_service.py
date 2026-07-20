"""
Сервис для работы с файлами.
"""
from sqlalchemy.orm import Session
from fastapi import HTTPException
from datetime import datetime
from app.models.chat import Chat  # ✅ добавлен импорт
from app.models.file_version import FileVersion
from app.models.project import Project
from app.services.file_reader_service import FileReaderService
from app.services.apply_service import ApplyService
from app.services.snapshot_service import SnapshotService
from app.services.file_manager_service import FileManagerService


class FileService:
    """Сервис для управления файлами."""

    get_by_chat = staticmethod(FileReaderService.get_by_chat)
    get_by_project = staticmethod(FileReaderService.get_by_project)
    get_by_id = staticmethod(FileReaderService.get_by_id)

    @staticmethod
    def delete(db: Session, file_id: int):
        """Удалить версию файла."""
        version = FileReaderService.get_by_id(db, file_id)
        db.delete(version)

    @staticmethod
    def apply(db: Session, file_id: int) -> dict:
        """Применить версию файла."""
        return ApplyService.apply_file(db, file_id)

    @staticmethod
    def apply_message_files(db: Session, message_id: int) -> dict:
        """Применить все файлы из сообщения."""
        return ApplyService.apply_message_files(db, message_id)

    @staticmethod
    def make_current(db: Session, file_id: int) -> dict:
        """Сделать версию текущей."""
        version = FileReaderService.get_by_id(db, file_id)
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
            snapshot_type="auto",
            level=3,
            name=f"Выбрана версия {version.filename}",
            new_files={version.filename: version.content_hash}
        )

        SnapshotService.restore(db, future.id)
        return {"status": "current", "version_id": version.id}

    @staticmethod
    def get_unified_files(
        db: Session, 
        project_id: int, 
        show_ignored: bool = False
    ) -> dict:
        """Получить унифицированную информацию о файлах проекта."""
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise HTTPException(status_code=404, detail=f"Проект {project_id} не найден")

        disk_files = FileManagerService.get_disk_files(db, project, show_ignored)

        # Получаем все текущие файлы из ВСЕХ чатов проекта
        chats = db.query(Chat).filter(Chat.project_id == project_id).all()
        chat_ids = [c.id for c in chats]
        
        db_files = {}
        if chat_ids:
            versions = db.query(FileVersion).filter(
                FileVersion.chat_id.in_(chat_ids),
                FileVersion.is_current == True
            ).all()
            for v in versions:
                normalized = v.filename.replace("\\", "/")
                db_files[normalized] = v

        unified_files = []
        in_db_count = 0
        not_in_db_count = 0

        for disk_file in disk_files:
            path = disk_file["path"]
            version = db_files.get(path)
            
            is_in_db = version is not None
            if is_in_db:
                in_db_count += 1
            else:
                not_in_db_count += 1

            modified_iso = None
            if disk_file.get("modified"):
                try:
                    modified_iso = datetime.fromtimestamp(
                        disk_file["modified"]
                    ).isoformat()
                except:
                    pass

            unified_files.append({
                "path": path,
                "name": disk_file["name"],
                "size": disk_file["size"],
                "modified": disk_file.get("modified"),
                "modified_iso": modified_iso,
                "in_database": is_in_db,
                "version_id": version.id if version else None,
                "content": version.content if version else None,
                "language": version.language if version else None,
                "file_type": version.file_type if version else None,
                "is_current": version.is_current if version else False,
                "applied": version.applied if version else False,
                "is_allowed": disk_file.get("isAllowed", True),
                "is_directory": disk_file.get("isDirectory", False)
            })

        return {
            "project_id": project.id,
            "project_name": project.name,
            "folder_path": project.folder_path,
            "files": unified_files,
            "total": len(unified_files),
            "in_database_count": in_db_count,
            "not_in_database_count": not_in_db_count
        }
