#!/usr/bin/env python3

"""
Плагин для упаковки проекта.
Полностью сохраняет логику pack_app.py.
"""

import argparse
import os
import sys

try:
    from plugins.base_plugin import BasePlugin
except ModuleNotFoundError:
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from plugins.base_plugin import BasePlugin


class PackPlugin(BasePlugin):
    """
    Плагин для упаковки проекта в source/source.py
    """

    def __init__(self):
        super().__init__()
        self.name = "PackPlugin"
        self.version = "1.0.0"
        self.description = "Упаковка проекта в source файлы"

    def get_menu_items(self):
        """
        Возвращает пункты меню для плагина.
        """
        return [{"icon": "📦", "name": "Упаковать проект", "args": {}}]

    def get_info(self):
        """
        Возвращает информацию о плагине.
        """
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "enabled": self.enabled,
        }

    def find_project_files(self):
        """
        Автоматически находит все файлы проекта для упаковки.
        """
        print("🔍 Ищу файлы проекта...")

        # Паттерны для включения (расширения файлов)
        include_extensions = {
            ".py",
            ".json",
            ".yaml",
            ".yml",
            ".md",
            ".txt",
            ".js",
            ".html",
            ".css",
            ".cfg",
            ".toml",
            ".ps1",
        }

        # Директории для исключения
        exclude_dirs = {
            "__pycache__",
            ".git",
            ".vscode",
            ".idea",
            "venv",
            "env",
            ".venv",
            ".env",
            "node_modules",
            "dist",
            "build",
            "logs",
            "temp",
            "tmp",
            ".tmp",
            "архив",
            "migrations",
            "plugins",
            "promts",
            "tests",
        }

        # Файлы для исключения
        exclude_files = {
            "project.py",
            "pack_app.py",
            "deploy_app.py",
            "source.py",
            "source1.py",
            "source2.py",
            "source3.py",
            "source4.py",
            "source5.py",
            "source6.py",
            "source7.py",
            "source8.py",
            "source9.py",
            "source10.py",
            "all_templates.txt",
            "Задачи.txt",
            "readme1.md",
        }

        all_files = []

        # Рекурсивно обходим все директории
        for root, dirs, files in os.walk("."):
            # Пропускаем скрытые директории и исключенные папки
            dirs[:] = [
                d for d in dirs if not d.startswith(".") and d not in exclude_dirs
            ]

            for file in files:
                file_path = os.path.join(root, file)
                rel_path = os.path.relpath(file_path)

                # Пропускаем скрытые файлы
                if file.startswith("."):
                    continue

                # Пропускаем исключенные файлы
                if file in exclude_files:
                    continue

                # Проверяем расширение файла
                _, ext = os.path.splitext(file)
                if ext.lower() in include_extensions:
                    all_files.append(rel_path)

        # Также включаем специальные файлы без расширения
        special_files = [
            ".gitignore",
            ".dockerignore",
            "Dockerfile",
            "docker-compose.yml",
        ]
        for special_file in special_files:
            if os.path.exists(special_file):
                all_files.append(special_file)

        # Убираем дубликаты и сортируем
        return sorted(set(all_files))

    def comment_readme(self, content):
        """
        Добавляет символы комментариев к каждой строке README.
        """
        lines = content.split("\n")
        commented_lines = []

        for line in lines:
            if line.strip():  # Не пустая строка
                commented_lines.append(f"# {line}")
            else:  # Пустая строка
                commented_lines.append("#")

        return "\n".join(commented_lines)

    def pack_application(self):
        """
        Упаковывает приложение в source/source.py
        """
        print("📦 Упаковываю приложение...")

        # Автоматически находим файлы
        files_to_pack = self.find_project_files()

        if not files_to_pack:
            print("❌ Не найдено файлов для упаковки!")
            return False

        print(f"📁 Найдено файлов: {len(files_to_pack)}")
        for file_path in files_to_pack:
            print(f"   📄 {file_path}")

        packed_content = ""
        success_count = 0

        for file_path in files_to_pack:
            try:
                with open(file_path, encoding="utf-8") as f:
                    content = f.read().strip()

                # Для README добавляем комментарии
                if file_path.lower() == "readme.md":
                    content = self.comment_readme(content)

                packed_content += f"# ======== FILE: {file_path} ========\n"
                packed_content += f"{content}\n"
                packed_content += f"# ======== END FILE: {file_path} ========\n\n"

                print(f"✅ Упакован: {file_path}")
                success_count += 1

            except UnicodeDecodeError:
                print(f"⚠️  Пропущен (бинарный): {file_path}")
            except Exception as e:
                print(f"❌ Ошибка чтения {file_path}: {e}")

        # Создаём папку source, если её нет
        os.makedirs("source", exist_ok=True)

        # Сохраняем упакованный файл в папку source
        with open("source/source.py", "w", encoding="utf-8") as f:
            f.write(packed_content)

        print("\n🎉 Приложение упаковано в: source/source.py")
        print(f"📦 Размер: {os.path.getsize('source/source.py')} байт")
        print(f"📊 Файлов успешно упаковано: {success_count}/{len(files_to_pack)}")

        return True

    def show_file_list(self):
        """
        Просто показывает список файлов без упаковки.
        """
        files = self.find_project_files()
        print("\n📋 Полный список файлов для упаковки:")
        print("=" * 60)
        for i, file_path in enumerate(files, 1):
            size = os.path.getsize(file_path) if os.path.exists(file_path) else 0
            print(f"{i:2d}. {file_path} ({size} байт)")
        print("=" * 60)
        print(f"Всего файлов: {len(files)}")
        return True

    def execute(self, *args, **kwargs):
        """
        Основной метод выполнения плагина.
        Поддерживает аргументы:
            - list: только показать список файлов
            - pack: выполнить упаковку (по умолчанию)
        """
        action = kwargs.get("action", "pack")

        if action == "list":
            return self.show_file_list()
        # pack
        return self.pack_application()


