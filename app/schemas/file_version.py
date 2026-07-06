# Pydantic схемы для версий файлов.
from datetime import datetime
from pydantic import BaseModel
from typing import Optional


class FileVersionResponse(BaseModel):
    # Схема ответа с данными версии файла.
    id: int
    chat_id: int
    message_id: Optional[int]
    filename: str
    content: str
    language: Optional[str]
    file_type: str
    is_current: bool
    applied: bool
    created_at: datetime

    class Config:
        from_attributes = True


class ApplyRequest(BaseModel):
    # Схема для применения версии на диск.
    chat_id: int


class MakeCurrentRequest(BaseModel):
    # Схема для выбора версии как текущей.
    chat_id: int
