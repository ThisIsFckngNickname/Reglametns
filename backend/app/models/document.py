"""
SQLAlchemy модель Document.

Соответствует таблице documents из спецификации (раздел 4).
"""

import uuid
from datetime import datetime
from sqlalchemy import Column, String, Text, DateTime, CheckConstraint
from app.database import Base


def generate_uuid() -> str:
    """Генерация UUID v4 как строки."""
    return str(uuid.uuid4())


class Document(Base):
    """Модель документа регламента."""

    __tablename__ = "documents"

    id = Column(
        String(36),
        primary_key=True,
        default=generate_uuid,
        doc="UUID v4",
    )
    topic = Column(
        String(2000),
        nullable=False,
        doc="Тема регламента (от пользователя)",
    )
    provider_used = Column(
        String(50),
        nullable=False,
        doc="Идентификатор провайдера (groq, yandexgpt, ollama)",
    )
    prompt = Column(
        Text,
        nullable=False,
        doc="Полный промпт (system + user), отправленный провайдеру",
    )
    raw_response = Column(
        Text,
        nullable=True,
        doc="Сырой ответ от LLM (markdown)",
    )
    docx_path = Column(
        String(500),
        nullable=True,
        doc="Путь к .docx файлу относительно корня проекта",
    )
    status = Column(
        String(20),
        nullable=False,
        default="completed",
        doc="Статус генерации: completed / failed",
    )
    error_message = Column(
        Text,
        nullable=True,
        doc="Текст ошибки (при status='failed')",
    )
    created_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        doc="Время создания записи (UTC)",
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('completed', 'failed')",
            name="ck_documents_status",
        ),
    )

    def __repr__(self) -> str:
        return f"<Document(id={self.id}, topic={self.topic!r}, status={self.status})>"
