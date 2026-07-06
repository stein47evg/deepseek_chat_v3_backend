# Тесты для парсинга ответа ИИ.
import pytest
from app.services.parser import parse_ai_response, detect_language


class TestParser:
    # Тесты парсинга ответов ИИ.

    def test_parse_simple_response(self):
        # Парсинг простого ответа с одним файлом.
        # Создаём тестовый ответ с маркером FILE (без тройных кавычек)
        content = (
            "Вот пример кода:\n\n"
            "### FILE: main.py\n"
            "```python\n"
            'print("Hello World")\n'
            "```"
        )
        # Вызываем парсер
        text, files = parse_ai_response(content)
        # Проверяем, что текст сохранился
        assert "Вот пример кода" in text
        # Проверяем, что найден ровно один файл
        assert len(files) == 1
        # Проверяем тип файла
        assert files[0]["type"] == "file"
        # Проверяем имя файла
        assert files[0]["filename"] == "main.py"
        # Проверяем язык
        assert files[0]["language"] == "python"
        # Проверяем содержимое
        assert "print" in files[0]["content"]

    def test_parse_multiple_files(self):
        # Парсинг ответа с несколькими файлами.
        # Создаём тестовый ответ с двумя файлами (без тройных кавычек)
        content = (
            "### FILE: main.py\n"
            "```python\n"
            'print("Hello")\n'
            "```\n"
            "\n"
            "### FILE: utils.py\n"
            "```python\n"
            "def helper():\n"
            "    return True\n"
            "```"
        )
        # Вызываем парсер
        text, files = parse_ai_response(content)
        # Проверяем, что найдено 2 файла
        assert len(files) == 2
        # Проверяем первый файл
        assert files[0]["filename"] == "main.py"
        # Проверяем второй файл
        assert files[1]["filename"] == "utils.py"

    def test_parse_code_snippet(self):
        # Парсинг сниппета (CODE).
        # Создаём тестовый ответ с маркером CODE (без тройных кавычек)
        content = (
            "Пример использования:\n\n"
            "### CODE: python\n"
            "```python\n"
            "import requests\n"
            'print("OK")\n'
            "```"
        )
        # Вызываем парсер
        text, files = parse_ai_response(content)
        # Проверяем, что найден ровно один элемент
        assert len(files) == 1
        # Проверяем тип (сниппет)
        assert files[0]["type"] == "snippet"
        # Проверяем язык
        assert files[0]["language"] == "python"
        # Проверяем, что имя файла отсутствует
        assert files[0]["filename"] is None

    def test_parse_mixed_content(self):
        # Парсинг смешанного ответа (файлы + сниппеты).
        # Создаём ответ с файлом и сниппетом (без тройных кавычек)
        content = (
            "Создал файл:\n\n"
            "### FILE: main.py\n"
            "```python\n"
            'print("Hello")\n'
            "```\n"
            "\n"
            "А вот пример использования:\n\n"
            "### CODE: bash\n"
            "```bash\n"
            "python main.py\n"
            "```"
        )
        # Вызываем парсер
        text, files = parse_ai_response(content)
        # Проверяем, что найдено 2 элемента
        assert len(files) == 2
        # Проверяем тип первого элемента
        assert files[0]["type"] == "file"
        # Проверяем тип второго элемента
        assert files[1]["type"] == "snippet"

    def test_detect_language_by_extension(self):
        # Определение языка по расширению файла.
        # Проверяем Python
        assert detect_language("main.py") == "python"
        # Проверяем JavaScript
        assert detect_language("app.js") == "javascript"
        # Проверяем CSS
        assert detect_language("style.css") == "css"
        # Проверяем Dockerfile
        assert detect_language("Dockerfile") == "dockerfile"
        # Проверяем неизвестное расширение
        assert detect_language("unknown.xyz") == "text"
        # Проверяем файл без расширения
        assert detect_language("README") == "text"

    def test_detect_language_model_priority(self):
        # Приоритет языка, указанного моделью.
        # Модель указала Java, но расширение .py - приоритет у модели
        assert detect_language("main.py", "java") == "java"
        # Модель указала TypeScript, расширение .js - приоритет у модели
        assert detect_language("app.js", "typescript") == "typescript"
