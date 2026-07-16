from datetime import datetime
from pydantic import BaseModel
from typing import Optional


class PromptCreate(BaseModel):
    name: str
    content: str
    reminder: Optional[str] = None
    is_quick: bool = False
    strategy: Optional[str] = "flexible"


class PromptUpdate(BaseModel):
    name: Optional[str] = None
    content: Optional[str] = None
    reminder: Optional[str] = None
    is_quick: Optional[bool] = None
    strategy: Optional[str] = None


class PromptResponse(BaseModel):
    id: int
    name: str
    content: str
    reminder: Optional[str] = None
    strategy: str
    is_default: bool
    is_custom: bool
    is_quick: bool
    created_at: datetime
    token_count: Optional[int] = None

    class Config:
        from_attributes = True
