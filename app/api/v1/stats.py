"""
Эндпоинты для статистики.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.config import Settings
from app.models.chat import Chat
from app.models.project import Project
from app.models.message import Message
from app.models.snapshot import Snapshot
from app.models.file_version import FileVersion
from app.models.system_prompt import SystemPrompt
from app.schemas.stats import StatsResponse, TokenCountRequest, TokenCountResponse
from app.services.token_counter import count_tokens, calculate_cost

router = APIRouter(prefix="/stats", tags=["stats"])


@router.get("/chats/{chat_id}", response_model=StatsResponse)
def get_chat_stats(chat_id: int, db: Session = Depends(get_db)):
    """Получить статистику чата."""
    chat = db.query(Chat).filter(Chat.id == chat_id).first()
    if not chat:
        raise HTTPException(status_code=404, detail=f"Чат {chat_id} не найден")

    messages = db.query(Message).filter(Message.chat_id == chat_id).all()
    file_versions = db.query(FileVersion).filter(FileVersion.chat_id == chat_id).all()

    return {
        "total_input_tokens": chat.total_input_tokens or 0,
        "total_output_tokens": chat.total_output_tokens or 0,
        "total_tokens": (chat.total_input_tokens or 0)
        + (chat.total_output_tokens or 0),
        "total_cost": chat.total_cost * Settings.RUBLE_RATE or 0.0,
        "messages_count": len(messages),
        "files_generated": len(
            [v for v in file_versions if v.file_type == "generated"]
        ),
    }


@router.get("/projects/{project_id}", response_model=StatsResponse)
def get_project_stats(project_id: int, db: Session = Depends(get_db)):
    """Получить статистику проекта."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail=f"Проект {project_id} не найден")

    chats = db.query(Chat).filter(Chat.project_id == project_id).all()
    snapshots = db.query(Snapshot).filter(Snapshot.project_id == project_id).all()

    return {
        "total_input_tokens": project.total_input_tokens or 0,
        "total_output_tokens": project.total_output_tokens or 0,
        "total_tokens": (project.total_input_tokens or 0)
        + (project.total_output_tokens or 0),
        "total_cost": project.total_cost * Settings.RUBLE_RATE or 0.0,
        "chats_count": len(chats),
        "snapshots_count": len(snapshots),
    }


@router.post("/chats/{chat_id}/context-tokens", response_model=TokenCountResponse)
def count_context_tokens(
    chat_id: int, request: TokenCountRequest, db: Session = Depends(get_db)
):
    """Подсчитать количество токенов в контексте перед отправкой."""
    chat = db.query(Chat).filter(Chat.id == chat_id).first()
    if not chat:
        raise HTTPException(status_code=404, detail=f"Чат {chat_id} не найден")

    total = 0
    breakdown = {"system_prompt": 0, "history": 0, "files": 0, "query": 0}

    # 1. Системный промпт (берём дефолтный)
    default_prompt = (
        db.query(SystemPrompt).filter(SystemPrompt.is_default == True).first()
    )
    if default_prompt:
        total += count_tokens(default_prompt.content)
        breakdown["system_prompt"] = count_tokens(default_prompt.content)

    # 2. История
    history = (
        db.query(Message)
        .filter(Message.chat_id == chat.id)
        .order_by(Message.created_at.desc())
        .limit(request.history_limit)
        .all()
    )

    for msg in reversed(history):
        tokens = count_tokens(msg.content)
        total += tokens
        breakdown["history"] += tokens

    # 3. Файлы
    for filename in request.selected_files:
        version = (
            db.query(FileVersion)
            .filter(
                FileVersion.chat_id == chat.id,
                FileVersion.filename == filename,
                FileVersion.is_current == True,
            )
            .first()
        )
        if version:
            tokens = count_tokens(version.content)
            total += tokens
            breakdown["files"] += tokens

    # 4. Запрос
    query_tokens = count_tokens(request.query)
    total += query_tokens
    breakdown["query"] = query_tokens

    return {
        "total_tokens": total,
        "breakdown": breakdown,
        "files_count": len(request.selected_files),
        "history_count": len(history),
        "estimated_cost": calculate_cost(total, 1000, "flash"),
    }
