# Pydantic схемы для статистики.
from pydantic import BaseModel
from typing import Optional, List


class StatsResponse(BaseModel):
    # Схема ответа со статистикой.
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_tokens: int = 0
    total_cost: float = 0.0
    messages_count: Optional[int] = 0
    files_generated: Optional[int] = 0
    # Для статистики проекта
    chats_count: Optional[int] = 0
    snapshots_count: Optional[int] = 0


class TokenCountRequest(BaseModel):
    # Схема запроса на подсчёт токенов.
    query: str
    selected_files: Optional[List[str]] = []
    history_limit: Optional[int] = 10


class TokenCountResponse(BaseModel):
    # Схема ответа с подсчётом токенов.
    total_tokens: int
    breakdown: dict
    files_count: int
    history_count: int
    estimated_cost: float
