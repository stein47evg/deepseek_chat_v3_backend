from sqlalchemy import Column, Integer, String, TIMESTAMP, DECIMAL
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base


class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    folder_path = Column(String(500), nullable=False, unique=True)
    created_at = Column(TIMESTAMP, server_default=func.now())

    # Статистика токенов
    total_input_tokens = Column(Integer, default=0)
    total_output_tokens = Column(Integer, default=0)
    total_cost = Column(DECIMAL(10, 6), default=0.0)

    # Связи
    chats = relationship("Chat", back_populates="project", cascade="all, delete-orphan")
    snapshots = relationship("Snapshot", back_populates="project", cascade="all, delete-orphan")
