# Pydantic схемы для системных промптов.
from datetime import datetime
from pydantic import BaseModel
from typing import Optional


class PromptCreate(BaseModel):
    # Схема для создания пользовательского промпта.
    name: str
    content: str
    is_quick: bool = False


class PromptUpdate(BaseModel):
    # Схема для обновления пользовательского промпта.
    name: Optional[str] = None
    content: Optional[str] = None
    is_quick: Optional[bool] = None


class PromptResponse(BaseModel):
    # Схема ответа с данными промпта.
    id: int
    name: str
    content: str
    is_default: bool
    is_custom: bool
    is_quick: bool
    created_at: datetime

    class Config:
        from_attributes = True
