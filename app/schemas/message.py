# Pydantic схемы для сообщений.
from datetime import datetime
from pydantic import BaseModel
from typing import Optional, List
from app.schemas.file_version import FileVersionResponse


class MessageResponse(BaseModel):
    # Схема ответа с данными сообщения.
    id: int
    chat_id: int
    role: str
    content: str
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    total_tokens: Optional[int] = None
    cost: Optional[float] = None
    created_at: datetime
    file_versions: List[FileVersionResponse] = []

    class Config:
        from_attributes = True
