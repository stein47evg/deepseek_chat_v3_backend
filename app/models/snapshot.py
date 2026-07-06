from sqlalchemy import Column, Integer, String, Text, TIMESTAMP, ForeignKey, Enum, JSON, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base


class Snapshot(Base):
    __tablename__ = "snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)

    prev_id = Column(Integer, ForeignKey("snapshots.id", ondelete="CASCADE"), nullable=True)
    sequence_number = Column(Integer, nullable=False)

    level = Column(Integer, default=2)
    type = Column(Enum("initial", "manual", "apply", "upload", "sync", "auto"), nullable=False)

    name = Column(String(255), nullable=True)
    description = Column(Text, nullable=True)

    files_manifest = Column(JSON, nullable=False)

    is_current = Column(Boolean, default=False)
    created_at = Column(TIMESTAMP, server_default=func.now())

    # Связи
    project = relationship("Project", back_populates="snapshots")
    prev = relationship("Snapshot", remote_side=[id], backref="next")
