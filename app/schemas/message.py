from datetime import datetime
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from app.schemas.file_version import FileVersionResponse


class MessageResponse(BaseModel):
    id: int
    chat_id: int
    role: str
    content: str
    is_complete: bool = True
    partial_content: Optional[str] = None
    context_data: Optional[Dict[str, Any]] = None
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    total_tokens: Optional[int] = None
    cost: Optional[float] = None
    created_at: datetime
    file_versions: List[FileVersionResponse] = []

    class Config:
        from_attributes = True


class ApplyFileResult(BaseModel):
    filename: str
    status: str
    error: Optional[str] = None


class ApplyFilesResponse(BaseModel):
    status: str
    message_id: int
    files_applied: int
    files_failed: int
    snapshot_id: Optional[int] = None
    files: List[ApplyFileResult]
