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
from app.schemas.file_version import FileVersionResponse, ApplyRequest, MakeCurrentRequest
from app.services.file_service import FileService
from app.api.dependencies import get_chat
from fastapi import UploadFile, File, Form
from typing import List, Optional

router = APIRouter(prefix="/files", tags=["files"])


@router.get("/chats/{chat_id}", response_model=List[FileVersionResponse])
def get_files(chat_id: int, db: Session = Depends(get_db)):
    """Получить все файлы чата."""
    return FileService.get_by_chat(db, chat_id)

@router.get("/projects/{project_id}/files", response_model=List[FileVersionResponse])
def get_project_files(
    project_id: int,
    db: Session = Depends(get_db)
):
    """
    Получить все текущие версии файлов для проекта.
    """
    return FileService.get_by_project(db, project_id)

@router.get("/{file_id}", response_model=FileVersionResponse)
def get_file(file_id: int, db: Session = Depends(get_db)):
    """Получить версию файла по ID."""
    version = FileService.get_by_id(db, file_id)
    if not version:
        raise HTTPException(status_code=404, detail="Файл не найден")
    return version


# @router.post("/projects/{project_id}/upload", response_model=List[FileVersionResponse])
# async def upload_files(
#     project_id: int,
#     files: List[UploadFile] = File(...),
#     db: Session = Depends(get_db)
# ):
#     """Загрузить файлы в проект."""
#     return await FileService.upload(db, project_id, files)
@router.post("/projects/{project_id}/upload", response_model=List[FileVersionResponse])
async def upload_files(
    project_id: int,
    files: Optional[List[UploadFile]] = File(None),  # <-- сделали опциональным
    filenames: Optional[List[str]] = Form(None),
    db: Session = Depends(get_db)
):
    """
    Загрузить или синхронизировать файлы.
    - files: файлы с содержимым (из input type="file")
    - filenames: имена файлов на диске (для синхронизации)
    """
    # Если переданы файлы с содержимым
    if files and len(files) > 0:
        return await FileService.upload(db, project_id, files)
    
    # Если переданы только имена файлов
    if filenames and len(filenames) > 0:
        return  FileService.sync_by_filename(db, project_id, filenames)
    

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
