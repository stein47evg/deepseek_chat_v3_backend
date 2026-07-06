# Pydantic схемы для снимков.
from datetime import datetime
from pydantic import BaseModel
from typing import Optional, Dict


class SnapshotCreate(BaseModel):
    # Схема для создания ручного снимка.
    name: str
    description: Optional[str] = None


class SnapshotResponse(BaseModel):
    # Схема ответа с данными снимка.
    id: int
    project_id: int
    prev_id: Optional[int]
    sequence_number: int
    level: int
    type: str
    name: Optional[str]
    description: Optional[str]
    files_manifest: Dict[str, str]
    is_current: bool
    created_at: datetime

    class Config:
        from_attributes = True


class RestoreRequest(BaseModel):
    # Схема для восстановления снимка.
    strategy: str = "ask"  # ask | preserve | overwrite
