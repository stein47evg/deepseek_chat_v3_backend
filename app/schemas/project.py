from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class ProjectCreate(BaseModel):
    name: str
    folder_path: str


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    folder_path: Optional[str] = None


class ProjectResponse(BaseModel):
    id: int
    name: str
    folder_path: str
    created_at: datetime

    class Config:
        from_attributes = True
