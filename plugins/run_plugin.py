#!/usr/bin/env python3

"""
Плагин для умного запуска проекта с логированием.
При неудачном запуске автоматически копирует лог в буфер обмена.
"""

import os
import platform
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# Попытка импорта win32clipboard для Windows
try:
    if platform.system() == "Windows":
        import win32clipboard
        import win32con

        HAS_WIN32CLIPBOARD = True
    else:
        HAS_WIN32CLIPBOARD = False
except ImportError:
    HAS_WIN32CLIPBOARD = False

try:
    from plugins.base_plugin import BasePlugin
except ModuleNotFoundError:
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from plugins.base_plugin import BasePlugin


class RunPlugin(BasePlugin):
    def __init__(self):
        super().__init__()
        self.name = "RunPlugin"
        self.version = "1.0.0"
        self.description = "Умный запуск проекта с логированием"

    def get_menu_items(self):
        return [{"icon": "🚀", "name": "Запустить проект (умный запуск)", "args": {}}]

    def get_info(self):
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "enabled": self.enabled,
        }

    def get_timestamp(self):
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def print_status(self, icon, text, status="info"):
        colors = {
            "success": "\033[92m",
            "error": "\033[91m",
            "warning": "\033[93m",
            "info": "\033[94m",
            "process": "\033[96m",
        }
        reset = "\033[0m"
        print(f"{colors.get(status, reset)}{icon} {text}{reset}")

    def print_info(self, text):
        print(f"\033[94mℹ️ {text}\033[0m")

    def print_separator(self, char="=", length=58):
        print(f"\033[2m{char * length}\033[0m")

    def print_box(self, text, color="\033[96m", padding=2):
        lines = text.split("\n")
        max_len = max(len(line) for line in lines)
        width = max_len + padding * 2
        print(f"{color}┌{'─' * width}┐\033[0m")
        for line in lines:
            print(
                f"{color}│{' ' * padding}{line}{' ' * (max_len - len(line))}{' ' * padding}│\033[0m"
            )
        print(f"{color}└{'─' * width}┘\033[0m")

    def get_venv_python(self):
        if platform.system() == "Windows":
            venv_python = "venv\\Scripts\\python.exe"
        else:
            venv_python = "venv/bin/python"
        return venv_python if os.path.exists(venv_python) else None

    def load_env_file(self):
        env_file = Path(".env")
        if not env_file.exists():
            self.print_info("Файл .env не найден")
            return False
        try:
            loaded = 0
            for line in open(env_file, encoding="utf-8"):
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    k, v = line.split("=", 1)
                    k, v = k.strip(), v.strip()
                    if (v.startswith('"') and v.endswith('"')) or (
                        v.startswith("'") and v.endswith("'")
                    ):
                        v = v[1:-1]
                    os.environ[k] = v
                    loaded += 1
            if loaded > 0:
                self.print_status("🔧", f"Загружено {loaded} переменных", "success")
            return True
        except Exception as e:
            self.print_status("❌", f"Ошибка: {e}", "error")
            return False

    def is_port_in_use(self, port):
        import socket

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return False
            except OSError:
                return True

    def find_free_port(self, start_port=5000, max_attempts=10):
        port = start_port
        for _ in range(max_attempts):
            if not self.is_port_in_use(port):
                return port
            port += 1
        return None

    def detect_app_type(self):
        results = []

        # Flask
        flask_files = ["app.py", "application.py", "wsgi.py", "main.py", "run.py"]
        for file in flask_files:
            if os.path.exists(file):
                try:
                    with open(file, encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                        if "Flask" in content and "Flask(" in content:
                            results.append(
                                {
                                    "type": "flask  ",
                                    "entry_file": file,
                                    "port": int(os.environ.get("FLASK_PORT", 5000)),
                                    "priority": 10,
                                }
                            )
                            break
                except:
                    pass

        # Django
        if os.path.exists("manage.py"):
            try:
                with open("manage.py", encoding="utf-8", errors="ignore") as f:
                    if "django" in f.read().lower():
                        results.append(
                            {
                                "type": "django ",
                                "entry_file": "manage.py",
                                "port": int(os.environ.get("DJANGO_PORT", 8000)),
                                "priority": 9,
                            }
                        )
            except:
                pass

        # FastAPI
        fastapi_files = ["main.py", "app.py", "api.py"]
        for file in fastapi_files:
            if os.path.exists(file):
                try:
                    with open(file, encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                        if "FastAPI" in content or "APIRouter" in content:
                            results.append(
                                {
                                    "type": "fastapi",
                                    "entry_file": file,
                                    "port": int(os.environ.get("FASTAPI_PORT", 8000)),
                                    "priority": 8,
                                }
                            )
                            break
                except:
                    pass

        # Node.js
        if os.path.exists("package.json"):
            try:
                import json

                with open("package.json", encoding="utf-8") as f:
                    data = json.load(f)
                    if "scripts" in data and "start" in data["scripts"]:
                        results.append(
                            {
                                "type": "node   ",
                                "entry_file": "package.json",
                                "port": 3000,
                                "priority": 6,
                            }
                        )
            except:
                pass

        # Script
        script_files = ["main.py", "run.py", "app.py", "start.py", "bot.py"]
        for file in script_files:
            if os.path.exists(file):
                results.append(
                    {"type": "script", "entry_file": file, "port": None, "priority": 5}
                )
                break

        if results:
            results.sort(key=lambda x: x["priority"], reverse=True)
            return results[0]
        return None

    def copy_to_clipboard(self, text):
        """Копирует текст в буфер обмена с правильной кодировкой"""
        try:
            if platform.system() == "Windows":
                if HAS_WIN32CLIPBOARD:
                    # Используем win32clipboard для правильной кодировки
                    win32clipboard.OpenClipboard()
                    win32clipboard.EmptyClipboard()
                    # UTF-16 для Windows буфера
                    win32clipboard.SetClipboardData(win32con.CF_UNICODETEXT, text)
                    win32clipboard.CloseClipboard()
                    return True
                # Если win32clipboard не установлен, пробуем через PowerShell
                import tempfile

                with tempfile.NamedTemporaryFile(
                    mode="w", encoding="utf-8", delete=False, suffix=".txt"
                ) as f:
                    f.write(text)
                    temp_file = f.name
                subprocess.run(
                    [
                        "powershell",
                        "-Command",
                        f'Get-Content -Encoding UTF8 "{temp_file}" | Set-Clipboard',
                    ],
                    check=True,
                    capture_output=True,
                )
                os.unlink(temp_file)
                return True
            if platform.system() == "Darwin":
                subprocess.run(["pbcopy"], input=text.encode("utf-8"), check=True)
                return True
            # Linux
            subprocess.run(
                ["xclip", "-selection", "clipboard"],
                input=text.encode("utf-8"),
                check=True,
            )
            return True
        except Exception as e:
            print(f"Ошибка копирования: {e}")
            return False

    def read_log_file(self, filepath):
        """Читает лог-файл"""
        if not os.path.exists(filepath):
            return None
        try:
            with open(filepath, encoding="utf-8") as f:
                return f.read()
        except:
            return None

    def execute(self, *args, **kwargs):
        env = kwargs.get("env", "dev")
        port = kwargs.get("port")

        self.print_status("🚀", f"Запуск (окружение: {env.upper()})...", "process")
        self.print_separator()

        self.load_env_file()

        os.environ["APP_ENV"] = env
        if env == "prod":
            os.environ["FLASK_ENV"] = "production"
        elif env == "staging":
            os.environ["FLASK_ENV"] = "staging"
        else:
            os.environ["FLASK_ENV"] = "development"
            os.environ["FLASK_DEBUG"] = "1"

        venv_python = self.get_venv_python()
        if not venv_python:
            self.print_status("⚠️", "Виртуальное окружение не найдено", "warning")
            self.print_info("Запуск с системным Python")
            python_cmd = sys.executable
        else:
            python_cmd = venv_python

        self.print_separator()

        app_info = self.detect_app_type()
        if not app_info:
            self.print_status("❌", "Не удалось определить тип приложения", "error")
            return False

        if port:
            app_info["port"] = port
        elif app_info["port"] and self.is_port_in_use(app_info["port"]):
            new_port = self.find_free_port(app_info["port"])
            if new_port:
                self.print_status(
                    "⚠️", f"Порт {app_info['port']} занят → {new_port}", "warning"
                )
                app_info["port"] = new_port
                os.environ["PORT"] = str(new_port)
            else:
                self.print_status("❌", "Нет свободных портов", "error")
                return False

        self.print_box(f"🚀 ЗАПУСК: {app_info['type'].upper()}", "\033[92m")
        self.print_info(f"Тип: {app_info['type']}")
        self.print_info(f"Окружение: {env.upper()}")
        self.print_info(f"Файл: {app_info['entry_file']}")
        if app_info["port"]:
            self.print_info(f"Порт: {app_info['port']}")
        self.print_separator()

        # Формирование команды
        if app_info["type"] == "flask":
            os.environ["FLASK_APP"] = app_info["entry_file"]
            if app_info["port"]:
                os.environ["FLASK_RUN_PORT"] = str(app_info["port"])
            cmd = [python_cmd, "-m", "flask", "run", "--host=0.0.0.0"]
            if app_info["port"]:
                cmd.extend(["--port", str(app_info["port"])])
            if env == "prod":
                cmd.append("--no-debugger")

        elif app_info["type"] == "django":
            cmd = [python_cmd, "manage.py", "runserver"]
            if app_info["port"]:
                cmd.append(f"0.0.0.0:{app_info['port']}")

        elif app_info["type"] == "fastapi":
            cmd = [
                python_cmd,
                "-m",
                "uvicorn",
                app_info["entry_file"].replace(".py", ":app"),
            ]
            if app_info["port"]:
                cmd.extend(["--port", str(app_info["port"])])
            cmd.extend(["--host", "0.0.0.0"])
            if env != "prod":
                cmd.append("--reload")

        elif app_info["type"] == "node":
            cmd = ["npm", "start"]

        else:
            cmd = [python_cmd, app_info["entry_file"]]

        if platform.system() == "Windows":
            if cmd[0].endswith("python.exe") or cmd[0].endswith("python"):
                cmd = [cmd[0], "-X", "utf8"] + cmd[1:]

        self.print_info(f"Команда: \033[2m{' '.join(cmd)}\033[0m")
        self.print_separator()
        print("\n\033[92m▶️  Запуск...\033[0m\n")

        if app_info["port"] and app_info["type"] in ["flask", "fastapi"]:
            print(f"\033[96m🌐 http://127.0.0.1:{app_info['port']}\033[0m")
            print("\033[2mCtrl+C для остановки\033[0m\n")

        # Логирование
        log_full = "project.log"
        log_last = "last_run.log"

        full_log = open(log_full, "a", encoding="utf-8")
        full_log.write(f"\n{'=' * 60}\n")
        full_log.write(f"[{self.get_timestamp()}] ЗАПУСК\n")
        full_log.write(f"Окружение: {env.upper()}\n")
        full_log.write(f"Тип: {app_info['type']}\n")
        full_log.write(f"Файл: {app_info['entry_file']}\n")
        if app_info["port"]:
            full_log.write(f"Порт: {app_info['port']}\n")
        full_log.write(f"Команда: {' '.join(cmd)}\n")
        full_log.write(f"{'=' * 60}\n")
        full_log.flush()

        last_log = open(log_last, "w", encoding="utf-8")
        last_log.write(f"{'=' * 60}\n")
        last_log.write(f"[{self.get_timestamp()}] ПОСЛЕДНИЙ ЗАПУСК\n")
        last_log.write(f"Окружение: {env.upper()}\n")
        last_log.write(f"Тип: {app_info['type']}\n")
        last_log.write(f"Файл: {app_info['entry_file']}\n")
        if app_info["port"]:
            last_log.write(f"Порт: {app_info['port']}\n")
        last_log.write(f"Команда: {' '.join(cmd)}\n")
        last_log.write(f"{'=' * 60}\n")
        last_log.flush()

        success = False
        error_occurred = False

        try:
            my_env = os.environ.copy()
            my_env["PYTHONIOENCODING"] = "utf-8"
            my_env["PYTHONUTF8"] = "1"

            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=my_env,
                cwd=os.getcwd(),
            )

            for line in process.stdout:
                line = line.rstrip()
                print(line)
                full_log.write(line + "\n")
                full_log.flush()
                last_log.write(line + "\n")
                last_log.flush()

            process.wait()

            if process.returncode == 0:
                full_log.write(
                    f"\n[{self.get_timestamp()}] УСПЕШНО (код: {process.returncode})\n"
                )
                full_log.write(f"{'=' * 60}\n")
                full_log.close()
                last_log.write(
                    f"\n[{self.get_timestamp()}] УСПЕШНО (код: {process.returncode})\n"
                )
                last_log.write(f"{'=' * 60}\n")
                last_log.close()
                self.print_status("✅", "Завершено успешно", "success")
                success = True
            else:
                full_log.write(
                    f"\n[{self.get_timestamp()}] ОШИБКА (код: {process.returncode})\n"
                )
                full_log.write(f"{'=' * 60}\n")
                full_log.close()
                last_log.write(
                    f"\n[{self.get_timestamp()}] ОШИБКА (код: {process.returncode})\n"
                )
                last_log.write(f"{'=' * 60}\n")
                last_log.close()
                self.print_status("❌", f"Ошибка (код: {process.returncode})", "error")
                error_occurred = True
                success = False

        except KeyboardInterrupt:
            print("\n\n\033[93m⏹️  Остановлено\033[0m")
            full_log.write(f"\n[{self.get_timestamp()}] ОСТАНОВЛЕНО (Ctrl+C)\n")
            full_log.write(f"{'=' * 60}\n")
            full_log.close()
            last_log.write(f"\n[{self.get_timestamp()}] ОСТАНОВЛЕНО (Ctrl+C)\n")
            last_log.write(f"{'=' * 60}\n")
            last_log.close()
            success = True

        except Exception as e:
            self.print_status("❌", f"Ошибка: {e}", "error")
            full_log.write(f"\n[{self.get_timestamp()}] ОШИБКА: {str(e)}\n")
            full_log.write(f"{'=' * 60}\n")
            full_log.close()
            last_log.write(f"\n[{self.get_timestamp()}] ОШИБКА: {str(e)}\n")
            last_log.write(f"{'=' * 60}\n")
            last_log.close()
            error_occurred = True
            success = False

        # ========== АВТОМАТИЧЕСКОЕ КОПИРОВАНИЕ ЛОГА ПРИ ОШИБКЕ ==========
        if error_occurred:
            log_content = self.read_log_file("last_run.log")
            if log_content:
                if self.copy_to_clipboard(log_content):
                    self.print_status(
                        "📋", "Лог ошибки скопирован в буфер обмена", "warning"
                    )
                    print(f"\033[2mРазмер: {len(log_content)} символов\033[0m")
                else:
                    self.print_status(
                        "⚠️", "Не удалось скопировать лог в буфер обмена", "warning"
                    )
                    self.print_info("Установите pywin32: pip install pywin32")

        return success


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--env", default="dev")
    parser.add_argument("--port", type=int)
    args = parser.parse_args()
    plugin = RunPlugin()
    plugin.execute(env=args.env, port=args.port)
