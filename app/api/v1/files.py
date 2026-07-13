"""
Эндпоинты для управления файлами.
"""

import os

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.config import settings
from app.models.file_version import FileVersion
from app.models.chat import Chat
from app.models.project import Project
from app.schemas.file_version import (
    FileVersionResponse,
    ApplyRequest,
    MakeCurrentRequest,
)
from app.schemas.files import UnifiedFileResponse, UnifiedFilesResponse
from app.services.file_service import FileService
from app.services.file_manager_service import FileManagerService
from app.api.dependencies import get_chat
from fastapi import UploadFile, File, Form
from typing import List, Optional

router = APIRouter(prefix="/files", tags=["files"])


@router.get("/chats/{chat_id}", response_model=List[FileVersionResponse])
def get_files(chat_id: int, db: Session = Depends(get_db)):
    """Получить все файлы чата."""
    return FileService.get_by_chat(db, chat_id)


@router.get("/projects/{project_id}", response_model=List[FileVersionResponse])
def get_project_files(project_id: int, db: Session = Depends(get_db)):
    """
    Получить все текущие версии файлов для проекта.
    """
    return FileService.get_by_project(db, project_id)


@router.get("/projects/{project_id}/unified", response_model=UnifiedFilesResponse)
def get_unified_files(
    project_id: int, show_ignored: bool = False, db: Session = Depends(get_db)
):
    """
    Универсальный эндпоинт для получения всех файлов проекта.
    Объединяет информацию с диска и из базы данных в одном формате.

    - show_ignored: показывать игнорируемые файлы (node_modules, .git и т.д.)
    """
    result = FileService.get_unified_files(db, project_id, show_ignored)
    return UnifiedFilesResponse(**result)


@router.get("/{file_id}", response_model=FileVersionResponse)
def get_file(file_id: int, db: Session = Depends(get_db)):
    """Получить версию файла по ID."""
    version = FileService.get_by_id(db, file_id)
    if not version:
        raise HTTPException(status_code=404, detail="Файл не найден")
    return version


@router.post("/projects/{project_id}/upload", response_model=List[FileVersionResponse])
async def upload_files(
    project_id: int,
    files: Optional[List[UploadFile]] = File(None),
    filenames: Optional[List[str]] = Form(None),
    db: Session = Depends(get_db),
):
    """
    Загрузить или синхронизировать файлы.
    - files: файлы с содержимым (из input type="file")
    - filenames: имена файлов на диске (для синхронизации)
    """
    if files and len(files) > 0:
        return await FileService.upload(db, project_id, files)

    if filenames and len(filenames) > 0:
        return FileService.sync_by_filename(db, project_id, filenames)

    raise HTTPException(status_code=400, detail="Не указаны файлы или имена файлов")


@router.put("/{file_id}/apply")
def apply_file(file_id: int, db: Session = Depends(get_db)):
    """Применить версию файла на диск."""
    return FileService.apply(db, file_id)


@router.post("/{file_id}/make-current")
def make_current(file_id: int, db: Session = Depends(get_db)):
    """Сделать версию текущей (выбор индивидуальной версии)."""
    return FileService.make_current(db, file_id)


@router.delete("/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_file(file_id: int, db: Session = Depends(get_db)):
    """Удалить версию файла."""
    FileService.delete(db, file_id)