# ========== АВТОНОМНЫЙ РЕЖИМ ==========
def main():
    """
    Основная функция для автономной работы плагина.
    Полностью сохраняет логику исходного pack_app.py.
    """
    parser = argparse.ArgumentParser(description="Упаковка приложения")
    parser.add_argument(
        "--list", action="store_true", help="Только показать список файлов"
    )
    parser.add_argument("--pack", action="store_true", help="Выполнить упаковку")
    parser.add_argument(
        "--test", action="store_true", help="Создать тестовую структуру"
    )

    args = parser.parse_args()

    plugin = PackPlugin()

    if args.test:
        print("🧪 Создаю тестовую структуру...")
        plugin.create_test_structure()
        print("\n✅ Тестовая структура создана!")
        plugin.show_file_list()
    elif args.list:
        plugin.show_file_list()
    elif args.pack:
        plugin.pack_application()
    else:
        # По умолчанию показываем список
        plugin.show_file_list()
        print("\n💡 Команды:")
        print("   python pack_plugin.py --list   - показать список файлов")
        print("   python pack_plugin.py --pack   - выполнить упаковку")
        print("   python pack_plugin.py --test   - создать тестовую структуру")


def create_test_structure():
    """
    Создает тестовую структуру для проверки работы.
    """
    test_structure = {
        "app.py": 'print("Основное приложение")',
        "utils/__init__.py": "# Пакет утилит",
        "utils/helpers.py": 'def help():\n    return "Помощь!"',
        "utils/subfolder/more_utils.py": 'def extra():\n    return "Дополнительно"',
        "config/settings.json": '{"debug": false}',
        "config/database/config.yml": "database:\n  host: localhost",
        "README.md": "# Тестовый проект\n\nОписание проекта",
        "requirements.txt": "python>=3.8",
    }

    for file_path, content in test_structure.items():
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"📝 Создан: {file_path}")


if __name__ == "__main__":
    main()
