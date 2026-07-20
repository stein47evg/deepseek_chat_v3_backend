"""
Сервис для выполнения команд в терминале.
Поддерживает стриминг вывода и прерывание команд.
"""
import asyncio
import logging
import os
import sys
import subprocess
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class TerminalService:
    """Сервис для выполнения команд в терминале."""

    def __init__(self, default_cwd: str):
        self.default_cwd = default_cwd
        self.current_process: Optional[asyncio.subprocess.Process] = None
        self.current_cwd = default_cwd

    async def execute_command(
        self,
        command: str,
        shell: str = "powershell" if sys.platform == "win32" else "bash",
        cwd: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Выполняет команду и возвращает результат.
        
        Args:
            command: Команда для выполнения
            shell: powershell, cmd, bash
            cwd: Рабочая директория
        
        Returns:
            dict: {"output": str, "error": str, "code": int, "cwd": str}
        """
        try:
            # Определяем команду для запуска
            if shell == "powershell":
                shell_cmd = "powershell.exe" if sys.platform == "win32" else "pwsh"
                shell_args = ["-Command", command]
            elif shell == "cmd":
                shell_cmd = "cmd.exe"
                shell_args = ["/c", command]
            elif shell == "bash":
                shell_cmd = "bash"
                shell_args = ["-c", command]
            else:
                return {
                    "output": "",
                    "error": f"Неподдерживаемый shell: {shell}",
                    "code": 1,
                    "cwd": self.current_cwd
                }

            # Рабочая директория
            working_dir = cwd or self.current_cwd
            if not os.path.exists(working_dir):
                working_dir = self.default_cwd

            logger.info(f"Выполнение команды: {command} в {working_dir}")

            # Запускаем процесс
            self.current_process = await asyncio.create_subprocess_exec(
                shell_cmd,
                *shell_args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=working_dir
            )

            # Ждём завершения с таймаутом
            try:
                stdout, stderr = await asyncio.wait_for(
                    self.current_process.communicate(),
                    timeout=300  # 5 минут
                )
            except asyncio.TimeoutError:
                self.current_process.kill()
                await self.current_process.wait()
                return {
                    "output": "",
                    "error": "Превышено время выполнения команды (5 минут)",
                    "code": -1,
                    "cwd": working_dir
                }

            # Декодируем вывод
            if sys.platform == "win32":
                output = stdout.decode('cp866', errors='ignore')
                error = stderr.decode('cp866', errors='ignore')
            else:
                output = stdout.decode('utf-8', errors='ignore')
                error = stderr.decode('utf-8', errors='ignore')

            # Обновляем текущую директорию
            self.current_cwd = working_dir

            return {
                "output": output,
                "error": error,
                "code": self.current_process.returncode or 0,
                "cwd": self.current_cwd
            }

        except Exception as e:
            logger.error(f"Ошибка выполнения команды: {e}", exc_info=True)
            return {
                "output": "",
                "error": str(e),
                "code": 1,
                "cwd": self.current_cwd
            }
        finally:
            self.current_process = None

    def interrupt(self):
        """Прерывает текущую выполняемую команду."""
        if self.current_process:
            try:
                self.current_process.kill()
                logger.info("Команда прервана")
            except Exception as e:
                logger.error(f"Ошибка прерывания команды: {e}")

    def close(self):
        """Закрывает сервис и завершает все процессы."""
        if self.current_process:
            try:
                self.current_process.kill()
            except Exception:
                pass
