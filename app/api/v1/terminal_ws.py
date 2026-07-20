"""
WebSocket эндпоинт для эмулятора консоли.
"""
import json
import asyncio
import logging
import os
import sys
import subprocess
from typing import Dict, Optional
from fastapi import WebSocket, WebSocketDisconnect, APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.project import Project
from app.models.chat import Chat
from app.services.terminal_service import TerminalService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/terminal", tags=["terminal"])

# Активные WebSocket соединения
active_sessions: Dict[str, Dict] = {}


@router.websocket("/ws/{project_id}/{chat_id}")
async def terminal_websocket(
    websocket: WebSocket,
    project_id: int,
    chat_id: int,
    db: Session = Depends(get_db)
):
    """
    WebSocket для интерактивной консоли.
    
    Формат сообщений от клиента:
    {
        "type": "command",      # выполнение команды
        "command": "ls -la",    # команда
        "shell": "bash",        # bash, powershell, cmd
        "cwd": "/path/to/dir"   # рабочая директория (опционально)
    }
    
    {
        "type": "interrupt"     # прерывание текущей команды
    }
    """
    
    # Проверяем проект и чат
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        await websocket.accept()
        await websocket.send_text(json.dumps({
            "type": "error",
            "data": f"Проект {project_id} не найден"
        }))
        await websocket.close()
        return
    
    chat = db.query(Chat).filter(Chat.id == chat_id).first()
    if not chat:
        await websocket.accept()
        await websocket.send_text(json.dumps({
            "type": "error",
            "data": f"Чат {chat_id} не найден"
        }))
        await websocket.close()
        return
    
    # Принимаем соединение
    await websocket.accept()
    
    # Создаём сессию
    session_id = f"{project_id}_{chat_id}"
    terminal_service = TerminalService(project.folder_path)
    
    active_sessions[session_id] = {
        "websocket": websocket,
        "project_id": project_id,
        "chat_id": chat_id,
        "service": terminal_service,
        "cwd": project.folder_path,
        "running": False
    }
    
    logger.info(f"WebSocket подключен: {session_id}")
    
    try:
        # Отправляем приветствие
        await websocket.send_text(json.dumps({
            "type": "info",
            "data": f"Подключено к проекту: {project.name}",
            "cwd": project.folder_path
        }))
        
        # Основной цикл обработки сообщений
        while True:
            try:
                # Ждём сообщение от клиента
                data = await websocket.receive_text()
                message = json.loads(data)
                
                msg_type = message.get("type")
                
                if msg_type == "command":
                    # Выполняем команду
                    command = message.get("command", "")
                    shell = message.get("shell", "powershell" if sys.platform == "win32" else "bash")
                    cwd = message.get("cwd") or active_sessions[session_id]["cwd"]
                    
                    if not command.strip():
                        await websocket.send_text(json.dumps({
                            "type": "error",
                            "data": "Команда не указана"
                        }))
                        continue
                    
                    # Отмечаем, что команда запущена
                    active_sessions[session_id]["running"] = True
                    
                    # Выполняем команду
                    result = await terminal_service.execute_command(
                        command=command,
                        shell=shell,
                        cwd=cwd
                    )
                    
                    # Отправляем результат
                    if result["output"]:
                        await websocket.send_text(json.dumps({
                            "type": "output",
                            "data": result["output"]
                        }))
                    
                    if result["error"]:
                        await websocket.send_text(json.dumps({
                            "type": "error",
                            "data": result["error"]
                        }))
                    
                    # Отправляем код возврата
                    await websocket.send_text(json.dumps({
                        "type": "code",
                        "data": result["code"]
                    }))
                    
                    # Обновляем текущую директорию (если изменилась)
                    if result["cwd"]:
                        active_sessions[session_id]["cwd"] = result["cwd"]
                    
                    active_sessions[session_id]["running"] = False
                    
                elif msg_type == "interrupt":
                    # Прерываем текущую команду
                    if active_sessions[session_id]["running"]:
                        terminal_service.interrupt()
                        await websocket.send_text(json.dumps({
                            "type": "info",
                            "data": "Команда прервана"
                        }))
                    else:
                        await websocket.send_text(json.dumps({
                            "type": "info",
                            "data": "Нет активной команды"
                        }))
                
                elif msg_type == "ping":
                    # Проверка соединения
                    await websocket.send_text(json.dumps({
                        "type": "pong"
                    }))
                    
                else:
                    await websocket.send_text(json.dumps({
                        "type": "error",
                        "data": f"Неизвестный тип сообщения: {msg_type}"
                    }))
                    
            except json.JSONDecodeError as e:
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "data": f"Ошибка парсинга JSON: {str(e)}"
                }))
                
    except WebSocketDisconnect:
        logger.info(f"WebSocket отключен: {session_id}")
    except Exception as e:
        logger.error(f"Ошибка WebSocket: {e}", exc_info=True)
    finally:
        # Очищаем сессию
        if session_id in active_sessions:
            terminal_service.close()
            del active_sessions[session_id]
        logger.info(f"Сессия очищена: {session_id}")


@router.get("/ws/sessions")
async def get_active_sessions():
    """Получить список активных WebSocket сессий."""
    return {
        "sessions": [
            {
                "id": sid,
                "project_id": data["project_id"],
                "chat_id": data["chat_id"],
                "cwd": data["cwd"],
                "running": data["running"]
            }
            for sid, data in active_sessions.items()
        ]
    }
