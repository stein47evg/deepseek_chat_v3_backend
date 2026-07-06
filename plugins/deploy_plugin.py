#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Плагин для развертывания приложения из упакованных файлов.
"""

import os
import re
import sys
import argparse
import glob

try:
    from plugins.base_plugin import BasePlugin
except ModuleNotFoundError:
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from plugins.base_plugin import BasePlugin


class DeployPlugin(BasePlugin):
    def __init__(self):
        super().__init__()
        self.name = "DeployPlugin"
        self.version = "1.0.0"
        self.description = "Развертывание из упакованных файлов"
        self.deployed_files = []

    def get_menu_items(self):
        return [
            {
                "icon": "🚀",
                "name": "Распаковать все source файлы",
                "args": {"auto": True},
            },
            {
                "icon": "🚀",
                "name": "Распаковать конкретный source файл",
                "args": {"interactive": True},
            },
        ]

    def get_info(self):
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "enabled": self.enabled,
        }

    def find_source_files(self):
        if not os.path.exists("source"):
            return []
        pattern = "source/source*.py"
        found_files = glob.glob(pattern)

        def sort_key(filename):
            basename = os.path.basename(filename)
            if basename == "source.py":
                return (0, basename)
            match = re.search(r"source(\d+)\.py", basename)
            if match:
                return (1, int(match.group(1)))
            return (2, basename)

        found_files.sort(key=sort_key)
        return found_files

    def extract_files_from_source(self, source_file):
        if not os.path.exists(source_file):
            print(f"❌ Файл {source_file} не найден!")
            return False
        try:
            with open(source_file, "r", encoding="utf-8") as f:
                content = f.read()
            pattern = (
                r"# ======== FILE: (.*?) ========(.*?)# ======== END FILE: \1 ========"
            )
            matches = re.findall(pattern, content, re.DOTALL)
            return matches
        except Exception as e:
            print(f"❌ Ошибка: {e}")
            return False

    def uncomment_readme(self, content):
        lines = content.split("\n")
        result = []
        for line in lines:
            if line.startswith("# "):
                result.append(line[2:])
            elif line == "#":
                result.append("")
            else:
                result.append(line)
        return "\n".join(result)

    def create_directories(self, file_path):
        directory = os.path.dirname(file_path)
        if directory and not os.path.exists(directory):
            os.makedirs(directory, exist_ok=True)
            print(f"📂 Создана: {directory}")

    def deploy_file(self, file_path, content):
        try:
            self.create_directories(file_path)
            content = content.strip() + "\n"
            if file_path == "README.md":
                content = self.uncomment_readme(content)
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
            self.deployed_files.append(file_path)
            return True
        except Exception as e:
            print(f"❌ Ошибка {file_path}: {e}")
            return False

    def deploy_single_file(self, source_file):
        print(f"🚀 Развертывание: {source_file}")
        print("=" * 50)

        files = self.extract_files_from_source(source_file)
        if not files:
            return False

        success = 0
        total = len(files)
        for file_path, content in files:
            if self.deploy_file(file_path, content):
                print(f"✅ {file_path}")
                success += 1
            else:
                print(f"❌ {file_path}")

        print("=" * 50)
        print(f"📊 {success}/{total} файлов")
        return success == total

    def deploy_all_files(self):
        source_files = self.find_source_files()
        if not source_files:
            print("❌ Нет файлов source/source*.py")
            return False

        print(f"🔍 Найдено: {len(source_files)}")
        for f in source_files:
            print(f"   - {f}")

        total = 0
        success = True
        for source_file in source_files:
            print(f"\n{'=' * 60}")
            if self.deploy_single_file(source_file):
                total += 1
            else:
                success = False

        print(f"\n📊 Обработано: {total}/{len(source_files)}")
        return success

    def execute(self, *args, **kwargs):
        auto = kwargs.get("auto", False)
        interactive = kwargs.get("interactive", False)

        if auto:
            return self.deploy_all_files()
        elif interactive:
            print_status("❓", "Введите имя source файла", "info")
            print("Пример: source/source1.py")
            source_file = input("👉 ").strip()
            if source_file:
                return self.deploy_single_file(source_file)
            return False
        else:
            return self.deploy_all_files()


def print_status(icon, text, status="info"):
    colors = {
        "success": "\033[92m",
        "error": "\033[91m",
        "warning": "\033[93m",
        "info": "\033[94m",
        "process": "\033[96m",
    }
    reset = "\033[0m"
    print(f"{colors.get(status, reset)}{icon} {text}{reset}")


if __name__ == "__main__":
    plugin = DeployPlugin()
    plugin.execute()
