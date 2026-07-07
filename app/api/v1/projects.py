"""
Эндпоинты для управления проектами.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from app.core.database import get_db
from app.models.project import Project
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
