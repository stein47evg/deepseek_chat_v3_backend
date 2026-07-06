"""
Скрипт для инициализации базы данных.
"""
import sys
import os

# Добавляем корневую директорию в путь
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import init_db, engine
from app.models import *  # noqa: F401


def main():
    """Создаёт все таблицы в базе данных."""
    print("🔄 Инициализация базы данных...")
    init_db()
    print("✅ База данных успешно инициализирована")


if __name__ == "__main__":
    main()
