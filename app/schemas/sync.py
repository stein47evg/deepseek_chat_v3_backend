# Pydantic схемы для синхронизации.
from pydantic import BaseModel
from typing import List, Optional


class SyncResponse(BaseModel):
    # Схема ответа на синхронизацию.
    changes: List[dict]
    snapshot_id: Optional[int]
