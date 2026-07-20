"""
Утилиты для работы с файловой системой.
"""

import os
from typing import List, Tuple, Dict, Any
from app.core.config import settings
from app.core.exceptions import InvalidPathError, FileTooLargeError


# Игнорируемые папки и файлы
IGNORED_PATTERNS = [
    ".git",
    "node_modules",
    "__pycache__",
    ".venv",
    "venv",
    ".idea",
    ".vscode",
    "dist",
    "build",
    ".next",
    "coverage",
    "*.pyc",
    "*.pyo",
    "*.so",
    "*.dll",
    "*.exe",
    "*.log",
    "*.tmp",
    "*.cache",
    ".DS_Store",
    "Thumbs.db",
]


def is_ignored(path: str) -> bool:
    """Проверяет, нужно ли игнорировать файл/папку."""
    name = os.path.basename(path)
    for pattern in IGNORED_PATTERNS:
        if pattern.startswith("*"):
            if name.endswith(pattern[1:]):
                return True
        elif pattern in name or name == pattern:
            return True
    return False


def scan_directory_for_disk(
    directory: str, show_ignored: bool = False
) -> List[Dict[str, Any]]:
    """Сканирует директорию и возвращает список файлов для файлового менеджера."""
    result = []
    directory = os.path.abspath(directory)

    for root, dirs, files in os.walk(directory):
        if not show_ignored:
            dirs[:] = [d for d in dirs if not is_ignored(os.path.join(root, d))]

        for file in files:
            file_path = os.path.join(root, file)
            rel_path = os.path.relpath(file_path, directory)

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
    """Безопасное соединение путей с защитой от directory traversal."""
    base_abs = os.path.abspath(base_path)
    full_path = os.path.abspath(os.path.join(base_abs, filename))

    if not full_path.startswith(base_abs + os.sep) and full_path != base_abs:
        raise InvalidPathError(filename)

    return full_path


def is_allowed_file(file_path: str) -> bool:
    """
    Проверяет, разрешён ли файл для загрузки.
    Проверяет расширение и размер файла.
    
    Args:
        file_path: Полный путь к файлу
    
    Returns:
        True если файл разрешён, иначе False
    """
    # Проверяем расширение
    _, ext = os.path.splitext(file_path)
    if ext.lower() not in settings.ALLOWED_EXTENSIONS:
        return False
    
    # Проверяем размер
    try:
        stat = os.stat(file_path)
        if stat.st_size > settings.MAX_FILE_SIZE:
            return False
    except OSError:
        return False
    
    return True


def validate_file_size(content: bytes) -> None:
    """Проверяет размер содержимого на превышение лимита."""
    if len(content) > settings.MAX_FILE_SIZE:
        raise FileTooLargeError(len(content), settings.MAX_FILE_SIZE)


def scan_directory(
    directory: str, ignore_patterns: List[str] = None
) -> List[Tuple[str, str]]:
    """Рекурсивно сканирует директорию и возвращает все текстовые файлы."""
    if ignore_patterns is None:
        ignore_patterns = [".git", "node_modules", "__pycache__", ".venv", "venv"]

    result = []
    directory = os.path.abspath(directory)

    for root, dirs, files in os.walk(directory):
        dirs[:] = [d for d in dirs if d not in ignore_patterns]

        for file in files:
            full_path = os.path.join(root, file)
            rel_path = os.path.relpath(full_path, directory)

            if not is_allowed_file(full_path):
                continue

            try:
                with open(full_path, "r", encoding="utf-8") as f:
                    content = f.read()
                result.append((rel_path, content))
            except (UnicodeDecodeError, IOError):
                continue

    return result
