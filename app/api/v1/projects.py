"""
Эндпоинты для управления проектами.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from app.core.database import get_db
from app.models.project import Project
from app.models.chat import Chat
from app.models.file_version import FileVersion
from app.schemas.project import ProjectCreate, ProjectResponse, ProjectUpdate
from app.services.project_service import ProjectService

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("/", response_model=List[ProjectResponse])
def get_projects(db: Session = Depends(get_db)):
    """Получить список всех проектов."""
    return ProjectService.get_all(db)


@router.post("/", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
def create_project(data: ProjectCreate, db: Session = Depends(get_db)):
    """Создать новый проект."""
    return ProjectService.create(db, data)


@router.put("/{project_id}", response_model=ProjectResponse)
def update_project(project_id: int, data: ProjectUpdate, db: Session = Depends(get_db)):
    """Обновить проект."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail=f"Проект {project_id} не найден")
    
    if data.name is not None:
        project.name = data.name
    if data.folder_path is not None:
        project.folder_path = data.folder_path
    
    db.commit()
    db.refresh(project)
    return project


@router.get("/{project_id}", response_model=ProjectResponse)
def get_project_by_id(project_id: int, db: Session = Depends(get_db)):
    """Получить проект по ID."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail=f"Проект {project_id} не найден")
    return project


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(project_id: int, db: Session = Depends(get_db)):
    """Удалить проект и все связанные данные."""
    ProjectService.delete(db, project_id)


@router.get("/{project_id}/files")
def get_project_files(project_id: int, db: Session = Depends(get_db)):
    """Получить список файлов проекта."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail=f"Проект {project_id} не найден")
    
    chat = db.query(Chat).filter(Chat.project_id == project_id).first()
    if not chat:
        return []
    
    files = db.query(FileVersion).filter(
        FileVersion.chat_id == chat.id,
        FileVersion.is_current == True
    ).all()
    
    result = []
    for file in files:
        result.append({
            "path": file.filename,
            "name": file.filename.split('/')[-1],
            "content": file.content,
            "size": len(file.content),
            "language": file.language or "text",
            "tokens": len(file.content) // 4
        })
    
    return result
