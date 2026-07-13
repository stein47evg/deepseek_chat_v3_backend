from pydantic import BaseModel
from typing import Optional, List


class UnifiedFileResponse(BaseModel):
    path: str
    name: str
    size: int
    modified: Optional[float] = None
    modified_iso: Optional[str] = None
    in_database: bool = False
    version_id: Optional[int] = None
    content: Optional[str] = None
    language: Optional[str] = None
    file_type: Optional[str] = None
    is_current: bool = False
    applied: bool = False
    is_allowed: bool = True
    is_directory: bool = False


class UnifiedFilesResponse(BaseModel):
    project_id: int
    project_name: str
    folder_path: str
    files: List[UnifiedFileResponse]
    total: int
    in_database_count: int
    not_in_database_count: int
