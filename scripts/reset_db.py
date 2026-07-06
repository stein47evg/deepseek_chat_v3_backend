"""
Скрипт для сброса базы данных (только для разработки).
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import engine, Base
from app.models import *  # noqa: F401


def main():
    """Удаляет все таблицы и создаёт заново."""
    confirm = input("⚠️  Вы уверены, что хотите сбросить базу данных? (y/N): ")
    if confirm.lower() != 'y':
        print("❌ Отменено")
        return

    print("🔄 Сброс базы данных...")
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    print("✅ База данных сброшена")


if __name__ == "__main__":
    main()
