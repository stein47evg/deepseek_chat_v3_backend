"""
Парсинг ответа ИИ.
Извлекает файлы и сниппеты из текста с маркерами.
"""
import re
import os
from typing import Tuple, List, Dict, Optional


# Маппинг расширений на язык программирования
EXTENSION_TO_LANGUAGE = {
    ".py": "python",
    ".pyi": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".html": "html",
    ".htm": "html",
    ".css": "css",
    ".scss": "scss",
    ".sass": "sass",
    ".less": "less",
    ".json": "json",
    ".jsonc": "json",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".toml": "toml",
    ".md": "markdown",
    ".mdx": "mdx",
    ".sh": "bash",
    ".bash": "bash",
    ".zsh": "bash",
    ".fish": "bash",
    ".c": "c",
    ".h": "c",
    ".cpp": "cpp",
    ".hpp": "cpp",
    ".cc": "cpp",
    ".cxx": "cpp",
    ".rs": "rust",
    ".go": "go",
    ".java": "java",
    ".kt": "kotlin",
    ".kts": "kotlin",
    ".php": "php",
    ".rb": "ruby",
    ".swift": "swift",
    ".sql": "sql",
    "Dockerfile": "dockerfile",
    ".dockerignore": "dockerfile",
    ".gitignore": "gitignore",
    ".gitattributes": "gitignore",
    ".env": "env",
    ".ini": "ini",
    ".cfg": "ini",
    ".conf": "ini",
    ".xml": "xml",
    ".svg": "xml",
    ".graphql": "graphql",
    ".gql": "graphql",
    ".vue": "vue",
    ".svelte": "svelte",
    ".txt": "text",
    ".log": "text",
    ".csv": "csv",
    ".tsv": "csv",
}


def detect_language(filename: str, model_language: Optional[str] = None) -> str:
    """
    Определяет язык для подсветки синтаксиса.
    
    Приоритет:
    1. Язык, указанный моделью (если есть)
    2. Определение по расширению файла
    3. 'text' (по умолчанию)
    
    Args:
        filename: Имя файла с расширением
        model_language: Язык, указанный моделью в маркере
    Returns:
        Название языка для подсветки
    """
    # 1. Приоритет у модели
    if model_language and model_language.strip():
        return model_language.lower()

    # 2. Определение по расширению
    _, ext = os.path.splitext(filename)

    if not ext:
        # Файлы без расширения (например, Dockerfile)
        return EXTENSION_TO_LANGUAGE.get(filename, "text")

    return EXTENSION_TO_LANGUAGE.get(ext.lower(), "text")


def parse_ai_response(content: str) -> Tuple[str, List[Dict]]:
    """
    Парсит ответ ИИ, извлекая текст, файлы и сниппеты.
    
    Аргументы:
        content: Сырой ответ ИИ с маркерами
    Возвращает:
        - text: текст без маркеров
        - files: список словарей {type, filename, language, content}
    
    Типы:
        - 'file': файл для сохранения (маркер ### FILE:)
        - 'snippet': пример кода (маркер ### CODE:)
    """
    # Паттерн для FILE (с именем файла)
    file_pattern = r'### FILE: (.*?)\n```(\w*)\n([\s\S]*?)```'

    # Паттерн для CODE (только язык)
    code_pattern = r'### CODE: (\w*)\n```(\w*)\n([\s\S]*?)```'

    files = []
    text = content

    # 1. Парсим файлы (FILE)
    for match in re.finditer(file_pattern, content):
        filename = match.group(1).strip()
        model_language = match.group(2).strip()
        code = match.group(3).strip()

        # Защита от directory traversal
        if ".." in filename or filename.startswith("/"):
            continue

        language = detect_language(filename, model_language)

        files.append({
            "type": "file",
            "filename": filename,
            "language": language,
            "content": code
        })

        text = text.replace(match.group(0), "")

    # 2. Парсим сниппеты (CODE)
    for match in re.finditer(code_pattern, content):
        language = match.group(1).strip() or "text"
        code = match.group(3).strip()

        files.append({
            "type": "snippet",
            "language": language,
            "content": code,
            "filename": None
        })

        text = text.replace(match.group(0), "")

    # Очищаем текст от лишних переносов
    text = re.sub(r'\n{3,}', '\n\n', text).strip()

    return text, files
