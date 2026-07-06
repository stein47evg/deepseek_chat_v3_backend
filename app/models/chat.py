from sqlalchemy import Column, Integer, String, TIMESTAMP, ForeignKey, DECIMAL
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base


class Chat(Base):
    __tablename__ = "chats"

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=True)
    title = Column(String(255), default="Новый чат")
    created_at = Column(TIMESTAMP, server_default=func.now())

    # Статистика токенов
    total_input_tokens = Column(Integer, default=0)
    total_output_tokens = Column(Integer, default=0)
    total_cost = Column(DECIMAL(10, 6), default=0.0)

    # Связи
    project = relationship("Project", back_populates="chats")
    messages = relationship("Message", back_populates="chat", cascade="all, delete-orphan")
    file_versions = relationship("FileVersion", back_populates="chat", cascade="all, delete-orphan")
