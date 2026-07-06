"""
Утилиты для работы с хешами.
"""
import hashlib


def compute_hash(content: str) -> str:
    """
    Вычисляет SHA-256 хеш содержимого.
    
    Аргументы:
        content: Текстовое содержимое
    Возвращает:
        SHA-256 хеш в виде шестнадцатеричной строки
    """
    return hashlib.sha256(content.encode("utf-8")).hexdigest()
