"""
Кастомные исключения для приложения.
"""
from typing import Optional


class AppException(Exception):
    """Базовое исключение приложения."""
    def __init__(self, message: str, code: int = 400, detail: Optional[str] = None):
        self.message = message
        self.code = code
        self.detail = detail
        super().__init__(message)


class FileNotFoundError(AppException):
    """Исключение: файл не найден."""
    def __init__(self, filename: str):
        super().__init__(
            message=f"Файл не найден: {filename}",
            code=404
        )


class ProjectNotFoundError(AppException):
    """Исключение: проект не найден."""
    def __init__(self, project_id: int):
        super().__init__(
            message=f"Проект с ID {project_id} не найден",
            code=404
        )


class ChatNotFoundError(AppException):
    """Исключение: чат не найден."""
    def __init__(self, chat_id: int):
        super().__init__(
            message=f"Чат с ID {chat_id} не найден",
            code=404
        )


class SnapshotNotFoundError(AppException):
    """Исключение: снимок не найден."""
    def __init__(self, snapshot_id: int):
        super().__init__(
            message=f"Снимок с ID {snapshot_id} не найден",
            code=404
        )


class VersionNotFoundError(AppException):
    """Исключение: версия файла не найдена."""
    def __init__(self, version_id: int):
        super().__init__(
            message=f"Версия файла с ID {version_id} не найдена",
            code=404
        )


class FileTooLargeError(AppException):
    """Исключение: файл слишком большой."""
    def __init__(self, size: int, max_size: int):
        super().__init__(
            message=f"Файл слишком большой: {size} байт (макс. {max_size} байт)",
            code=413
        )


class InvalidPathError(AppException):
    """Исключение: недопустимый путь."""
    def __init__(self, path: str):
        super().__init__(
            message=f"Недопустимый путь: {path}",
            code=400
        )


class DeepSeekAPIError(AppException):
    """Исключение: ошибка API DeepSeek."""
    def __init__(self, detail: str):
        super().__init__(
            message="Ошибка при обращении к DeepSeek API",
            code=500,
            detail=detail
        )


class SyncError(AppException):
    """Исключение: ошибка синхронизации."""
    def __init__(self, detail: str):
        super().__init__(
            message="Ошибка синхронизации",
            code=500,
            detail=detail
        )
