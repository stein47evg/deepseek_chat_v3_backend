import re
import os
from typing import Tuple, List, Dict, Optional
import logging

logger = logging.getLogger(__name__)

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
    if model_language and model_language.strip():
        return model_language.lower()

    _, ext = os.path.splitext(filename)

    if not ext:
        return EXTENSION_TO_LANGUAGE.get(filename, "text")

    return EXTENSION_TO_LANGUAGE.get(ext.lower(), "text")


def parse_ai_response(content: str) -> Tuple[str, List[Dict]]:
    files = []
    text = content

    file_pattern = r'### ?FILE: ?(.*?)\n*```(\w*)\n([\s\S]*?)```'
    code_pattern = r'### ?CODE: ?(\w*)\n+```(\w*)\n([\s\S]*?)```'

    for match in re.finditer(file_pattern, content):
        filename = match.group(1).strip()
        model_language = match.group(2).strip()
        code = match.group(3).strip()

        if ".." in filename or filename.startswith("/"):
            continue

        if code == "[здесь был код, сгенерированный нейросетью]" or code.startswith("[здесь был код, сгенерированный нейросетью, ID:"):
            logger.warning(f"Пропущен плейсхолдер в файле {filename}")
            continue

        language = detect_language(filename, model_language)

        files.append({
            "type": "file",
            "filename": filename,
            "language": language,
            "content": code
        })

        text = text.replace(match.group(0), "")

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

    if not files and '```' in content:
        logger.warning("Найдены блоки кода без маркеров. Пытаемся извлечь...")
        code_pattern = r'```(\w*)\n([\s\S]*?)```'
        code_blocks = re.findall(code_pattern, content)
        
        for i, (lang, code) in enumerate(code_blocks):
            if code.strip().startswith("[здесь был код, сгенерированный нейросетью"):
                continue
                
            ext_map = {"python": "py", "javascript": "js", "bash": "sh", 
                      "html": "html", "css": "css", "json": "json", "sql": "sql"}
            ext = ext_map.get(lang, "txt")
            filename = f"code_{i+1}.{ext}"
            
            files.append({
                "type": "file",
                "filename": filename,
                "language": lang or "text",
                "content": code.strip()
            })
            logger.info(f"Извлечён файл из кодового блока: {filename}")

    text = re.sub(r'\n{3,}', '\n\n', text).strip()

    if not files:
        logger.warning("Файлы не найдены в ответе ИИ")

    return text, files
