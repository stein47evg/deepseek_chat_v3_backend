"""
Эндпоинты для файлового менеджера.
"""

import logging
import os

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.project import Project
from app.schemas.file_manager import (
    DeleteFileResponse,
    DiskFileResponse,
    FlattenHistoryResponse,
)
from app.services.file_manager_service import FileManagerService
from app.utils.file_utils import safe_join

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/file-manager", tags=["File Manager"])


@router.get("/{project_id}/disk-files", response_model=list[DiskFileResponse])
def get_disk_files(
    project_id: int, show_ignored: bool = False, db: Session = Depends(get_db)
):
    """
    Получить все файлы на диске проекта с флагами состояния.
    - show_ignored: показывать игнорируемые файлы (node_modules, .git и т.д.)
    """
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail=f"Проект {project_id} не найден")

    if not os.path.exists(project.folder_path):
        return []

    return FileManagerService.get_disk_files(db, project, show_ignored)


@router.post("/{project_id}/disk-files/sync")
def sync_disk_files(project_id: int, db: Session = Depends(get_db)):
    """
    Синхронизировать файлы с диска в БД.
    """
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail=f"Проект {project_id} не найден")

    return FileManagerService.sync_disk_to_db(db, project)


@router.delete("/{project_id}/files/{path:path}", response_model=DeleteFileResponse)
def delete_file(
    project_id: int, path: str, hard: bool = False, db: Session = Depends(get_db)
):
    """
    Удалить файл с диска.
    - hard=True: полное удаление (из БД и с диска)
    - hard=False: мягкое удаление (с диска, но в БД остаётся is_current=False)
    """
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail=f"Проект {project_id} не найден")

    normalized_path = path.replace("\\", "/")
    full_path = safe_join(project.folder_path, normalized_path)

    if not os.path.exists(full_path):
        raise HTTPException(
            status_code=404, detail=f"Файл {normalized_path} не найден на диске"
        )

    if os.path.isdir(full_path):
        raise HTTPException(status_code=400, detail="Нельзя удалить папку")

    if hard:
        result = FileManagerService.hard_delete_file(db, project, normalized_path)
    else:
        result = FileManagerService.soft_delete_file(db, project, normalized_path)

    return result


@router.post("/{project_id}/history/flatten", response_model=FlattenHistoryResponse)
def flatten_history(project_id: int, db: Session = Depends(get_db)):
    """
    Сбросить историю состояний.
    Удаляет все старые снимки и неактуальные версии файлов.
    """
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail=f"Проект {project_id} не найден")

    return FileManagerService.flatten_history(db, project)
