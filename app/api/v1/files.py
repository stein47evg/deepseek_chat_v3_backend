"""
Эндпоинты для управления файлами.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from app.core.database import get_db
from app.models.file_version import FileVersion
from app.schemas.file_version import FileVersionResponse
from app.schemas.files import UnifiedFileResponse, UnifiedFilesResponse
from app.services.file_service import FileService
from app.services.apply_service import ApplyService
from fastapi import File, Form, UploadFile

router = APIRouter(prefix="/files", tags=["files"])


# ======== ПРИМЕНЕНИЕ ФАЙЛОВ ========
@router.post("/messages/{message_id}/apply")
def apply_message_files(message_id: int, db: Session = Depends(get_db)):
    """
    Применить все файлы из сообщения на диск.
    Использует единый механизм create_future + restore.
    """
    result = ApplyService.apply_message_files(db, message_id)
    db.commit()
    return result


@router.put("/{file_id}/apply")
def apply_file(file_id: int, db: Session = Depends(get_db)):
    """Применить версию файла на диск."""
    result = ApplyService.apply_file(db, file_id)
    db.commit()
    return result


@router.post("/{file_id}/make-current")
def make_current(file_id: int, db: Session = Depends(get_db)):
    """Сделать версию текущей (выбор индивидуальной версии)."""
    result = FileService.make_current(db, file_id)
    db.commit()
    return result


# ======== ЧТЕНИЕ ФАЙЛОВ ========
@router.get("/chats/{chat_id}", response_model=List[FileVersionResponse])
def get_files(chat_id: int, db: Session = Depends(get_db)):
    """Получить все файлы чата."""
    return FileService.get_by_chat(db, chat_id)


@router.get("/projects/{project_id}", response_model=List[FileVersionResponse])
def get_project_files(
    project_id: int,
    db: Session = Depends(get_db)
):
    """Получить все текущие версии файлов для проекта."""
    return FileService.get_by_project(db, project_id)


@router.get("/projects/{project_id}/unified", response_model=UnifiedFilesResponse)
def get_unified_files(
    project_id: int,
    show_ignored: bool = False,
    db: Session = Depends(get_db)
):
    """
    Универсальный эндпоинт для получения всех файлов проекта.
    Объединяет информацию с диска и из базы данных в одном формате.
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


# ======== УДАЛЕНИЕ ========
@router.delete("/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_file(file_id: int, db: Session = Depends(get_db)):
    """Удалить версию файла."""
    FileService.delete(db, file_id)
    db.commit()
