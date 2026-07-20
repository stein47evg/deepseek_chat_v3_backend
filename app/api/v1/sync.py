"""
Эндпоинты для синхронизации.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.schemas.sync import SyncResponse
from app.services.sync_service import SyncService
from app.api.dependencies import get_project

router = APIRouter(prefix="/sync", tags=["sync"])


@router.post("/projects/{project_id}", response_model=SyncResponse)
def sync_project(project_id: int, db: Session = Depends(get_db)):
    """Явная синхронизация: диск → база."""
    result = SyncService.explicit_sync(db, project_id)
    db.commit()
    return result


@router.post("/projects/{project_id}/quiet", response_model=SyncResponse)
def quiet_sync(project_id: int, db: Session = Depends(get_db)):
    """Тихая синхронизация: обнаружение изменений и удалений."""
    result = SyncService.quiet_sync(db, project_id)
    db.commit()
    return result
