"""
Pydantic схемы для API запросов/ответов.
Pydantic v2.
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, field_validator
from enum import Enum


class ProviderEnum(str, Enum):
    """Допустимые провайдеры для запроса генерации."""

    auto = "auto"
    groq = "groq"
    yandexgpt = "yandexgpt"
    ollama = "ollama"


# ───────────────────────────── Requests ─────────────────────────────


class GenerateRequest(BaseModel):
    """Запрос на генерацию регламента."""

    topic: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="Тема регламента (1–2000 символов)",
    )
    provider: ProviderEnum = Field(
        default=ProviderEnum.groq,
        description="Выбор AI-провайдера",
    )

    @field_validator("topic")
    @classmethod
    def topic_not_blank(cls, v: str) -> str:
        """Проверка, что тема не состоит только из пробелов."""
        stripped = v.strip()
        if not stripped:
            raise ValueError("Тема не может быть пустой или состоять только из пробелов")
        return stripped


# ───────────────────────────── Responses ─────────────────────────────


class GenerateResponse(BaseModel):
    """Ответ после успешной генерации регламента."""

    id: str = Field(..., description="UUID документа")
    topic: str = Field(..., description="Тема регламента")
    filename: str = Field(..., description="Имя .docx файла для скачивания")
    provider_used: str = Field(..., description="Фактический провайдер")
    status: str = Field(..., description="Статус генерации")
    created_at: datetime = Field(..., description="Время создания (ISO 8601)")

    model_config = {"from_attributes": True}


class DocumentResponse(BaseModel):
    """Документ в списке истории (краткая информация)."""

    id: str = Field(..., description="UUID документа")
    topic: str = Field(..., description="Тема регламента")
    provider_used: str = Field(..., description="Провайдер")
    status: str = Field(..., description="Статус генерации")
    created_at: datetime = Field(..., description="Время создания")

    model_config = {"from_attributes": True}


class DocumentDetailResponse(BaseModel):
    """Детальная информация о документе."""

    id: str = Field(..., description="UUID документа")
    topic: str = Field(..., description="Тема регламента")
    prompt: str = Field(..., description="Отправленный промпт")
    provider_used: str = Field(..., description="Провайдер")
    status: str = Field(..., description="Статус генерации")
    error_message: Optional[str] = Field(None, description="Текст ошибки")
    created_at: datetime = Field(..., description="Время создания")

    model_config = {"from_attributes": True}


class DocumentListResponse(BaseModel):
    """Список документов с пагинацией."""

    items: list[DocumentResponse] = Field(..., description="Список документов")
    total: int = Field(..., description="Общее количество документов")


class ErrorResponse(BaseModel):
    """Унифицированный ответ с ошибкой."""

    detail: str = Field(..., description="Описание ошибки")


class ErrorDetailItem(BaseModel):
    """Деталь валидационной ошибки."""

    field: str = Field(..., description="Поле с ошибкой")
    message: str = Field(..., description="Описание ошибки")


class ValidationErrorResponse(BaseModel):
    """Ответ при 422 Validation Error."""

    detail: list[ErrorDetailItem] = Field(..., description="Список ошибок")


# ───────────────────────────── Providers ─────────────────────────────


class ProviderStatus(BaseModel):
    """Статус одного AI-провайдера."""

    id: str = Field(..., description="Идентификатор провайдера")
    name: str = Field(..., description="Человекочитаемое имя")
    available: bool = Field(..., description="Доступен ли провайдер")
    model: Optional[str] = Field(None, description="Название модели")
    error: Optional[str] = Field(None, description="Описание ошибки (если недоступен)")


class ProvidersResponse(BaseModel):
    """Ответ со статусами всех провайдеров."""

    providers: list[ProviderStatus] = Field(..., description="Список провайдеров")
