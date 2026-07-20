import os
from typing import List, Optional, Dict
from sqlalchemy.orm import Session
from fastapi import HTTPException
from app.models.snapshot import Snapshot
from app.models.project import Project
from app.models.chat import Chat
from app.models.file_version import FileVersion
from app.utils.file_utils import safe_join


class SnapshotService:

    @staticmethod
    def get_by_project(db: Session, project_id: int):
        return db.query(Snapshot).filter(
            Snapshot.project_id == project_id
        ).order_by(Snapshot.sequence_number.asc()).all()

    @staticmethod
    def get_by_levels(db: Session, project_id: int, levels: List[int]):
        return db.query(Snapshot).filter(
            Snapshot.project_id == project_id,
            Snapshot.level.in_(levels)
        ).order_by(Snapshot.sequence_number.asc()).all()

    @staticmethod
    def get_current(db: Session, project_id: int) -> Optional[Snapshot]:
        return db.query(Snapshot).filter(
            Snapshot.project_id == project_id,
            Snapshot.is_current == True
        ).first()

    @staticmethod
    def get_previous(db: Session, project_id: int) -> Optional[Snapshot]:
        """Получить предыдущий снимок (перед текущим)."""
        current = SnapshotService.get_current(db, project_id)
        if not current:
            return None
        
        return db.query(Snapshot).filter(
            Snapshot.project_id == project_id,
            Snapshot.sequence_number < current.sequence_number
        ).order_by(Snapshot.sequence_number.desc()).first()

    @staticmethod
    def get_next(db: Session, project_id: int) -> Optional[Snapshot]:
        """Получить следующий снимок (после текущего)."""
        current = SnapshotService.get_current(db, project_id)
        if not current:
            return None
        
        return db.query(Snapshot).filter(
            Snapshot.project_id == project_id,
            Snapshot.sequence_number > current.sequence_number
        ).order_by(Snapshot.sequence_number.asc()).first()

    @staticmethod
    def create(
        db: Session,
        project_id: int,
        snapshot_type: str,
        level: int,
        name: Optional[str] = None,
        description: Optional[str] = None,
        files_manifest: Optional[Dict[str, str]] = None
    ) -> Snapshot:
        current = SnapshotService.get_current(db, project_id)

        last = db.query(Snapshot).filter(
            Snapshot.project_id == project_id
        ).order_by(Snapshot.sequence_number.desc()).first()

        next_seq = last.sequence_number + 1 if last else 1

        if files_manifest is None:
            files_manifest = SnapshotService._get_current_manifest(db, project_id)

        snapshot = Snapshot(
            project_id=project_id,
            prev_id=current.id if current else None,
            sequence_number=next_seq,
            level=level,
            type=snapshot_type,
            name=name,
            description=description,
            files_manifest=files_manifest,
            is_current=True
        )

        db.add(snapshot)
        db.flush()

        db.query(Snapshot).filter(
            Snapshot.project_id == project_id,
            Snapshot.id != snapshot.id
        ).update({"is_current": False})

        db.commit()
        return snapshot

    @staticmethod
    def create_manual(db: Session, project_id: int, name: str, description: Optional[str] = None) -> Snapshot:
        return SnapshotService.create(
            db=db,
            project_id=project_id,
            snapshot_type="manual",
            level=1,
            name=name,
            description=description
        )

    @staticmethod
    def restore(db: Session, snapshot_id: int, strategy: str = "ask") -> dict:
        snapshot = db.query(Snapshot).filter(Snapshot.id == snapshot_id).first()
        if not snapshot:
            raise HTTPException(status_code=404, detail=f"Снимок {snapshot_id} не найден")

        project = db.query(Project).filter(Project.id == snapshot.project_id).first()
        if not project:
            raise HTTPException(status_code=404, detail=f"Проект {snapshot.project_id} не найден")

        if strategy == "ask":
            current = SnapshotService.get_current(db, project.id)
            if current:
                current_manifest = SnapshotService._get_current_manifest(db, project.id)
                if current_manifest != snapshot.files_manifest:
                    return {
                        "warning": True,
                        "message": "Есть несохранённые изменения",
                        "options": ["preserve", "overwrite", "cancel"]
                    }

        chat = db.query(Chat).filter(Chat.project_id == project.id).first()
        if not chat:
            raise HTTPException(status_code=404, detail=f"У проекта {project.id} нет чатов")

        for filename, content_hash in snapshot.files_manifest.items():
            version = db.query(FileVersion).filter(
                FileVersion.chat_id == chat.id,
                FileVersion.filename == filename,
                FileVersion.content_hash == content_hash
            ).first()

            if not version:
                continue

            full_path = safe_join(project.folder_path, filename)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            with open(full_path, "w", encoding="utf-8") as f:
                f.write(version.content)

            db.query(FileVersion).filter(
                FileVersion.chat_id == chat.id,
                FileVersion.filename == filename
            ).update({"is_current": False})

            version.is_current = True

        db.query(Snapshot).filter(
            Snapshot.project_id == project.id
        ).update({"is_current": False})

        snapshot.is_current = True
        db.commit()

        return {"status": "restored", "snapshot_id": snapshot.id}

    @staticmethod
    def move_to(db: Session, snapshot_id: int) -> dict:
        return SnapshotService.restore(db, snapshot_id, strategy="overwrite")

    @staticmethod
    def rollback_to_previous(db: Session, project_id: int) -> dict:
        """
        Откатиться к предыдущему снимку (без предупреждений).
        Удобно для тестирования и разработки.
        """
        current = SnapshotService.get_current(db, project_id)
        if not current:
            raise HTTPException(
                status_code=404,
                detail="Нет текущего снимка для отката"
            )

        previous = SnapshotService.get_previous(db, project_id)
        if not previous:
            raise HTTPException(
                status_code=404,
                detail="Нет предыдущего снимка для отката"
            )

        return SnapshotService.restore(db, previous.id, strategy="overwrite")

    @staticmethod
    def forward_to_next(db: Session, project_id: int) -> dict:
        """
        Перейти к следующему снимку (без предупреждений).
        Удобно для тестирования и разработки.
        """
        current = SnapshotService.get_current(db, project_id)
        if not current:
            raise HTTPException(
                status_code=404,
                detail="Нет текущего снимка для перехода"
            )

        next_snapshot = SnapshotService.get_next(db, project_id)
        if not next_snapshot:
            raise HTTPException(
                status_code=404,
                detail="Нет следующего снимка для перехода"
            )

        return SnapshotService.restore(db, next_snapshot.id, strategy="overwrite")

    @staticmethod
    def delete(db: Session, snapshot_id: int):
        snapshot = db.query(Snapshot).filter(Snapshot.id == snapshot_id).first()
        if not snapshot:
            return

        if snapshot.level != 1:
            raise HTTPException(status_code=400, detail="Можно удалять только ручные снимки (level=1)")

        if snapshot.is_current:
            prev = db.query(Snapshot).filter(
                Snapshot.project_id == snapshot.project_id,
                Snapshot.id != snapshot.id
            ).order_by(Snapshot.sequence_number.desc()).first()

            if prev:
                prev.is_current = True

        db.delete(snapshot)
        db.commit()

    @staticmethod
    def _get_current_manifest(db: Session, project_id: int) -> Dict[str, str]:
        chat = db.query(Chat).filter(Chat.project_id == project_id).first()
        if not chat:
            return {}

        manifest = {}
        current_files = db.query(FileVersion).filter(
            FileVersion.chat_id == chat.id,
            FileVersion.is_current == True
        ).all()

        for version in current_files:
            manifest[version.filename] = version.content_hash

        return manifest
