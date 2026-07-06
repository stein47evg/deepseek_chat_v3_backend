# Pydantic схемы для эндпоинта генерации.
from pydantic import BaseModel
from typing import Optional, List


class GenerateRequest(BaseModel):
    # Схема запроса на генерацию.
    query: str
    system_prompt_id: Optional[int] = None
    selected_files: Optional[List[str]] = []
    model: Optional[str] = "flash"  # flash | pro
    reasoning: Optional[bool] = True
    temperature: Optional[float] = 0.7


class GenerateResponse(BaseModel):
    # Схема ответа на генерацию.
    message_id: int
    content: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    cost: float
