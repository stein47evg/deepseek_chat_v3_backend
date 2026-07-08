from fastapi import APIRouter
from pydantic import BaseModel
from app.services.token_counter import count_tokens as ct

router = APIRouter(prefix="/tokens", tags=["tokens"])

class TokenCountRequest(BaseModel):
    content: str

@router.post("/count")
def count_tokens(request: TokenCountRequest):
    """Подсчёт количества токенов в тексте."""
    return {"tokens": ct(request.content)}
