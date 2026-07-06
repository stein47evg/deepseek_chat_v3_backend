#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Плагин для запуска тестов.
"""

import os
import sys
import subprocess

try:
    from plugins.base_plugin import BasePlugin
except ModuleNotFoundError:
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from plugins.base_plugin import BasePlugin


class TestPlugin(BasePlugin):
    def __init__(self):
        super().__init__()
        self.name = "TestPlugin"
        self.version = "1.0.0"
        self.description = "Запуск тестов (pytest/unittest)"

    def get_menu_items(self):
        return [{"icon": "🧪", "name": "Запустить тесты", "args": {}}]

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

    def get_venv_python(self):
        if os.name == "nt":
            venv_python = "venv\\Scripts\\python.exe"
        else:
            venv_python = "venv/bin/python"
        return venv_python if os.path.exists(venv_python) else None

    def execute(self, *args, **kwargs):
        print()
        self.print_status("🧪", "Запуск тестов...", "process")
        print("=" * 58)
        venv_python = self.get_venv_python()
        python_cmd = venv_python if venv_python else sys.executable

        has_pytest = False
        try:
            result = subprocess.run(
                [python_cmd, "-m", "pytest", "--version"],
                capture_output=True,
                timeout=5,
            )
            has_pytest = result.returncode == 0
        except:
            pass

        if has_pytest:
            
            result = subprocess.run([python_cmd, "-m", "pytest", "-v"], cwd=os.getcwd()+'/tests')
        else:
            result = subprocess.run(
                [python_cmd, "-m", "unittest", "discover", "-v"], cwd=os.getcwd()
            )

        if result.returncode == 0:
            self.print_status("✅", "Все тесты пройдены!", "success")
            return True
        else:
            self.print_status("❌", "Некоторые тесты не пройдены", "error")
            return False


if __name__ == "__main__":
    plugin = TestPlugin()
    plugin.execute()
