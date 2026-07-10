"""
Настройка логирования.
"""
import logging
import sys


def setup_logging(level: str = "INFO"):
    """
    Настраивает логирование для приложения.
    Логи выводятся в stdout в формате: время - уровень - сообщение.
    """
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )

    # Устанавливаем уровень для SQLAlchemy
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.INFO)


def get_logger(name: str) -> logging.Logger:
    """
    Возвращает логгер с указанным именем.
    
    Аргументы:
        name: Имя логгера (обычно __name__)
    Возвращает:
        Объект логгера
    """
    return logging.getLogger(name)
