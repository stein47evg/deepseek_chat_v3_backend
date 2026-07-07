"""
Утилиты для работы с файловой системой.
"""
import os
from typing import List, Tuple, Dict, Any
from app.core.config import settings
from app.core.exceptions import InvalidPathError, FileTooLargeError


# Игнорируемые папки и файлы
IGNORED_PATTERNS = [
    ".git", "node_modules", "__pycache__", ".venv", "venv",
    ".idea", ".vscode", "dist", "build", ".next", "coverage",
    "*.pyc", "*.pyo", "*.so", "*.dll", "*.exe",
    "*.log", "*.tmp", "*.cache", ".DS_Store", "Thumbs.db"
]


def is_ignored(path: str) -> bool:
    """
    Проверяет, нужно ли игнорировать файл/папку.
    
    Аргументы:
        path: Путь к файлу или папке
    Возвращает:
        True если нужно игнорировать, иначе False
    """
    name = os.path.basename(path)
    for pattern in IGNORED_PATTERNS:
        if pattern.startswith("*"):
            if name.endswith(pattern[1:]):
                return True
        elif pattern in name or name == pattern:
            return True
    return False


def scan_directory_for_disk(directory: str, show_ignored: bool = False) -> List[Dict[str, Any]]:
    """
    Сканирует директорию и возвращает список файлов для файлового менеджера.
    
    Аргументы:
        directory: Путь к директории
        show_ignored: Показывать игнорируемые файлы
    Возвращает:
        Список словарей с информацией о файлах
    """
    result = []
    directory = os.path.abspath(directory)
    
    for root, dirs, files in os.walk(directory):
        # Фильтруем игнорируемые папки
        if not show_ignored:
            dirs[:] = [d for d in dirs if not is_ignored(os.path.join(root, d))]
        
        for file in files:
            file_path = os.path.join(root, file)
            rel_path = os.path.relpath(file_path, directory)
            
            # Фильтруем игнорируемые файлы
            if not show_ignored and is_ignored(rel_path):
                continue
            
            try:
                stat = os.stat(file_path)
                result.append({
                    "path": rel_path.replace("\\", "/"),
                    "name": file,
                    "size": stat.st_size,
                    "modified": stat.st_mtime,
                    "isDirectory": False,
                })
            except (OSError, IOError):
                continue
    
    return result


def safe_join(base_path: str, filename: str) -> str:
    """
    Безопасное соединение путей с защитой от directory traversal.
    
    Аргументы:
        base_path: Абсолютный путь к папке проекта
        filename: Относительный путь к файлу
    Возвращает:
        Полный безопасный путь
    Исключение:
        InvalidPathError: При попытке выйти за пределы проекта
    """
    base_abs = os.path.abspath(base_path)
    full_path = os.path.abspath(os.path.join(base_abs, filename))

    if not full_path.startswith(base_abs + os.sep) and full_path != base_abs:
        raise InvalidPathError(filename)

    return full_path


def is_allowed_file(filename: str) -> bool:
    """
    Проверяет, разрешён ли тип файла для загрузки.
    
    Аргументы:
        filename: Имя файла с расширением
    Возвращает:
        True если разрешён, иначе False
    """
    _, ext = os.path.splitext(filename)
    return ext in settings.ALLOWED_EXTENSIONS


def validate_file_size(content: bytes) -> None:
    """
    Проверяет размер файла на превышение лимита.
    
    Аргументы:
        content: Содержимое файла в байтах
    Исключение:
        FileTooLargeError: При превышении лимита
    """
    if len(content) > settings.MAX_FILE_SIZE:
        raise FileTooLargeError(len(content), settings.MAX_FILE_SIZE)


def scan_directory(directory: str, ignore_patterns: List[str] = None) -> List[Tuple[str, str]]:
    """
    Рекурсивно сканирует директорию и возвращает все текстовые файлы.
    
    Аргументы:
        directory: Путь к директории
        ignore_patterns: Список паттернов для игнорирования
    Возвращает:
        Список кортежей (относительный_путь, содержимое)
    """
    if ignore_patterns is None:
        ignore_patterns = [".git", "node_modules", "__pycache__", ".venv", "venv"]

    result = []
    directory = os.path.abspath(directory)

    for root, dirs, files in os.walk(directory):
        # Игнорируем системные папки
        dirs[:] = [d for d in dirs if d not in ignore_patterns]

        for file in files:
            full_path = os.path.join(root, file)
            rel_path = os.path.relpath(full_path, directory)

            # Проверяем расширение
            if not is_allowed_file(rel_path):
                continue

            try:
                with open(full_path, "r", encoding="utf-8") as f:
                    content = f.read()
                result.append((rel_path, content))
            except (UnicodeDecodeError, IOError):
                # Пропускаем бинарные и недоступные файлы
                continue

    return result
