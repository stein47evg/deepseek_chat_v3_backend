# Pydantic схемы для проектов.
from datetime import datetime
from pydantic import BaseModel


class ProjectCreate(BaseModel):
    # Схема для создания проекта.
    name: str
    folder_path: str


class ProjectResponse(BaseModel):
    # Схема ответа с данными проекта.
    id: int
    name: str
    folder_path: str
    created_at: datetime

    class Config:
        from_attributes = True
