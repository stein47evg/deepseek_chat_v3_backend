"""
Утилиты для парсинга ответов ИИ.
"""
import re
from typing import List, Dict


def extract_file_refs(content: str) -> List[Dict[str, str]]:
    """
    Извлекает ссылки на файлы из текста сообщения.
    Используется на фронте для отображения файлов.
    
    Аргументы:
        content: Текст сообщения с маркерами ### FILE_REF:
    Возвращает:
        Список словарей {file_id, filename}
    """
    pattern = r'### FILE_REF: (\d+) (.*?)(?=\n|$)'
    refs = []

    for match in re.finditer(pattern, content):
        refs.append({
            "file_id": int(match.group(1)),
            "filename": match.group(2).strip()
        })

    return refs
