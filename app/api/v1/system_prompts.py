"""
Эндпоинты для управления системными промптами.
"""
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.system_prompt import SystemPrompt
from app.schemas.system_prompt import PromptCreate, PromptUpdate, PromptResponse
from app.services.prompt_service import PromptService

router = APIRouter(prefix="/system-prompts", tags=["system-prompts"])


@router.get("/", response_model=List[PromptResponse])
def get_prompts(db: Session = Depends(get_db)):
    """Получить все системные промпты с подсчётом токенов."""
    return PromptService.get_all(db)


@router.get("/quick", response_model=List[PromptResponse])
def get_quick_prompts(db: Session = Depends(get_db)):
    """Получить промпты для быстрого выбора с подсчётом токенов."""
    return PromptService.get_quick(db)


@router.post("/", response_model=PromptResponse, status_code=status.HTTP_201_CREATED)
def create_prompt(data: PromptCreate, db: Session = Depends(get_db)):
    """Создать пользовательский промпт."""
    return PromptService.create(db, data)


@router.put("/{prompt_id}", response_model=PromptResponse)
def update_prompt(prompt_id: int, data: PromptUpdate, db: Session = Depends(get_db)):
    """Обновить пользовательский промпт."""
    return PromptService.update(db, prompt_id, data)


@router.delete("/{prompt_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_prompt(prompt_id: int, db: Session = Depends(get_db)):
    """Удалить пользовательский промпт."""
    PromptService.delete(db, prompt_id)
