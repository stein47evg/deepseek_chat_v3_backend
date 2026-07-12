import asyncio
import uuid
from datetime import datetime
from typing import Dict, Optional
from fastapi import HTTPException

class GenerationManager:
    # Менеджер активных задач генерации
    
    def __init__(self):
        self.active_tasks: Dict[str, dict] = {}
        self.cancelled_tasks: set = set()
    
    def create_task(self, chat_id: int, task: asyncio.Task) -> str:
        # Создаёт новую задачу и возвращает task_id
        task_id = str(uuid.uuid4())
        self.active_tasks[task_id] = {
            "task": task,
            "chat_id": chat_id,
            "started_at": datetime.now(),
            "cancelled": False
        }
        return task_id
    
    def cancel_task(self, task_id: str) -> bool:
        # Отменяет задачу по task_id
        if task_id not in self.active_tasks:
            return False
        
        task_info = self.active_tasks[task_id]
        if task_info["cancelled"]:
            return False
        
        task_info["cancelled"] = True
        task_info["task"].cancel()
        self.cancelled_tasks.add(task_id)
        return True
    
    def is_cancelled(self, task_id: str) -> bool:
        # Проверяет, отменена ли задача
        return task_id in self.cancelled_tasks
    
    def remove_task(self, task_id: str):
        # Удаляет задачу из активных
        if task_id in self.active_tasks:
            del self.active_tasks[task_id]
        if task_id in self.cancelled_tasks:
            self.cancelled_tasks.remove(task_id)
    
    def get_task_status(self, task_id: str) -> Optional[dict]:
        # Возвращает статус задачи
        if task_id in self.active_tasks:
            task_info = self.active_tasks[task_id]
            return {
                "task_id": task_id,
                "status": "cancelled" if task_info["cancelled"] else "running",
                "chat_id": task_info["chat_id"],
                "started_at": task_info["started_at"].isoformat()
            }
        return None
    
    def get_active_tasks(self) -> list:
        # Возвращает список активных задач
        return [
            {
                "task_id": task_id,
                "chat_id": info["chat_id"],
                "started_at": info["started_at"].isoformat(),
                "cancelled": info["cancelled"]
            }
            for task_id, info in self.active_tasks.items()
        ]
    
    def cleanup_completed(self):
        # Очищает завершённые задачи (вызывается периодически)
        completed_tasks = []
        for task_id, info in self.active_tasks.items():
            if info["task"].done():
                completed_tasks.append(task_id)
        
        for task_id in completed_tasks:
            self.remove_task(task_id)


# Глобальный экземпляр менеджера
generation_manager = GenerationManager()
