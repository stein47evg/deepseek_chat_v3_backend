import os
import logging
from typing import List, Optional, Dict
from sqlalchemy.orm import Session
from fastapi import HTTPException
from app.models.snapshot import Snapshot
from app.models.project import Project
from app.models.chat import Chat
from app.models.file_version import FileVersion
from app.utils.file_utils import safe_join

logger = logging.getLogger(__name__)


class SnapshotService:
    @staticmethod
    def get_by_project(db: Session, project_id: int):
        return (
            db.query(Snapshot)
            .filter(Snapshot.project_id == project_id)
            .order_by(Snapshot.sequence_number.asc())
            .all()
        )

    @staticmethod
    def get_by_levels(db: Session, project_id: int, levels: List[int]):
        return (
            db.query(Snapshot)
            .filter(Snapshot.project_id == project_id, Snapshot.level.in_(levels))
            .order_by(Snapshot.sequence_number.asc())
            .all()
        )

    @staticmethod
    def get_by_id(db: Session, snapshot_id: int):
        snapshot = db.query(Snapshot).filter(Snapshot.id == snapshot_id).first()
        if not snapshot:
            raise HTTPException(
                status_code=404, detail=f"Снимок {snapshot_id} не найден"
            )
        return snapshot

    @staticmethod
    def get_current(db: Session, project_id: int) -> Optional[Snapshot]:
        return (
            db.query(Snapshot)
            .filter(Snapshot.project_id == project_id, Snapshot.is_current == True)
            .first()
        )

    @staticmethod
    def get_previous(db: Session, project_id: int) -> Optional[Snapshot]:
        current = SnapshotService.get_current(db, project_id)
        if not current:
            return None

        return (
            db.query(Snapshot)
            .filter(
                Snapshot.project_id == project_id,
                Snapshot.sequence_number < current.sequence_number,
            )
            .order_by(Snapshot.sequence_number.desc())
            .first()
        )

    @staticmethod
    def get_next(db: Session, project_id: int) -> Optional[Snapshot]:
        current = SnapshotService.get_current(db, project_id)
        if not current:
            return None

        return (
            db.query(Snapshot)
            .filter(
                Snapshot.project_id == project_id,
                Snapshot.sequence_number > current.sequence_number,
            )
            .order_by(Snapshot.sequence_number.asc())
            .first()
        )

    @staticmethod
    def _get_current_manifest(db: Session, project_id: int) -> Dict[str, str]:
        chats = db.query(Chat).filter(Chat.project_id == project_id).all()
        if not chats:
            return {}

        chat_ids = [c.id for c in chats]
        manifest = {}
        current_files = (
            db.query(FileVersion)
            .filter(FileVersion.chat_id.in_(chat_ids), FileVersion.is_current == True)
            .all()
        )

        for version in current_files:
            manifest[version.filename] = version.content_hash or ""

        return manifest

    @staticmethod
    def create(
        db: Session,
        project_id: int,
        snapshot_type: str,
        level: int,
        name: Optional[str] = None,
        description: Optional[str] = None,
        new_files: Optional[Dict[str, str]] = None,
        make_current: bool = True,
    ) -> Snapshot:
        manifest = SnapshotService._get_current_manifest(db, project_id)

        if new_files:
            manifest.update(new_files)

        current = SnapshotService.get_current(db, project_id)

        last = (
            db.query(Snapshot)
            .filter(Snapshot.project_id == project_id)
            .order_by(Snapshot.sequence_number.desc())
            .first()
        )

        next_seq = last.sequence_number + 1 if last else 1

        snapshot = Snapshot(
            project_id=project_id,
            prev_id=current.id if current else None,
            sequence_number=next_seq,
            level=level,
            type=snapshot_type,
            name=name,
            description=description,
            files_manifest=manifest,
            is_current=make_current,
        )

        db.add(snapshot)
        db.flush()

        if make_current:
            db.query(Snapshot).filter(
                Snapshot.project_id == project_id, Snapshot.id != snapshot.id
            ).update({"is_current": False})

        return snapshot

    @staticmethod
    def create_manual(
        db: Session, project_id: int, name: str, description: Optional[str] = None
    ) -> Snapshot:
        return SnapshotService.create(
            db=db,
            project_id=project_id,
            snapshot_type="manual",
            level=1,
            name=name,
            description=description,
            make_current=True,
        )

    @staticmethod
    def create_future(
        db: Session,
        project_id: int,
        snapshot_type: str,
        level: int,
        name: Optional[str] = None,
        description: Optional[str] = None,
        new_files: Optional[Dict[str, str]] = None,
    ) -> Snapshot:
        return SnapshotService.create(
            db=db,
            project_id=project_id,
            snapshot_type=snapshot_type,
            level=level,
            name=name,
            description=description,
            new_files=new_files,
            make_current=False,
        )

    @staticmethod
    def restore(db: Session, snapshot_id: int, strategy: str = "ask") -> dict:
        snapshot = SnapshotService.get_by_id(db, snapshot_id)

        project = db.query(Project).filter(Project.id == snapshot.project_id).first()
        if not project:
            raise HTTPException(
                status_code=404, detail=f"Проект {snapshot.project_id} не найден"
            )

        if strategy == "ask":
            current = SnapshotService.get_current(db, project.id)
            if current:
                current_manifest = SnapshotService._get_current_manifest(db, project.id)
                if current_manifest != snapshot.files_manifest:
                    return {
                        "warning": True,
                        "message": "Есть несохранённые изменения",
                        "options": ["preserve", "overwrite", "cancel"],
                    }

        chats = db.query(Chat).filter(Chat.project_id == project.id).all()
        if not chats:
            raise HTTPException(
                status_code=404, detail=f"У проекта {project.id} нет чатов"
            )

        chat_ids = [c.id for c in chats]

        current_manifest = SnapshotService._get_current_manifest(db, project.id)
        target_manifest = snapshot.files_manifest

        applied_files = []
        failed_files = []
        deleted_files = []

        files_to_remove = set(current_manifest.keys()) - set(target_manifest.keys())

        # 1. Удаление файлов, которых нет в целевом манифесте
        for filename in files_to_remove:
            # Находим версию файла
            version = (
                db.query(FileVersion)
                .join(Chat, FileVersion.chat_id == Chat.id)
                .filter(
                    Chat.project_id == project.id,
                    FileVersion.filename == filename,
                    FileVersion.is_current == True,
                )
                .first()
            )

            if not version:
                continue

            if version.file_type == "generated":
                try:
                    # Удаляем с диска
                    full_path = safe_join(project.folder_path, filename)
                    if os.path.exists(full_path):
                        os.remove(full_path)

                    # Помечаем все версии файла как неактивные
                    # Находим ID всех версий файла в проекте
                    version_ids = (
                        db.query(FileVersion.id)
                        .join(Chat, FileVersion.chat_id == Chat.id)
                        .filter(
                            Chat.project_id == project.id,
                            FileVersion.filename == filename,
                        )
                        .all()
                    )
                    ids = [v[0] for v in version_ids]
                    if ids:
                        db.query(FileVersion).filter(FileVersion.id.in_(ids)).update(
                            {"is_current": False}, synchronize_session=False
                        )

                    deleted_files.append(filename)

                except Exception as e:
                    logger.error(f"Ошибка удаления файла {filename}: {e}")
                    failed_files.append({"filename": filename, "reason": str(e)})
            else:
                # uploaded или synced — только помечаем в БД
                # Находим ID всех версий файла в проекте
                version_ids = (
                    db.query(FileVersion.id)
                    .join(Chat, FileVersion.chat_id == Chat.id)
                    .filter(
                        Chat.project_id == project.id,
                        FileVersion.filename == filename,
                    )
                    .all()
                )
                ids = [v[0] for v in version_ids]
                if ids:
                    db.query(FileVersion).filter(FileVersion.id.in_(ids)).update(
                        {"is_current": False}, synchronize_session=False
                    )

                logger.info(
                    f"Файл {filename} помечен как неактивный (тип: {version.file_type})"
                )

        # 2. Восстановление/обновление файлов из целевого манифеста
        for filename, content_hash in target_manifest.items():
            current_hash = current_manifest.get(filename)

            if current_hash == content_hash and filename not in files_to_remove:
                continue

            version = (
                db.query(FileVersion)
                .filter(
                    FileVersion.chat_id.in_(chat_ids),
                    FileVersion.filename == filename,
                    FileVersion.content_hash == content_hash,
                )
                .first()
            )

            if not version:
                logger.warning(f"Файл не найден: {filename}, хеш: {content_hash}")
                failed_files.append(
                    {"filename": filename, "reason": "Файл не найден в БД"}
                )
                continue

            try:
                # Записываем на диск
                full_path = safe_join(project.folder_path, filename)
                os.makedirs(os.path.dirname(full_path), exist_ok=True)
                with open(full_path, "w", encoding="utf-8") as f:
                    f.write(version.content)

                # Помечаем все версии файла как неактивные
                version_ids = (
                    db.query(FileVersion.id)
                    .join(Chat, FileVersion.chat_id == Chat.id)
                    .filter(
                        Chat.project_id == project.id,
                        FileVersion.filename == filename,
                    )
                    .all()
                )
                ids = [v[0] for v in version_ids]
                if ids:
                    db.query(FileVersion).filter(FileVersion.id.in_(ids)).update(
                        {"is_current": False}, synchronize_session=False
                    )

                # Делаем эту версию текущей
                version.is_current = True
                applied_files.append(filename)

            except IOError as e:
                logger.error(f"Ошибка записи файла {full_path}: {e}")
                failed_files.append(
                    {"filename": filename, "reason": f"Ошибка записи: {str(e)}"}
                )

        # 3. Обновляем текущий снимок
        db.query(Snapshot).filter(Snapshot.project_id == project.id).update(
            {"is_current": False}
        )

        snapshot.is_current = True

        # 4. Обновляем prev_id для следующих снимков
        db.query(Snapshot).filter(
            Snapshot.project_id == project.id,
            Snapshot.sequence_number > snapshot.sequence_number,
        ).update({"prev_id": snapshot.id})

        db.commit()
        return {
            "status": "restored",
            "snapshot_id": snapshot.id,
            "applied_files": applied_files,
            "deleted_files": deleted_files,
            "failed_files": failed_files,
        }

    @staticmethod
    def move_to(db: Session, snapshot_id: int) -> dict:
        return SnapshotService.restore(db, snapshot_id, strategy="overwrite")

    @staticmethod
    def rollback_to_previous(db: Session, project_id: int) -> dict:
        current = SnapshotService.get_current(db, project_id)
        if not current:
            raise HTTPException(
                status_code=404, detail="Нет текущего снимка для отката"
            )

        previous = SnapshotService.get_previous(db, project_id)
        if not previous:
            raise HTTPException(
                status_code=404, detail="Нет предыдущего снимка для отката"
            )

        return SnapshotService.restore(db, previous.id, strategy="overwrite")

    @staticmethod
    def forward_to_next(db: Session, project_id: int) -> dict:
        current = SnapshotService.get_current(db, project_id)
        if not current:
            raise HTTPException(
                status_code=404, detail="Нет текущего снимка для перехода"
            )

        next_snapshot = SnapshotService.get_next(db, project_id)
        if not next_snapshot:
            raise HTTPException(
                status_code=404, detail="Нет следующего снимка для перехода"
            )

        return SnapshotService.restore(db, next_snapshot.id, strategy="overwrite")

    @staticmethod
    def delete(db: Session, snapshot_id: int):
        snapshot = SnapshotService.get_by_id(db, snapshot_id)

        if snapshot.level != 1:
            raise HTTPException(
                status_code=400, detail="Можно удалять только ручные снимки (level=1)"
            )

        project_id = snapshot.project_id

        if snapshot.is_current:
            prev = (
                db.query(Snapshot)
                .filter(Snapshot.project_id == project_id, Snapshot.id != snapshot_id)
                .order_by(Snapshot.sequence_number.desc())
                .first()
            )

            if prev:
                prev.is_current = True

                next_snap = (
                    db.query(Snapshot)
                    .filter(
                        Snapshot.project_id == project_id,
                        Snapshot.sequence_number > snapshot.sequence_number,
                    )
                    .order_by(Snapshot.sequence_number.asc())
                    .first()
                )

                if next_snap:
                    next_snap.prev_id = prev.id

        db.delete(snapshot)
