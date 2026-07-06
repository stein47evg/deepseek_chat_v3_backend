import os
from sqlalchemy.orm import Session
from fastapi import HTTPException
from app.models.project import Project
from app.models.chat import Chat
from app.schemas.project import ProjectCreate
from app.utils.file_utils import scan_directory
from app.services.snapshot_service import SnapshotService


class ProjectService:

    @staticmethod
    def get_all(db: Session):
        return db.query(Project).order_by(Project.created_at.desc()).all()

    @staticmethod
    def create(db: Session, data: ProjectCreate):
        if not os.path.exists(data.folder_path):
            raise HTTPException(status_code=404, detail=f"Папка {data.folder_path} не существует")

        existing = db.query(Project).filter(
            Project.folder_path == data.folder_path
        ).first()
        if existing:
            raise HTTPException(
                status_code=400,
                detail=f"Проект с папкой {data.folder_path} уже существует"
            )

        project = Project(
            name=data.name,
            folder_path=data.folder_path
        )
        db.add(project)
        db.flush()

        chat = Chat(
            project_id=project.id,
            title="Основной чат"
        )
        db.add(chat)
        db.flush()

        files = scan_directory(data.folder_path)
        manifest = {}

        for filename, content in files:
            manifest[filename] = None

        SnapshotService.create(
            db=db,
            project_id=project.id,
            snapshot_type="initial",
            level=1,
            name="Исходное состояние",
            description="Состояние проекта до первой генерации",
            files_manifest=manifest
        )

        db.commit()
        return project

    @staticmethod
    def delete(db: Session, project_id: int):
        project = db.query(Project).filter(Project.id == project_id).first()
        if project:
            db.delete(project)
            db.commit()
