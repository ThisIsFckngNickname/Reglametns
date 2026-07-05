"""
DocumentAnalysis — модель анализа загруженного документа.
Хранит результат извлечения параграфов, LLM-анализа и синтезированные инсайты.
"""

import uuid
from datetime import datetime
from sqlalchemy import Column, String, Text, DateTime, Integer
from app.database import Base


def generate_uuid() -> str:
    return str(uuid.uuid4())


class DocumentAnalysis(Base):
    """Результат анализа одного загруженного .docx документа."""

    __tablename__ = "document_analyses"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    original_filename = Column(String(255), nullable=False)
    stored_path = Column(String(500), nullable=False)
    file_size = Column(Integer, default=0)
    status = Column(String(20), nullable=False, default="uploaded")
    # Статусы: uploaded, extracting, analyzing, ready, failed

    total_paragraphs = Column(Integer, default=0)
    total_steps = Column(Integer, default=0)
    insights_json = Column(Text, nullable=True)
    analysis_stats = Column(Text, nullable=True)
    paragraphs_json = Column(Text, nullable=True)

    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
