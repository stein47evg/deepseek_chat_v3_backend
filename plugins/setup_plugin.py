#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Плагин для установки проекта (venv + зависимости).
"""

import os
import sys
import platform
import subprocess
import shutil
import time

try:
    from plugins.base_plugin import BasePlugin
except ModuleNotFoundError:
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from plugins.base_plugin import BasePlugin


class SetupPlugin(BasePlugin):
    def __init__(self):
        super().__init__()
        self.name = "SetupPlugin"
        self.version = "1.0.0"
        self.description = "Установка проекта (venv + зависимости)"

    def get_menu_items(self):
        return [
            {
                "icon": "⚙️",
                "name": "Установить проект (venv + зависимости)",
                "args": {"action": "setup"},
            },
            {
                "icon": "🔄",
                "name": "Переустановить проект (удалить venv)",
                "args": {"action": "reinstall"},
            },
        ]

    def get_info(self):
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "enabled": self.enabled,
        }

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

    def get_venv_python(self):
        if platform.system() == "Windows":
            return "venv\\Scripts\\python.exe"
        return "venv/bin/python"

    def find_pip_in_venv(self):
        if platform.system() == "Windows":
            candidates = ["venv\\Scripts\\pip.exe", "venv\\Scripts\\pip"]
        else:
            candidates = ["venv/bin/pip", "venv/bin/pip3"]
        for candidate in candidates:
            if os.path.exists(candidate):
                return candidate
        return None

    def upgrade_pip(self, pip_path):
        self.print_info("Обновление pip...")
        venv_python = self.get_venv_python()
        if not os.path.exists(venv_python):
            return False
        subprocess.run(
            [venv_python, "-m", "pip", "install", "--upgrade", "pip"],
            capture_output=True,
        )
        return True

    def confirm_action(self, name, details=None):
        print(f"\n\033[93m⚠️ {name}\033[0m")
        if details:
            for d in details:
                print(f"  {d}")
        return input("\nВы уверены? [y/N]: ").strip().lower() in ["y", "yes", "да"]

    def run_setup(self):
        print()
        self.print_status("⚙️", "Установка проекта...", "process")

        if os.path.exists("venv"):
            if not self.confirm_action("Виртуальное окружение уже существует"):
                self.print_info("Отменено")
                return False

        if not os.path.exists("venv"):
            self.print_info("Создание venv...")
            result = subprocess.run(
                [sys.executable, "-m", "venv", "venv"], cwd=os.getcwd()
            )
            if result.returncode != 0:
                self.print_status("❌", "Ошибка создания venv", "error")
                return False
            time.sleep(2)

        pip_path = self.find_pip_in_venv()
        if pip_path:
            self.upgrade_pip(pip_path)

        if os.path.exists("requirements.txt"):
            self.print_info("Установка зависимостей...")
            if pip_path:
                result = subprocess.run(
                    [pip_path, "install", "-r", "requirements.txt"], cwd=os.getcwd()
                )
                if result.returncode != 0:
                    self.print_status("❌", "Ошибка установки", "error")
                    return False
            else:
                self.print_status("❌", "pip не найден", "error")
                return False
        else:
            self.print_info("requirements.txt не найден")

        if not os.path.exists(".env") and os.path.exists(".env.example"):
            shutil.copy(".env.example", ".env")
            self.print_status("✅", "Создан .env из .env.example", "success")

        self.print_status("✅", "Установка завершена", "success")
        return True

    def run_reinstall(self):
        print()
        if not self.confirm_action("ПЕРЕУСТАНОВКА", ["Будет удалено: ./venv/"]):
            self.print_info("Отменено")
            return False

        self.print_status("🔄", "Удаление venv...", "process")
        shutil.rmtree("venv", ignore_errors=True)
        time.sleep(2)
        self.print_status("✅", "venv удалён", "success")
        return self.run_setup()

    def execute(self, *args, **kwargs):
        action = kwargs.get("action", "setup")
        if action == "setup":
            return self.run_setup()
        elif action == "reinstall":
            return self.run_reinstall()
        else:
            return self.run_setup()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--action", default="setup", choices=["setup", "reinstall"])
    args = parser.parse_args()
    plugin = SetupPlugin()
    plugin.execute(action=args.action)
