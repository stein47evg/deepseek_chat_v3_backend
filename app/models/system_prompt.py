"""
Модель системного промпта.
"""
from sqlalchemy import Column, Integer, String, Text, TIMESTAMP, Boolean
from sqlalchemy.sql import func
from app.core.database import Base


class SystemPrompt(Base):
    __tablename__ = "system_prompts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    content = Column(Text, nullable=False)

    is_default = Column(Boolean, default=False)
    is_custom = Column(Boolean, default=False)
    is_quick = Column(Boolean, default=False)

    created_at = Column(TIMESTAMP, server_default=func.now())

    def __repr__(self):
        return f"<SystemPrompt(id={self.id}, name='{self.name}')>"
