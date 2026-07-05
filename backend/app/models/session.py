"""
generation_sessions — таблица для отслеживания multi-stage генерации.
"""

import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, Text, DateTime
from app.database import Base


class GenerationSession(Base):
    __tablename__ = "generation_sessions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    topic = Column(String, nullable=False)
    status = Column(
        String,
        nullable=False,
        default="accepted",
    )
    current_stage = Column(String, nullable=False, default="accepted")
    stage_progress = Column(Integer, default=0)
    total_sections = Column(Integer, default=0)
    completed_sections = Column(Integer, default=0)
    provider_used = Column(String, default="")
    document_id = Column(String, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "topic": self.topic,
            "status": self.status,
            "current_stage": self.current_stage,
            "stage_progress": self.stage_progress,
            "total_sections": self.total_sections,
            "completed_sections": self.completed_sections,
            "provider_used": self.provider_used,
            "document_id": self.document_id,
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }
