#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Плагин для работы с контекстом проекта.
Позволяет создавать новый контекст, выбирать файлы и добавлять их строки.
"""

import os
import sys
import json
import fnmatch
import subprocess
import platform
from pathlib import Path
from typing import List, Set, Dict, Optional, Tuple
from datetime import datetime

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


# ========== ЦВЕТА ДЛЯ КРАСИВОГО ВЫВОДА ==========
class Colors:
    HEADER = "\033[95m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    MAGENTA = "\033[95m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RESET = "\033[0m"


class Icons:
    SUCCESS = "✅"
    ERROR = "❌"
    WARNING = "⚠️"
    INFO = "ℹ️"
    ARROW = "👉"
    EXIT = "🚪"
    PLUGIN = "🔌"
    CONTEXT = "📝"
    COPY = "📋"


class ContextPlugin(BasePlugin):
    """
    Плагин для работы с контекстом проекта.
    """
    
    def __init__(self):
        super().__init__()
        self.name = "ContextPlugin"
        self.version = "1.0.0"
        self.description = "Управление контекстом проекта"
        self.root_path = Path(".").resolve()
        self.context_file = self.root_path / "context.txt"
        self.files: List[Path] = []
        self.selected_file: Optional[Path] = None
        self.selection_history: List[Path] = []
        self.ignored_patterns: Set[str] = set()
        self.included_patterns: Set[str] = set()
        self.excluded_folders: Set[str] = set()
        self.vscode_settings_path = self.root_path / ".vscode" / "settings.json"
    
    def get_menu_items(self):
        """
        Возвращает пункты меню для плагина.
        """
        return [
            {
                'icon': '📝',
                'name': 'Новый контекст (очистить и выбрать файл)',
                'args': {'action': 'new_context'}
            }
        ]
    
    def get_info(self):
        """
        Возвращает информацию о плагине.
        """
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "enabled": self.enabled
        }
    
    def get_quick_commands(self):
        """
        Возвращает команды для быстрого меню.
        """
        return {
            '6': {
                'name': 'Новый контекст',
                'action': self.new_context
            }
        }
    
    # ========== УТИЛИТЫ ==========
    def print_status(self, icon, text, status="info"):
        colors = {
            "success": Colors.GREEN,
            "error": Colors.RED,
            "warning": Colors.YELLOW,
            "info": Colors.BLUE,
            "process": Colors.CYAN,
            "highlight": Colors.MAGENTA,
        }
        print(f"{colors.get(status, Colors.RESET)}{icon} {text}{Colors.RESET}")
    
    def print_info(self, text):
        print(f"{Colors.BLUE}{Icons.INFO}{Colors.RESET} {text}")
    
    def print_separator(self, char="=", length=58):
        print(f"{Colors.DIM}{char * length}{Colors.RESET}")
    
    def print_box(self, text, color=Colors.CYAN, padding=2):
        lines = text.split("\n")
        max_len = max(len(line) for line in lines)
        width = max_len + padding * 2
        print(f"{color}┌{'─' * width}┐{Colors.RESET}")
        for line in lines:
            print(f"{color}│{' ' * padding}{line}{' ' * (max_len - len(line))}{' ' * padding}│{Colors.RESET}")
        print(f"{color}└{'─' * width}┘{Colors.RESET}")
    
    def copy_to_clipboard(self, text):
        """Копирует текст в буфер обмена с правильной кодировкой"""
        try:
            if platform.system() == "Windows":
                if HAS_WIN32CLIPBOARD:
                    win32clipboard.OpenClipboard()
                    win32clipboard.EmptyClipboard()
                    win32clipboard.SetClipboardData(win32con.CF_UNICODETEXT, text)
                    win32clipboard.CloseClipboard()
                    return True
                else:
                    import tempfile
                    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', delete=False, suffix='.txt') as f:
                        f.write(text)
                        temp_file = f.name
                    subprocess.run([
                        'powershell', '-Command',
                        f'Get-Content -Encoding UTF8 "{temp_file}" | Set-Clipboard'
                    ], check=True, capture_output=True)
                    os.unlink(temp_file)
                    return True
            elif platform.system() == "Darwin":
                subprocess.run(["pbcopy"], input=text.encode("utf-8"), check=True)
                return True
            else:
                subprocess.run(["xclip", "-selection", "clipboard"], input=text.encode("utf-8"), check=True)
                return True
        except Exception as e:
            print(f"Ошибка копирования: {e}")
            return False
    
    # ========== ЗАГРУЗКА НАСТРОЕК VS CODE ==========
    def load_vscode_settings(self) -> bool:
        """
        Загружает настройки из .vscode/settings.json
        """
        if not self.vscode_settings_path.exists():
            return False
        
        try:
            with open(self.vscode_settings_path, 'r', encoding='utf-8') as f:
                settings = json.load(f)
            
            files_exclude = settings.get("files.exclude", {})
            search_exclude = settings.get("search.exclude", {})
            all_exclude = {**files_exclude, **search_exclude}
            
            for pattern, enabled in all_exclude.items():
                if enabled:
                    self.ignored_patterns.add(pattern)
                    if pattern.endswith('/') or pattern.endswith('\\'):
                        folder = pattern.rstrip('/\\')
                        self.excluded_folders.add(folder)
            
            file_associations = settings.get("files.associations", {})
            for pattern in file_associations.keys():
                self.included_patterns.add(pattern)
            
            return True
            
        except Exception as e:
            return False
    
    def get_default_ignores(self) -> Set[str]:
        """
        Возвращает стандартные исключения.
        """
        return {
            "__pycache__/",
            "*.pyc",
            ".git/",
            ".vscode/",
            ".idea/",
            "venv/",
            "env/",
            ".venv/",
            ".env/",
            "node_modules/",
            "dist/",
            "build/",
            "logs/",
            "temp/",
            "tmp/",
            ".tmp/",
            "*.log",
            "*.lock",
            "*.pid",
            "*.db",
            "*.sqlite3",
        }
    
    def should_ignore(self, path: Path) -> bool:
        """
        Проверяет, должен ли файл/папка быть проигнорирован.
        """
        rel_path = str(path.relative_to(self.root_path))
        
        for pattern in self.ignored_patterns:
            if fnmatch.fnmatch(rel_path, pattern):
                return True
            if pattern.endswith('/') or pattern.endswith('\\'):
                folder = pattern.rstrip('/\\')
                if folder in rel_path.split(os.sep):
                    return True
        
        default_ignores = self.get_default_ignores()
        for pattern in default_ignores:
            if fnmatch.fnmatch(rel_path, pattern):
                return True
            if pattern.endswith('/') or pattern.endswith('\\'):
                folder = pattern.rstrip('/\\')
                if folder in rel_path.split(os.sep):
                    return True
        
        parts = rel_path.split(os.sep)
        for part in parts:
            if part.startswith('.') and part not in ['.', '..']:
                if part != '.gitignore':
                    return True
        
        if path.is_file():
            try:
                size = path.stat().st_size
                if size > 10 * 1024 * 1024:
                    return True
            except:
                pass
        
        return False
    
    def should_include(self, path: Path) -> bool:
        """
        Проверяет, должен ли файл быть включен.
        """
        default_extensions = {
            '.py', '.pyw', '.pyx', '.pyd',
            '.js', '.jsx', '.ts', '.tsx',
            '.html', '.htm', '.css', '.scss', '.sass', '.less',
            '.json', '.yaml', '.yml', '.toml', '.ini', '.cfg',
            '.md', '.rst', '.txt', '.log',
            '.xml', '.svg', '.png', '.jpg', '.jpeg', '.gif',
            '.ico', '.webp', '.woff', '.woff2', '.ttf', '.eot',
            '.sh', '.bat', '.cmd', '.ps1', '.psm1',
            '.dockerfile', '.conf', '.config',
            '.env', '.example', '.sample',
            '.sql', '.sqlite', '.db',
            '.rst', '.tex', '.pdf',
            '.java', '.kt', '.kts',
            '.go', '.rs', '.c', '.cpp', '.h', '.hpp',
        }
        
        for pattern in self.included_patterns:
            if pattern.startswith('*.'):
                ext = pattern[1:]
                if fnmatch.fnmatch(path.name, ext):
                    return True
        
        if path.suffix.lower() in default_extensions:
            return True
        
        special_files = {
            '.gitignore', '.dockerignore', '.gitattributes',
            'Dockerfile', 'docker-compose.yml', 'docker-compose.yaml',
            'Makefile', 'CMakeLists.txt', 'Cargo.toml',
            'package.json', 'package-lock.json',
            'requirements.txt', 'Pipfile', 'Pipfile.lock',
            'pyproject.toml', 'setup.py', 'setup.cfg',
            'manage.py', 'wsgi.py', 'asgi.py',
            'config.py', 'settings.py', 'constants.py',
            '__init__.py', 'main.py', 'app.py', 'run.py',
            'README.md', 'LICENSE', 'CHANGELOG.md',
            '.env.example', '.env.local', '.env.production',
            '.pre-commit-config.yaml',
        }
        
        if path.name in special_files:
            return True
        
        if path.is_file() and os.access(path, os.X_OK):
            return True
        
        return False
    
    def scan_project(self) -> List[Path]:
        """
        Сканирует проект и возвращает список файлов.
        """
        self.load_vscode_settings()
        self.files = []
        
        for root, dirs, files in os.walk(self.root_path):
            root_path = Path(root)
            dirs[:] = [d for d in dirs if not self.should_ignore(root_path / d)]
            
            for file in files:
                file_path = root_path / file
                if not self.should_ignore(file_path) and self.should_include(file_path):
                    self.files.append(file_path)
        
        self.files.sort()
        return self.files
    
    # ========== ВЫБОР ФАЙЛА ==========
    def select_file_interactive(self) -> Optional[Path]:
        """
        Интерактивный выбор файла из списка.
        """
        if not self.files:
            print("❌ Нет доступных файлов для выбора")
            return None
        
        if self.selected_file:
            self.selection_history.append(self.selected_file)
        
        print("\n" + "=" * 60)
        print("📂 ВЫБОР ФАЙЛА")
        print("=" * 60)
        
        files_per_page = 20
        total_pages = (len(self.files) + files_per_page - 1) // files_per_page
        current_page = 0
        
        while True:
            start_idx = current_page * files_per_page
            end_idx = min(start_idx + files_per_page, len(self.files))
            
            print(f"\n📄 Страница {current_page + 1}/{total_pages} (всего {len(self.files)} файлов)")
            print(f"{Colors.DIM}{'─' * 58}{Colors.RESET}")
            
            for i in range(start_idx, end_idx):
                file_path = self.files[i]
                rel_path = file_path.relative_to(self.root_path)
                size = file_path.stat().st_size if file_path.exists() else 0
                size_str = f"{size / 1024:.1f} KB" if size > 1024 else f"{size} B"
                print(f"  {Colors.GREEN}{i + 1:3d}{Colors.RESET}. {rel_path} {Colors.DIM}({size_str}){Colors.RESET}")
            
            print(f"{Colors.DIM}{'─' * 58}{Colors.RESET}")
            print(f"  {Colors.GREEN}N{Colors.RESET}. Следующая страница")
            print(f"  {Colors.GREEN}P{Colors.RESET}. Предыдущая страница")
            print(f"  {Colors.GREEN}S{Colors.RESET}. Поиск по имени")
            if self.selection_history:
                print(f"  {Colors.GREEN}H{Colors.RESET}. История выбора ({len(self.selection_history)})")
            print(f"  {Colors.GREEN}0{Colors.RESET}. Отмена")
            print()
            
            choice = input(f"{Colors.BOLD}{Icons.ARROW} Выберите номер файла: {Colors.RESET}").strip()
            
            if choice == "0":
                print("❌ Выбор отменен")
                return None
            
            elif choice.upper() == "N":
                if current_page < total_pages - 1:
                    current_page += 1
                else:
                    print("ℹ️ Это последняя страница")
                continue
            
            elif choice.upper() == "P":
                if current_page > 0:
                    current_page -= 1
                else:
                    print("ℹ️ Это первая страница")
                continue
            
            elif choice.upper() == "S":
                search_pattern = input("🔍 Введите имя файла (часть пути): ").strip()
                if search_pattern:
                    found = [f for f in self.files if search_pattern.lower() in str(f.relative_to(self.root_path)).lower()]
                    if found:
                        print(f"\n✅ Найдено файлов: {len(found)}")
                        for i, f in enumerate(found[:10], 1):
                            print(f"   {i}. {f.relative_to(self.root_path)}")
                        if len(found) > 10:
                            print(f"   ... и еще {len(found) - 10} файлов")
                    else:
                        print("❌ Файлы не найдены")
                continue
            
            elif choice.upper() == "H" and self.selection_history:
                print(f"\n📜 История выбора ({len(self.selection_history)} файлов):")
                for i, f in enumerate(self.selection_history[-5:], 1):
                    print(f"   {i}. {f.relative_to(self.root_path)}")
                print(f"  {Colors.GREEN}0{Colors.RESET}. Назад")
                hist_choice = input(f"{Colors.BOLD}{Icons.ARROW} Выберите файл из истории: {Colors.RESET}").strip()
                if hist_choice == "0":
                    continue
                try:
                    idx = int(hist_choice) - 1
                    if 0 <= idx < len(self.selection_history):
                        self.selected_file = self.selection_history[idx]
                        print(f"\n✅ Выбран файл из истории: {self.selected_file.relative_to(self.root_path)}")
                        return self.selected_file
                except ValueError:
                    pass
                continue
            
            try:
                idx = int(choice) - 1
                if 0 <= idx < len(self.files):
                    self.selected_file = self.files[idx]
                    print(f"\n✅ Выбран файл: {self.selected_file.relative_to(self.root_path)}")
                    return self.selected_file
                else:
                    print(f"❌ Неверный номер. Введите число от 1 до {len(self.files)}")
            except ValueError:
                print("❌ Неверный ввод")
    
    # ========== РАБОТА С КОНТЕКСТОМ ==========
    def clear_context(self):
        """
        Очищает файл контекста.
        """
        try:
            with open(self.context_file, 'w', encoding='utf-8') as f:
                f.write("")
            print(f"✅ Контекст очищен: {self.context_file.name}")
            return True
        except Exception as e:
            print(f"❌ Ошибка очистки контекста: {e}")
            return False
    
    def parse_context_command(self, command: str, total_lines: int) -> List[Tuple[int, int]]:
        """
        Парсит команду добавления контекста.
        Возвращает список кортежей (start_line, count).
        """
        command = command.strip()
        ranges = []
        
        if command == "*":
            return [(1, total_lines)]
        
        parts = [p.strip() for p in command.split(',') if p.strip()]
        
        for part in parts:
            if ':' in part:
                try:
                    start_str, count_str = part.split(':')
                    start = int(start_str.strip())
                    count = int(count_str.strip())
                    if start < 1 or start > total_lines:
                        print(f"⚠️ Пропущено: строка {start} вне диапазона (1-{total_lines})")
                        continue
                    if count < 1:
                        print(f"⚠️ Пропущено: количество должно быть > 0")
                        continue
                    ranges.append((start, count))
                except ValueError:
                    print(f"⚠️ Пропущено: неверный формат '{part}'")
                continue
            
            if '-' in part:
                try:
                    start_str, end_str = part.split('-')
                    start = int(start_str.strip())
                    end = int(end_str.strip())
                    if start < 1 or start > total_lines or end < 1 or end > total_lines:
                        print(f"⚠️ Пропущено: строки {start}-{end} вне диапазона")
                        continue
                    if start > end:
                        start, end = end, start
                    ranges.append((start, end - start + 1))
                except ValueError:
                    print(f"⚠️ Пропущено: неверный формат '{part}'")
                continue
            
            try:
                line_num = int(part)
                if line_num < 1 or line_num > total_lines:
                    print(f"⚠️ Пропущено: строка {line_num} вне диапазона")
                    continue
                ranges.append((line_num, 1))
            except ValueError:
                print(f"⚠️ Пропущено: неверный формат '{part}'")
        
        return ranges
    
    def show_context_preview(self, file_path: Path, ranges: List[Tuple[int, int]], lines: List[str]) -> bool:
        """
        Показывает предварительный просмотр и запрашивает подтверждение.
        """
        print("\n" + "=" * 60)
        print("📋 ПРЕДПРОСМОТР ДОБАВЛЯЕМЫХ СТРОК")
        print("=" * 60)
        print(f"📄 Файл: {file_path.relative_to(self.root_path)}")
        print(f"{Colors.DIM}{'─' * 58}{Colors.RESET}")
        
        all_preview = []
        for start, count in ranges:
            for i in range(count):
                line_idx = start + i - 1
                if line_idx < len(lines):
                    all_preview.append((line_idx + 1, lines[line_idx].rstrip()))
        
        if len(all_preview) <= 5:
            for line_num, content in all_preview:
                print(f"  {Colors.GREEN}{line_num:3d}{Colors.RESET}|{content}")
        else:
            for line_num, content in all_preview[:2]:
                print(f"  {Colors.GREEN}{line_num:3d}{Colors.RESET}|{content}")
            print(f"  {Colors.DIM}{'─' * 58}{Colors.RESET}")
            for line_num, content in all_preview[-2:]:
                print(f"  {Colors.GREEN}{line_num:3d}{Colors.RESET}|{content}")
            print(f"\n  {Colors.DIM}... и еще {len(all_preview) - 4} строк{Colors.RESET}")
        
        print(f"{Colors.DIM}{'─' * 58}{Colors.RESET}")
        print(f"📊 Всего строк для добавления: {len(all_preview)}")
        
        print(f"\n{Icons.ARROW} Добавить эти строки в контекст? [y/N]")
        confirm = input().strip().lower()
        return confirm in ["y", "yes", "да"]
    
    def add_to_context(self, file_path: Path, ranges: List[Tuple[int, int]]) -> bool:
        """
        Добавляет строки из файла в контекст.
        """
        if not file_path.exists():
            print(f"❌ Файл не найден: {file_path}")
            return False
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
        except Exception as e:
            print(f"❌ Ошибка чтения файла: {e}")
            return False
        
        if not ranges:
            print("❌ Не найдено строк для добавления")
            return False
        
        if not self.show_context_preview(file_path, ranges, lines):
            print("❌ Добавление отменено")
            return False
        
        context_entry = []
        context_entry.append(f"=== Файл: {file_path.relative_to(self.root_path)} ===")
        
        for start, count in ranges:
            for i in range(count):
                line_idx = start + i - 1
                if line_idx < len(lines):
                    line_content = lines[line_idx].rstrip()
                    context_entry.append(f"{line_idx + 1}|{line_content}")
        
        context_entry.append("")
        
        try:
            with open(self.context_file, 'a', encoding='utf-8') as f:
                f.write('\n'.join(context_entry) + '\n')
            print(f"✅ Добавлено {len(context_entry) - 2} строк в {self.context_file.name}")
            return True
        except Exception as e:
            print(f"❌ Ошибка записи в контекст: {e}")
            return False
    
    def add_context_interactive(self, file_path: Path):
        """
        Интерактивное добавление строк в контекст.
        """
        if not file_path.exists():
            print(f"❌ Файл не найден: {file_path}")
            return
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            total_lines = len(lines)
        except Exception as e:
            print(f"❌ Ошибка чтения файла: {e}")
            return
        
        print("\n" + "=" * 60)
        print("📝 ДОБАВЛЕНИЕ КОНТЕКСТА")
        print("=" * 60)
        print(f"📄 Файл: {file_path.relative_to(self.root_path)}")
        print(f"📊 Всего строк: {total_lines}")
        print()
        print("  Команды:")
        print("    *          - добавить все строки")
        print("    5          - добавить строку 5")
        print("    2-4        - добавить строки 2,3,4")
        print("    3:2        - добавить 2 строки начиная с 3 (3,4)")
        print("    2,3,4      - добавить строки 2,3,4")
        print("    2 - 4      - добавить строки 2,3,4 (с пробелами)")
        print()
        
        command = input(f"{Colors.BOLD}{Icons.ARROW} Введите команду: {Colors.RESET}").strip()
        
        if not command:
            print("❌ Команда не введена")
            return
        
        ranges = self.parse_context_command(command, total_lines)
        if not ranges:
            print("❌ Не найдено строк для добавления")
            return
        
        self.add_to_context(file_path, ranges)
    
    # ========== ДЕЙСТВИЯ С ФАЙЛОМ ==========
    def copy_context_to_clipboard(self) -> bool:
        """
        Копирует содержимое файла контекста в буфер обмена.
        """
        if not self.context_file.exists():
            print(f"❌ Файл контекста не найден: {self.context_file.name}")
            return False
        
        try:
            with open(self.context_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            if not content.strip():
                print("⚠️ Файл контекста пуст")
                return False
            
            if self.copy_to_clipboard(content):
                size = len(content)
                size_str = f"{size / 1024:.2f} KB" if size > 1024 else f"{size} B"
                print(f"✅ Контекст скопирован в буфер обмена ({size_str})")
                return True
            else:
                print("❌ Ошибка копирования в буфер обмена")
                return False
        except Exception as e:
            print(f"❌ Ошибка чтения файла контекста: {e}")
            return False
    
    def show_file_metadata(self, file_path: Path):
        """
        Показывает метаданные файла.
        """
        print("\n" + "=" * 60)
        print("📊 МЕТАДАННЫЕ ФАЙЛА")
        print("=" * 60)
        print(f"   Имя: {file_path.name}")
        print(f"   Путь: {file_path}")
        print(f"   Относительный путь: {file_path.relative_to(self.root_path)}")
        print(f"   Расширение: {file_path.suffix or 'нет'}")
        if file_path.exists():
            stat = file_path.stat()
            size_str = f"{stat.st_size / 1024:.2f} KB" if stat.st_size > 1024 else f"{stat.st_size} B"
            print(f"   Размер: {size_str} ({stat.st_size} байт)")
            print(f"   Создан: {datetime.fromtimestamp(stat.st_ctime)}")
            print(f"   Изменен: {datetime.fromtimestamp(stat.st_mtime)}")
            print(f"   Доступ: {datetime.fromtimestamp(stat.st_atime)}")
        print("=" * 60)
    
    def show_file_actions(self) -> bool:
        """
        Показывает меню действий с выбранным файлом.
        Возвращает False если нужно выйти из меню.
        """
        if not self.selected_file:
            print("❌ Файл не выбран")
            return False
        
        file_path = self.selected_file
        rel_path = file_path.relative_to(self.root_path)
        
        while True:
            print("\n" + "=" * 60)
            print(f"📄 РАБОТА С ФАЙЛОМ: {rel_path}")
            print("=" * 60)
            print(f"  {Colors.GREEN}1{Colors.RESET}. Добавить контекст")
            print(f"  {Colors.GREEN}2{Colors.RESET}. Скопировать контекст в буфер")
            print(f"  {Colors.GREEN}3{Colors.RESET}. Показать метаданные")
            print(f"  {Colors.GREEN}4{Colors.RESET}. Вернуться к списку")
            print(f"  {Colors.GREEN}0{Colors.RESET}. Выйти")
            print()
            
            action = input(f"{Colors.BOLD}{Icons.ARROW} Выберите действие: {Colors.RESET}").strip()
            
            if action == "0":
                print("👋 До свидания!")
                return False
            
            elif action == "1":
                self.add_context_interactive(file_path)
                # После добавления контекста возвращаемся к меню выбора файла
                # Без ожидания Enter
            
            elif action == "2":
                self.copy_context_to_clipboard()
                print(f"\n{Icons.ARROW} Нажмите Enter для продолжения...")
                input()
            
            elif action == "3":
                self.show_file_metadata(file_path)
                print(f"\n{Icons.ARROW} Нажмите Enter для продолжения...")
                input()
            
            elif action == "4":
                self.selected_file = None
                return True
            
            else:
                print("❌ Неверный выбор")
                print(f"\n{Icons.ARROW} Нажмите Enter для продолжения...")
                input()
        
        return True
    
    # ========== ОСНОВНОЙ МЕТОД ==========
    def new_context(self):
        """
        Создает новый контекст: очищает context.txt и переходит к выбору файла.
        """
        print("\n" + "=" * 60)
        print("📝 НОВЫЙ КОНТЕКСТ")
        print("=" * 60)
        
        # Очищаем контекст
        if not self.clear_context():
            return False
        
        # Сканируем проект
        self.scan_project()
        
        if not self.files:
            print("❌ Нет доступных файлов для выбора")
            return False
        
        # Выбор файла
        while True:
            selected = self.select_file_interactive()
            
            if selected is None:
                print("\n❌ Выбор отменен")
                break
            
            print(f"\n✅ Выбран файл: {selected.relative_to(self.root_path)}")
            
            # Показываем меню действий
            continue_to_list = self.show_file_actions()
            
            if not continue_to_list:
                break
        
        return True
    
    def execute(self, *args, **kwargs):
        """
        Основной метод выполнения плагина.
        """
        action = kwargs.get('action', 'new_context')
        
        if action == 'new_context':
            return self.new_context()
        else:
            return self.new_context()


# ========== АВТОНОМНЫЙ РЕЖИМ ==========
def main():
    """
    Основная функция для автономной работы плагина.
    """
    import argparse
    parser = argparse.ArgumentParser(description='Управление контекстом проекта')
    parser.add_argument('--new', action='store_true', help='Создать новый контекст')
    args = parser.parse_args()
    
    plugin = ContextPlugin()
    
    if args.new:
        success = plugin.new_context()
    else:
        success = plugin.new_context()
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
