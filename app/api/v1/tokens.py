from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/tokens", tags=["tokens"])

class TokenCountRequest(BaseModel):
    content: str

@router.post("/count")
def count_tokens(request: TokenCountRequest):
    """Подсчёт количества токенов в тексте (приблизительно)."""
    tokens = len(request.content) // 4
    return {"tokens": tokens}
