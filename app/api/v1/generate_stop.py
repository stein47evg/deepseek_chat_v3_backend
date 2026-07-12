import logging
from fastapi import APIRouter, HTTPException, status
from app.services.generation_manager import generation_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/generate", tags=["generate"])


@router.post("/stop/{task_id}")
async def stop_generation(task_id: str):
    # Останавливает генерацию по task_id
    logger.info(f"Запрос на остановку генерации: {task_id}")
    
    if not generation_manager.active_tasks.get(task_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Задача не найдена или уже завершена"
        )
    
    success = generation_manager.cancel_task(task_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Задача уже остановлена"
        )
    
    logger.info(f"Генерация остановлена: {task_id}")
    return {
        "status": "stopped",
        "task_id": task_id,
        "message": "Генерация остановлена пользователем"
    }


@router.get("/status/{task_id}")
async def get_generation_status(task_id: str):
    # Возвращает статус генерации
    status = generation_manager.get_task_status(task_id)
    if not status:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Задача не найдена"
        )
    return status


@router.get("/active")
async def get_active_tasks():
    # Возвращает список активных задач
    return {
        "tasks": generation_manager.get_active_tasks()
    }
