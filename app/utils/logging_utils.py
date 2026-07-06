"""
Настройка логирования.
"""
import logging


def setup_logging():
    """
    Настраивает логирование для приложения.
    Логи выводятся в stdout в формате: время - уровень - сообщение.
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # Устанавливаем уровень для SQLAlchemy
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """
    Возвращает логгер с указанным именем.
    
    Аргументы:
        name: Имя логгера (обычно __name__)
    Возвращает:
        Объект логгера
    """
    return logging.getLogger(name)
