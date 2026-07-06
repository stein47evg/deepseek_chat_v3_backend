"""
Утилиты для работы с файловой системой.
"""
import os
from typing import List, Tuple
from app.core.config import settings
from app.core.exceptions import InvalidPathError, FileTooLargeError


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
