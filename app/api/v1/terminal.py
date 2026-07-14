"""
Эндпоинт для эмулятора консоли.
"""
import asyncio
import logging
import os
import shutil
import sys
import subprocess
from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/terminal", tags=["terminal"])


class ExecuteRequest(BaseModel):
    command: str
    cwd: Optional[str] = None
    shell: Optional[str] = "powershell"


class ExecuteResponse(BaseModel):
    output: str
    error: str
    code: int


def find_powershell() -> Optional[str]:
    """Находит путь к PowerShell."""
    possible_paths = [
        "powershell.exe",
        "pwsh.exe",
        "pwsh",
        "C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe",
        "C:\\Program Files\\PowerShell\\7\\pwsh.exe",
        "/usr/bin/pwsh",
        "/opt/microsoft/powershell/7/pwsh"
    ]
    
    for path in possible_paths:
        if shutil.which(path):
            logger.info(f"Найден PowerShell: {shutil.which(path)}")
            return shutil.which(path)
    
    if sys.platform == "win32":
        try:
            result = subprocess.run(
                ["where", "powershell"],
                capture_output=True,
                text=True
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip().split("\n")[0]
        except Exception:
            pass
    
    return None


def find_cmd() -> Optional[str]:
    """Находит путь к CMD."""
    if sys.platform == "win32":
        cmd_paths = ["cmd.exe", "C:\\Windows\\System32\\cmd.exe"]
        for path in cmd_paths:
            if shutil.which(path):
                return shutil.which(path)
            if os.path.exists(path):
                return path
    return None


def build_command(shell: str, command: str) -> tuple:
    """Собирает команду для выполнения."""
    if shell == "powershell":
        shell_path = find_powershell()
        if not shell_path:
            raise HTTPException(
                status_code=500,
                detail="PowerShell не найден в системе."
            )
        return shell_path, ["-Command", command]
    
    elif shell == "cmd":
        shell_path = find_cmd()
        if not shell_path:
            raise HTTPException(
                status_code=500,
                detail="CMD не найден в системе."
            )
        return shell_path, ["/c", command]
    
    elif shell == "bash":
        shell_path = shutil.which("bash")
        if not shell_path:
            raise HTTPException(
                status_code=500,
                detail="Bash не найден в системе."
            )
        return shell_path, ["-c", command]
    
    else:
        raise HTTPException(
            status_code=400,
            detail=f"Неподдерживаемый shell: {shell}"
        )


@router.post("/execute", response_model=ExecuteResponse)
async def execute_command(request: ExecuteRequest):
    """Выполняет команду в консоли и возвращает результат."""
    try:
        # ✅ Логируем все параметры запроса
        logger.info("=" * 80)
        logger.info("📥 ПОЛУЧЕН ЗАПРОС НА ВЫПОЛНЕНИЕ КОМАНДЫ")
        logger.info("=" * 80)
        logger.info(f"  command: {request.command}")
        logger.info(f"  shell:   {request.shell}")
        logger.info(f"  cwd:     {request.cwd or os.getcwd()}")
        logger.info("=" * 80)

        shell_path, shell_args = build_command(request.shell, request.command)
        
        logger.info(f"Используется shell: {shell_path}")
        logger.info(f"Аргументы shell: {shell_args}")

        # На Windows используем subprocess с asyncio.to_thread
        if sys.platform == "win32":
            def run_sync():
                try:
                    result = subprocess.run(
                        [shell_path] + shell_args,
                        capture_output=True,
                        cwd=request.cwd or os.getcwd(),
                        timeout=300
                    )
                    return result
                except subprocess.TimeoutExpired:
                    raise HTTPException(
                        status_code=408,
                        detail="Превышено время выполнения команды (5 минут)"
                    )
            
            # Запускаем в отдельном потоке
            result = await asyncio.to_thread(run_sync)
            
            if sys.platform == "win32":
                output = result.stdout.decode('cp1251', errors='ignore')
                error = result.stderr.decode('cp1251', errors='ignore')
            else:
                output = result.stdout.decode('utf-8', errors='ignore')
                error = result.stderr.decode('utf-8', errors='ignore')
            
            logger.info(f"Команда выполнена, код: {result.returncode}")
            logger.info(f"Вывод: {len(output)} символов")
            if error:
                logger.warning(f"Ошибки: {error[:200]}...")
            
            return ExecuteResponse(
                output=output,
                error=error,
                code=result.returncode
            )
        
        else:
            # Linux/Mac: используем asyncio.create_subprocess_exec
            process = await asyncio.create_subprocess_exec(
                shell_path,
                *shell_args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=request.cwd or os.getcwd(),
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=300
                )
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                raise HTTPException(
                    status_code=408,
                    detail="Превышено время выполнения команды (5 минут)"
                )

            output = stdout.decode('utf-8', errors='ignore')
            error = stderr.decode('utf-8', errors='ignore')

            logger.info(f"Команда выполнена, код: {process.returncode}")
            logger.info(f"Вывод: {len(output)} символов")
            if error:
                logger.warning(f"Ошибки: {error[:200]}...")

            return ExecuteResponse(
                output=output,
                error=error,
                code=process.returncode
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка выполнения команды: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def terminal_health():
    """Проверка доступности терминала."""
    shells = {}
    
    ps = find_powershell()
    shells["powershell"] = ps is not None
    
    cmd = find_cmd()
    shells["cmd"] = cmd is not None
    
    bash = shutil.which("bash")
    shells["bash"] = bash is not None
    
    return {
        "status": "ok",
        "available_shells": shells
    }
