from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class ChatCreate(BaseModel):
    project_id: int
    title: Optional[str] = "Новый чат"


class ChatUpdate(BaseModel):
    title: str


class ChatResponse(BaseModel):
    id: int
    project_id: int
    title: str
    created_at: datetime

    class Config:
        from_attributes = True
