"""
document_sections — отдельные разделы регламента для multi-stage генерации.
"""

import uuid
from datetime import datetime
from sqlalchemy import Column, String, Text, Integer, DateTime, ForeignKey
from app.database import Base


class DocumentSection(Base):
    __tablename__ = "document_sections"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String, ForeignKey("generation_sessions.id"), nullable=False)
    section_number = Column(Integer, nullable=False)
    title = Column(String, nullable=False)
    annotation = Column(Text, nullable=True)
    content = Column(Text, nullable=True)
    status = Column(String, nullable=False, default="pending")
    fix_attempts = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
