"""
Скрипт для добавления предустановленных системных промптов.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import SessionLocal
from app.services.prompt_service import PromptService


def main():
    """Добавляет предустановленные промпты в базу."""
    db = SessionLocal()
    try:
        print("🔄 Добавление предустановленных промптов...")
        PromptService.seed_defaults(db)
        print("✅ Промпты успешно добавлены")
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    main()
