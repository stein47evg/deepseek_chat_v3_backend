"""
Общие зависимости для эндпоинтов.
"""

from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.chat import Chat
from app.models.project import Project
from app.models.snapshot import Snapshot


def get_project(project_id: int, db: Session = Depends(get_db)) -> Project:
    """
    Получить проект по ID или вернуть 404.
    """
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail=f"Проект {project_id} не найден")
    return project


def get_chat(chat_id: int, db: Session = Depends(get_db)) -> Chat:
    """
    Получить чат по ID или вернуть 404.
    """
    chat = db.query(Chat).filter(Chat.id == chat_id).first()
    if not chat:
        raise HTTPException(status_code=404, detail=f"Чат {chat_id} не найден")
    return chat


def get_snapshot(snapshot_id: int, db: Session = Depends(get_db)) -> Snapshot:
    """
    Получить снимок по ID или вернуть 404.
    """
    snapshot = db.query(Snapshot).filter(Snapshot.id == snapshot_id).first()
    if not snapshot:
        raise HTTPException(status_code=404, detail=f"Снимок {snapshot_id} не найден")
    return snapshot


def get_current_snapshot(project_id: int, db: Session = Depends(get_db)) -> Snapshot | None:
    """
    Получить текущий снимок проекта.
    """
    return db.query(Snapshot).filter(
        Snapshot.project_id == project_id,
        Snapshot.is_current == True
    ).first()
