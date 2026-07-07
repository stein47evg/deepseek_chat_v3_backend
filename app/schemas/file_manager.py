from pydantic import BaseModel
from typing import Optional, List


class DiskFileResponse(BaseModel):
    """Схема для файла на диске."""
    id: Optional[int] = None
    path: str
    name: str
    size: int
    modified: float
    isDirectory: bool
    isInDatabase: bool = False
    isAllowed: bool = True

    class Config:
        from_attributes = True


class DeleteFileResponse(BaseModel):
    """Схема ответа на удаление файла."""
    status: str
    path: str
    was_in_database: bool
    message: str
    versions_deleted: Optional[int] = 0


class FlattenHistoryResponse(BaseModel):
    """Схема ответа на сброс истории."""
    status: str
    new_snapshot_id: int
    deleted_snapshots: int
    deleted_versions: int
    preserved_files: int
    message: str
