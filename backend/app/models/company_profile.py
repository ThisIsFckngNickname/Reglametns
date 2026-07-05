"""
CompanyProfile — модель профиля компании для анализа документов.

Хранит синтезированный стилистико-логический профиль,
полученный после анализа загруженных .docx файлов.
"""

import uuid
from datetime import datetime
from sqlalchemy import Column, String, Text, DateTime, Integer
from sqlalchemy.orm import relationship
from app.database import Base


def generate_uuid() -> str:
    """Генерация UUID v4 как строки."""
    return str(uuid.uuid4())


class CompanyProfile(Base):
    """Профиль компании, сформированный по результатам анализа документов."""

    __tablename__ = "company_profiles"

    id = Column(
        String(36),
        primary_key=True,
        default=generate_uuid,
        doc="UUID v4",
    )
    name = Column(
        String(200),
        nullable=False,
        doc="Название профиля",
    )
    description = Column(
        Text,
        default="",
        doc="Описание профиля",
    )
    profile_type = Column(
        String(20),
        nullable=False,
        default="paragraph_logic",
        doc="Тип профиля: paragraph_logic | style_profile",
    )
    document_count = Column(
        Integer,
        default=0,
        doc="Количество обработанных документов",
    )
    profile_json = Column(
        Text,
        nullable=False,
        doc="Синтезированный профиль в формате JSON",
    )
    analysis_stats = Column(
        Text,
        nullable=True,
        doc="Статистика анализа в формате JSON",
    )
    status = Column(
        String(20),
        nullable=False,
        default="uploaded",
        doc="Статус: uploaded | extracting | analyzing | synthesizing | ready | failed",
    )
    error_message = Column(
        Text,
        nullable=True,
        doc="Текст ошибки (при status='failed')",
    )
    progress_pct = Column(
        Integer,
        default=0,
        doc="Прогресс обработки (0–100)",
    )
    created_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        doc="Время создания записи (UTC)",
    )
    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        doc="Время последнего обновления (UTC)",
    )

    documents = relationship(
        "UploadedDocument",
        back_populates="profile",
        cascade="all, delete-orphan",
        doc="Загруженные документы профиля",
    )
    analyzed_paragraphs = relationship(
        "AnalyzedParagraph",
        back_populates="profile",
        cascade="all, delete-orphan",
        doc="Проанализированные параграфы профиля",
    )

    def __repr__(self) -> str:
        return (
            f"<CompanyProfile(id={self.id}, name={self.name!r}, "
            f"status={self.status}, type={self.profile_type})>"
        )
