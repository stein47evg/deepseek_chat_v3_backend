from pydantic import BaseModel
from typing import Optional, List


class GenerateRequest(BaseModel):
    query: str
    system_prompt_id: Optional[int] = None
    selected_files: Optional[List[str]] = []
    model: Optional[str] = "flash"
    reasoning: Optional[bool] = True
    temperature: Optional[float] = 0.7
    max_tokens: Optional[int] = 8192
    use_stream: Optional[bool] = True


class GenerateResponse(BaseModel):
    message_id: int
    content: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    cost: float
