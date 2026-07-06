"""
Эндпоинты для управления файлами.
"""
import os
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.config import settings
from app.models.file_version import FileVersion
from app.models.chat import Chat
from app.schemas.file_version import FileVersionResponse, ApplyRequest, MakeCurrentRequest
from app.services.file_service import FileService
from app.api.dependencies import get_chat

router = APIRouter(prefix="/files", tags=["files"])


@router.get("/chats/{chat_id}", response_model=List[FileVersionResponse])
def get_files(chat_id: int, db: Session = Depends(get_db)):
    """Получить все файлы чата."""
    return FileService.get_by_chat(db, chat_id)


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
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db)
):
    """Загрузить файлы в проект."""
    return await FileService.upload(db, project_id, files)


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
