from sqlalchemy import Column, Integer, String, Text, TIMESTAMP, ForeignKey, Enum, DECIMAL, Boolean, JSON
from sqlalchemy.dialects.mysql import MEDIUMTEXT
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    chat_id = Column(Integer, ForeignKey("chats.id", ondelete="CASCADE"), nullable=False)
    role = Column(Enum("user", "assistant", "system"), nullable=False)
    content = Column(Text, nullable=False)

    # Поля для неполных сообщений
    is_complete = Column(Boolean, default=True)
    partial_content = Column(MEDIUMTEXT, nullable=True)  # ✅ MEDIUMTEXT для сырого ответа
    context_data = Column(JSON, nullable=True)           # Контекст запроса (для продолжения)

    # Статистика токенов
    input_tokens = Column(Integer, nullable=True)
    output_tokens = Column(Integer, nullable=True)
    total_tokens = Column(Integer, nullable=True)
    cost = Column(DECIMAL(10, 6), nullable=True)

    created_at = Column(TIMESTAMP, server_default=func.now())

    # Связи
    chat = relationship("Chat", back_populates="messages")
    file_versions = relationship("FileVersion", back_populates="message")
