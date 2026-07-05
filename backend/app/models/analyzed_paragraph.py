"""
AnalyzedParagraph — модель проанализированного параграфа.

Хранит результат разбора одного параграфа из загруженного документа,
включая выделенные шаги (steps) в формате JSON.
"""

import uuid
from datetime import datetime
from sqlalchemy import Column, String, Text, DateTime, Integer, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base


def generate_uuid() -> str:
    """Генерация UUID v4 как строки."""
    return str(uuid.uuid4())


class AnalyzedParagraph(Base):
    """Один параграф с результатами анализа и выделенными шагами."""

    __tablename__ = "analyzed_paragraphs"

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
        doc="ID профиля компании",
    )
    document_id = Column(
        String(36),
        ForeignKey("uploaded_documents.id", ondelete="CASCADE"),
        nullable=False,
        doc="ID загруженного документа",
    )
    paragraph_index = Column(
        Integer,
        nullable=False,
        doc="Порядковый номер параграфа в документе",
    )
    section_title = Column(
        Text,
        nullable=True,
        doc="Заголовок раздела, к которому относится параграф",
    )
    original_text = Column(
        Text,
        nullable=False,
        doc="Исходный текст параграфа",
    )
    steps_json = Column(
        Text,
        nullable=False,
        default="[]",
        doc="Массив выделенных шагов в формате JSON",
    )
    char_count = Column(
        Integer,
        default=0,
        doc="Количество символов в параграфе",
    )
    is_table_row = Column(
        Integer,
        default=0,
        doc="Является ли строкой таблицы (0/1)",
    )
    is_list_item = Column(
        Integer,
        default=0,
        doc="Является ли элементом списка (0/1)",
    )
    created_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        doc="Время создания записи (UTC)",
    )

    profile = relationship(
        "CompanyProfile",
        back_populates="analyzed_paragraphs",
        doc="Профиль компании",
    )
    document = relationship(
        "UploadedDocument",
        back_populates="analyzed_paragraphs",
        doc="Загруженный документ",
    )

    def __repr__(self) -> str:
        return (
            f"<AnalyzedParagraph(id={self.id}, index={self.paragraph_index}, "
            f"doc_id={self.document_id})>"
        )
