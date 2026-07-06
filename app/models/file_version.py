"""
Модель версии файла.
"""
from sqlalchemy import Column, Integer, String, Text, TIMESTAMP, ForeignKey, Enum, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base


class FileVersion(Base):
    __tablename__ = "file_versions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    chat_id = Column(Integer, ForeignKey("chats.id", ondelete="CASCADE"), nullable=False)
    message_id = Column(Integer, ForeignKey("messages.id", ondelete="SET NULL"), nullable=True)

    filename = Column(String(500), nullable=False)
    content = Column(Text, nullable=False)
    content_hash = Column(String(64), nullable=False)
    language = Column(String(50), nullable=True)

    file_type = Column(Enum("uploaded", "generated", "synced"), nullable=False)

    is_current = Column(Boolean, default=False)
    applied = Column(Boolean, default=False)

    created_at = Column(TIMESTAMP, server_default=func.now())

    # Связи (без backref, чтобы избежать конфликта)
    chat = relationship("Chat", back_populates="file_versions")
    message = relationship("Message", back_populates="file_versions")

    def __repr__(self):
        return f"<FileVersion(id={self.id}, filename='{self.filename}', is_current={self.is_current})>"
