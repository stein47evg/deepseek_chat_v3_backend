# Pydantic схемы для чатов.
from datetime import datetime
from pydantic import BaseModel
from typing import Optional


class ChatCreate(BaseModel):
    # Схема для создания чата.
    project_id: Optional[int] = None  # <-- Optional
    title: Optional[str] = "Новый чат"


class ChatResponse(BaseModel):
    # Схема ответа с данными чата.
    id: int
    project_id: Optional[int] = None  # <-- Optional
    title: str
    created_at: datetime

    class Config:
        from_attributes = True
