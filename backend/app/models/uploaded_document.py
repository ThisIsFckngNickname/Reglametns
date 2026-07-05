"""
UploadedDocument — модель загруженного .docx файла.

Содержит информацию о загруженном документе,
извлечённый текст и статус обработки.
"""

import uuid
from datetime import datetime
from sqlalchemy import Column, String, Text, DateTime, Integer, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base


def generate_uuid() -> str:
    """Генерация UUID v4 как строки."""
    return str(uuid.uuid4())


class UploadedDocument(Base):
    """Загруженный .docx файл для анализа."""

    __tablename__ = "uploaded_documents"

    id = Column(
        String(36),
        primary_key=True,
        default=generate_uuid,
        doc="UUID v4",
    )
    profile_id = Column(
        String(36),
        ForeignKey("company_profiles.id", ondelete="CASCADE"),
        nullable=False,
        doc="ID профиля компании-владельца",
    )
    original_name = Column(
        String(255),
        nullable=False,
        doc="Оригинальное имя файла",
    )
    stored_path = Column(
        String(500),
        nullable=False,
        doc="Путь к файлу на диске",
    )
    file_size = Column(
        Integer,
        default=0,
        doc="Размер файла в байтах",
    )
    mime_type = Column(
        String(100),
        default=(
            "application/vnd.openxmlformats-officedocument"
            ".wordprocessingml.document"
        ),
        doc="MIME-тип файла",
    )
    status = Column(
        String(20),
        nullable=False,
        default="uploaded",
        doc="Статус: uploaded | extracted | analyzed | failed",
    )
    paragraph_count = Column(
        Integer,
        default=0,
        doc="Количество извлечённых параграфов",
    )
    step_count = Column(
        Integer,
        default=0,
        doc="Количество выделенных шагов",
    )
    extracted_text = Column(
        Text,
        nullable=True,
        doc="Извлечённый текст документа",
    )
    analysis_error = Column(
        Text,
        nullable=True,
        doc="Текст ошибки анализа",
    )
    created_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        doc="Время загрузки (UTC)",
    )

    profile = relationship(
        "CompanyProfile",
        back_populates="documents",
        doc="Профиль компании-владельца",
    )
    analyzed_paragraphs = relationship(
        "AnalyzedParagraph",
        back_populates="document",
        cascade="all, delete-orphan",
        doc="Проанализированные параграфы документа",
    )

    def __repr__(self) -> str:
        return (
            f"<UploadedDocument(id={self.id}, name={self.original_name!r}, "
            f"status={self.status})>"
        )
