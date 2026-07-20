"""
Эндпоинты для управления снимками состояний.
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.snapshot import Snapshot
from app.schemas.snapshot import SnapshotCreate, SnapshotResponse, RestoreRequest
from app.services.snapshot_service import SnapshotService

router = APIRouter(prefix="/snapshots", tags=["snapshots"])


@router.get("/projects/{project_id}", response_model=List[SnapshotResponse])
def get_snapshots(
    project_id: int,
    level: Optional[str] = Query(None, description="1,2,3 или all"),
    db: Session = Depends(get_db)
):
    """Получить снимки проекта с фильтром по уровню."""
    if level == "all" or not level:
        return SnapshotService.get_by_project(db, project_id)
    else:
        levels = [int(l) for l in level.split(",")]
        return SnapshotService.get_by_levels(db, project_id, levels)


@router.get("/{snapshot_id}", response_model=SnapshotResponse)
def get_snapshot_by_id(snapshot_id: int, db: Session = Depends(get_db)):
    """Получить снимок по ID."""
    snapshot = db.query(Snapshot).filter(Snapshot.id == snapshot_id).first()
    if not snapshot:
        raise HTTPException(status_code=404, detail=f"Снимок {snapshot_id} не найден")
    return snapshot


@router.post("/projects/{project_id}", response_model=SnapshotResponse, status_code=status.HTTP_201_CREATED)
def create_snapshot(
    project_id: int,
    data: SnapshotCreate,
    db: Session = Depends(get_db)
):
    """Создать ручной снимок (уровень 1)."""
    return SnapshotService.create_manual(db, project_id, data.name, data.description)


@router.post("/{snapshot_id}/restore")
def restore_snapshot(
    snapshot_id: int,
    request: RestoreRequest = RestoreRequest(),
    db: Session = Depends(get_db)
):
    """Восстановить состояние проекта из снимка."""
    return SnapshotService.restore(db, snapshot_id, request.strategy)


@router.post("/{snapshot_id}/move")
def move_to_snapshot(
    snapshot_id: int,
    db: Session = Depends(get_db)
):
    """Переместиться к снимку (сделать текущим)."""
    return SnapshotService.move_to(db, snapshot_id)


@router.post("/projects/{project_id}/rollback")
def rollback_to_previous(
    project_id: int,
    db: Session = Depends(get_db)
):
    """
    Откатиться к предыдущему снимку (без предупреждений).
    Удобно для тестирования и разработки.
    """
    return SnapshotService.rollback_to_previous(db, project_id)


# ======== НОВЫЙ ЭНДПОЙНТ ========
@router.post("/projects/{project_id}/forward")
def forward_to_next(
    project_id: int,
    db: Session = Depends(get_db)
):
    """
    Перейти к следующему снимку (без предупреждений).
    Удобно для тестирования и разработки.
    """
    return SnapshotService.forward_to_next(db, project_id)


@router.delete("/{snapshot_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_snapshot(
    snapshot_id: int,
    db: Session = Depends(get_db)
):
    """Удалить снимок (только ручные)."""
    SnapshotService.delete(db, snapshot_id)
