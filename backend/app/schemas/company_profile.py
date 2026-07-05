"""
Pydantic схемы для API профилей компании.

Pydantic v2.
"""

import json
from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, Field, field_validator


# ───────────────────────────── Requests ─────────────────────────────


class CompanyProfileCreate(BaseModel):
    """Запрос на создание профиля компании."""

    name: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Название профиля (1–200 символов)",
    )
    description: str = Field(
        default="",
        description="Описание профиля",
    )


# ───────────────────────────── Responses ─────────────────────────────


class CompanyProfileResponse(BaseModel):
    """Полная информация о профиле компании."""

    profile_id: str = Field(..., validation_alias="id", description="UUID профиля")
    name: str = Field(..., description="Название профиля")
    description: str = Field(..., description="Описание профиля")
    profile_type: str = Field(..., description="Тип профиля")
    document_count: int = Field(..., description="Количество документов")
    status: str = Field(..., description="Статус обработки")
    progress_pct: int = Field(..., description="Прогресс обработки (0–100)")
    profile_json: Any = Field(..., description="Синтезированный профиль (JSON)")
    analysis_stats: Optional[Any] = Field(
        None, description="Статистика анализа (JSON)"
    )
    documents: list = Field(default=[], description="Список загруженных документов")
    created_at: datetime = Field(..., description="Время создания (ISO 8601)")
    updated_at: datetime = Field(..., description="Время обновления (ISO 8601)")

    model_config = {"from_attributes": True, "populate_by_name": True}

    @field_validator("profile_json", mode="before")
    @classmethod
    def parse_profile_json(cls, v: Any) -> Any:
        """Парсит profile_json из строки JSON в dict."""
        if isinstance(v, str):
            try:
                return json.loads(v)
            except (json.JSONDecodeError, TypeError):
                return v
        return v

    @field_validator("analysis_stats", mode="before")
    @classmethod
    def parse_analysis_stats(cls, v: Any) -> Any:
        """Парсит analysis_stats из строки JSON в dict."""
        if v is None:
            return None
        if isinstance(v, str):
            try:
                return json.loads(v)
            except (json.JSONDecodeError, TypeError):
                return v
        return v


class CompanyProfileListItem(BaseModel):
    """Краткая информация о профиле для списка."""

    profile_id: str = Field(..., validation_alias="id", description="UUID профиля")
    name: str = Field(..., description="Название профиля")
    document_count: int = Field(..., description="Количество документов")
    status: str = Field(..., description="Статус обработки")
    progress_pct: int = Field(..., description="Прогресс обработки")
    analysis_stats: Optional[Any] = Field(
        None, description="Статистика анализа (JSON)"
    )
    created_at: datetime = Field(..., description="Время создания (ISO 8601)")

    model_config = {"from_attributes": True, "populate_by_name": True}

    @field_validator("analysis_stats", mode="before")
    @classmethod
    def parse_analysis_stats(cls, v: Any) -> Any:
        """Парсит analysis_stats из строки JSON в dict."""
        if v is None:
            return None
        if isinstance(v, str):
            try:
                return json.loads(v)
            except (json.JSONDecodeError, TypeError):
                return v
        return v


class CompanyProfileListResponse(BaseModel):
    """Список профилей с пагинацией."""

    items: list[CompanyProfileListItem] = Field(
        ..., description="Список профилей"
    )
    total: int = Field(..., description="Общее количество профилей")


class AnalyzedParagraphResponse(BaseModel):
    """Информация о проанализированном параграфе."""

    id: str = Field(..., description="UUID параграфа")
    paragraph_index: int = Field(..., description="Порядковый номер параграфа")
    section_title: Optional[str] = Field(None, description="Заголовок раздела")
    original_text: str = Field(..., description="Исходный текст параграфа")
    char_count: int = Field(..., description="Количество символов")
    is_table_row: int = Field(..., description="Является строкой таблицы (0/1)")
    is_list_item: int = Field(..., description="Является элементом списка (0/1)")
    steps: list = Field(default=[], description="Выделенные шаги (JSON)")

    model_config = {"from_attributes": True}

    @field_validator("steps", mode="before")
    @classmethod
    def parse_steps(cls, v: Any) -> Any:
        """Парсит steps из строки JSON в список."""
        if isinstance(v, str):
            try:
                return json.loads(v)
            except (json.JSONDecodeError, TypeError):
                return v
        return v


class AnalyzedParagraphListResponse(BaseModel):
    """Список параграфов с пагинацией."""

    items: list[AnalyzedParagraphResponse] = Field(
        ..., description="Список параграфов"
    )
    total: int = Field(..., description="Общее количество параграфов")
