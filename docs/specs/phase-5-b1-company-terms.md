# Phase 5 B1: CompanyTerm и CompanyAbbreviation — Specification

> **Проект:** SRP (Service for Regulations and Policies)
> **Фаза:** 5 / Инкремент B1 — Общехолдинговый перечень терминов и сокращений
> **Дата:** 2026-06-28
> **Статус:** Черновик (готов к реализации)
> **Аудитория:** BE (Python/FastAPI), FE (React/TypeScript)

---

## Оглавление

1. [Контекст и цель](#1-контекст-и-цель)
2. [SQLAlchemy модели](#2-sqlalchemy-модели)
   - 2.1 CompanyTerm
   - 2.2 CompanyAbbreviation
   - 2.3 Отличия от DocumentTerm / DocumentAbbreviation
3. [Pipeline integration](#3-pipeline-integration)
   - 3.1 Расширение шага extract_terms
   - 3.2 Расширение шага extract_abbr
   - 3.3 Алгоритм синхронизации
4. [Pydantic схемы](#4-pydantic-схемы)
5. [API CRUD](#5-api-crud)
   - 5.1 Термины
   - 5.2 Сокращения
   - 5.3 Ролевая модель
   - 5.4 Формат ошибок
6. [DataLoader — новые методы](#6-dataloader--новые-методы)
7. [Alembic миграция](#7-alembic-миграция)

---

## 1. Контекст и цель

### 1.1 Проблема

В текущей реализации термины (`DocumentTerm`) и сокращения (`DocumentAbbreviation`) привязаны к конкретным документам. При генерации нового документа `DataLoader.load_company_terms()` собирает все термины из всех документов холдинга и дедуплицирует их.

**Недостатки:**
1. Нет **единого авторитетного перечня** терминов холдинга — каждый документ хранит свои копии
2. При изменении термина нужно перезагружать все документы
3. Невозможно создать термин «вручную» без привязки к документу
4. Нет отслеживания источника термина (из какого документа он впервые извлечён)
5. Нет флага «ручной» vs «автоматический»

### 1.2 Решение

Создать две новые таблицы `company_terms` и `company_abbreviations`, которые хранят **общехолдинговый перечень**. При анализе утверждённых документов термины автоматически синхронизируются с этим перечнем. Пользователи могут вручную добавлять, редактировать и удалять термины через UI.

### 1.3 Отношение с существующими моделями

```
CompanyTerm (общехолдинговый)         DocumentTerm (в рамках документа)
─────────────────────────────         ─────────────────────────────────
- Один термин на холдинг              - Много записей на документ
- Unique(company_id, term)            - Просто FK на document
- Есть source_document_id             - Нет источника
- Есть is_manual (флаг)               - Нет флага
- Можно редактировать/удалять         - Только для чтения (из анализа)
```

---

## 2. SQLAlchemy модели

### 2.1 CompanyTerm

```python
# backend/app/models/company_term.py

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    Boolean, DateTime, ForeignKey, Integer, String, Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.company import Company
    from app.models.document import Document


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class CompanyTerm(Base):
    __tablename__ = "company_terms"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("companies.id", ondelete="CASCADE"),
        index=True, nullable=False,
    )
    term: Mapped[str] = mapped_column(String(255), nullable=False)
    definition: Mapped[str] = mapped_column(Text, nullable=False)
    source_document_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("documents.id", ondelete="SET NULL"),
        nullable=True,
    )
    is_manual: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utcnow, nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utcnow, onupdate=_utcnow, nullable=False,
    )

    company: Mapped["Company"] = relationship("Company", lazy="selectin")
    source_document: Mapped[Optional["Document"]] = relationship(
        "Document", lazy="selectin",
    )

    __table_args__ = (
        UniqueConstraint("company_id", "term", name="uq_company_term"),
    )

    def __repr__(self) -> str:
        return f"<CompanyTerm(id={self.id}, company_id={self.company_id}, term={self.term})>"
```

### 2.2 CompanyAbbreviation

```python
# backend/app/models/company_abbreviation.py

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    Boolean, DateTime, ForeignKey, Integer, String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.company import Company
    from app.models.document import Document


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class CompanyAbbreviation(Base):
    __tablename__ = "company_abbreviations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("companies.id", ondelete="CASCADE"),
        index=True, nullable=False,
    )
    abbreviation: Mapped[str] = mapped_column(String(50), nullable=False)
    full_form: Mapped[str] = mapped_column(String(500), nullable=False)
    source_document_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("documents.id", ondelete="SET NULL"),
        nullable=True,
    )
    is_manual: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utcnow, nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utcnow, onupdate=_utcnow, nullable=False,
    )

    company: Mapped["Company"] = relationship("Company", lazy="selectin")
    source_document: Mapped[Optional["Document"]] = relationship(
        "Document", lazy="selectin",
    )

    __table_args__ = (
        UniqueConstraint("company_id", "abbreviation", name="uq_company_abbreviation"),
    )

    def __repr__(self) -> str:
        return (
            f"<CompanyAbbreviation(id={self.id}, "
            f"company_id={self.company_id}, "
            f"abbreviation={self.abbreviation})>"
        )
```

### 2.3 Отличия от DocumentTerm / DocumentAbbreviation

| Характеристика | DocumentTerm | CompanyTerm |
|---------------|-------------|-------------|
| Таблица | `document_terms` | `company_terms` |
| Привязка | К документу | К холдингу |
| Unique | Нет | `(company_id, term)` |
| Source | Нет | `source_document_id` (FK) |
| is_manual | Нет | Да |
| CRUD через UI | Нет (только чтение) | Да |
| Использование в генераторе | Legacy (Phase 1-4) | V2 (Phase 5 B1) |

**Важно:** Обе таблицы продолжают существовать. `DocumentTerm` остаётся для хранения терминов конкретного документа (для отображения в карточке документа). `CompanyTerm` — для общехолдингового перечня (используется в генераторе V2 и на странице терминов).

---

## 3. Pipeline integration

### 3.1 Расширение шага extract_terms

После успешного извлечения терминов из документа (шаг 3 pipeline), добавляется синхронизация с `CompanyTerm`:

```
Псевдокод для _step_extract_terms (расширение):

1. Извлечь термины из full_text (существующая логика)
2. Сохранить в document_terms (существующая логика)
3. ДЛЯ КАЖДОГО извлечённого термина:
   a. Проверить: SELECT FROM company_terms 
      WHERE company_id=? AND term=?
   b. ЕСЛИ НЕТ записи:
      → INSERT INTO company_terms 
        (company_id, term, definition, source_document_id, is_manual=False)
   c. ЕСЛИ запись ЕСТЬ:
      → Сравнить definition
      → Если отличается:
        → LOG: "Term '{term}' exists with different definition. 
                Saved: '{old_def}', Document: '{new_def}'. Skipping."
        → НЕ заменять (пользователь решит при редактировании)
   d. Если запись есть и definition совпадает:
      → SKIP (уже синхронизировано)
```

**Код:**

```python
async def _sync_terms_to_company(
    self,
    company_id: int,
    document_id: int,
    extracted_terms: list[dict],
    db: AsyncSession,
) -> dict:
    """Sync extracted terms to company-wide term list.
    
    Args:
        company_id: Company ID.
        document_id: Source document ID.
        extracted_terms: List of {"term": str, "definition": str}.
        db: Database session.
    
    Returns:
        {"inserted": int, "skipped_exists": int, "skipped_mismatch": int}
    """
    from app.models.company_term import CompanyTerm
    
    stats = {"inserted": 0, "skipped_exists": 0, "skipped_mismatch": 0}
    
    for term_data in extracted_terms:
        term_name = term_data.get("term", "").strip()
        definition = term_data.get("definition", "").strip()
        
        if not term_name or not definition:
            continue
        
        # Check if term exists for this company
        stmt = select(CompanyTerm).where(
            CompanyTerm.company_id == company_id,
            CompanyTerm.term == term_name,
        )
        result = await db.execute(stmt)
        existing = result.scalar_one_or_none()
        
        if existing is None:
            # New term — insert
            company_term = CompanyTerm(
                company_id=company_id,
                term=term_name,
                definition=definition,
                source_document_id=document_id,
                is_manual=False,
            )
            db.add(company_term)
            stats["inserted"] += 1
        elif existing.definition.strip() != definition:
            # Term exists with different definition — skip
            logger.info(
                f"CompanyTerm '{term_name}' exists with different definition. "
                f"Skipping. DB: '{existing.definition[:50]}', "
                f"Doc: '{definition[:50]}'"
            )
            stats["skipped_mismatch"] += 1
        else:
            # Term exists with same definition — skip
            stats["skipped_exists"] += 1
    
    await db.flush()
    return stats
```

### 3.2 Расширение шага extract_abbr

Аналогично для сокращений:

```python
async def _sync_abbreviations_to_company(
    self,
    company_id: int,
    document_id: int,
    extracted_abbreviations: list[dict],
    db: AsyncSession,
) -> dict:
    """Sync extracted abbreviations to company-wide list.
    
    Args:
        company_id: Company ID.
        document_id: Source document ID.
        extracted_abbreviations: List of {"abbreviation": str, "full_form": str}.
        db: Database session.
    
    Returns:
        {"inserted": int, "skipped_exists": int, "skipped_mismatch": int}
    """
    from app.models.company_abbreviation import CompanyAbbreviation
    
    stats = {"inserted": 0, "skipped_exists": 0, "skipped_mismatch": 0}
    
    for abbr_data in extracted_abbreviations:
        abbr = abbr_data.get("abbreviation", "").strip()
        full_form = abbr_data.get("full_form", "").strip()
        
        if not abbr or not full_form:
            continue
        
        stmt = select(CompanyAbbreviation).where(
            CompanyAbbreviation.company_id == company_id,
            CompanyAbbreviation.abbreviation == abbr,
        )
        result = await db.execute(stmt)
        existing = result.scalar_one_or_none()
        
        if existing is None:
            company_abbr = CompanyAbbreviation(
                company_id=company_id,
                abbreviation=abbr,
                full_form=full_form,
                source_document_id=document_id,
                is_manual=False,
            )
            db.add(company_abbr)
            stats["inserted"] += 1
        elif existing.full_form.strip() != full_form:
            logger.info(
                f"CompanyAbbreviation '{abbr}' exists with different full_form. "
                f"Skipping."
            )
            stats["skipped_mismatch"] += 1
        else:
            stats["skipped_exists"] += 1
    
    await db.flush()
    return stats
```

### 3.3 Интеграция в AnalysisPipelineService

```python
# В методе _step_extract_terms:
async def _step_extract_terms(self, full_text, document_id, db):
    # ... существующая логика извлечения ...
    terms = await parser_service._extract_terms_from_text(full_text)
    
    # Save to document_terms (existing)
    await self._save_document_terms(document_id, terms, db)
    
    # NEW: Sync to company-wide terms
    doc = await self._get_document(document_id, db)
    if doc:
        sync_stats = await self._sync_terms_to_company(
            company_id=doc.company_id,
            document_id=document_id,
            extracted_terms=terms,
            db=db,
        )
        logger.info(f"CompanyTerm sync: {sync_stats}")
    
    return len(terms)

# Аналогично для _step_extract_abbr:
async def _step_extract_abbr(self, full_text, document_id, db):
    # ... существующая логика извлечения ...
    abbreviations = await parser_service._extract_abbreviations_from_text(full_text)
    
    # Save to document_abbreviations (existing)
    await self._save_document_abbreviations(document_id, abbreviations, db)
    
    # NEW: Sync to company-wide abbreviations
    doc = await self._get_document(document_id, db)
    if doc:
        sync_stats = await self._sync_abbreviations_to_company(
            company_id=doc.company_id,
            document_id=document_id,
            extracted_abbreviations=abbreviations,
            db=db,
        )
        logger.info(f"CompanyAbbreviation sync: {sync_stats}")
    
    return len(abbreviations)
```

---

## 4. Pydantic схемы

### 4.1 CompanyTerm схемы

```python
# backend/app/schemas/company_term.py

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, field_validator


class CompanyTermCreate(BaseModel):
    term: str
    definition: str
    
    @field_validator("term")
    @classmethod
    def validate_term(cls, v: str) -> str:
        if not v or len(v) > 255:
            raise ValueError("Term must be between 1 and 255 characters")
        return v.strip()
    
    @field_validator("definition")
    @classmethod
    def validate_definition(cls, v: str) -> str:
        if not v:
            raise ValueError("Definition is required")
        return v.strip()


class CompanyTermUpdate(BaseModel):
    term: Optional[str] = None
    definition: Optional[str] = None
    
    @field_validator("term")
    @classmethod
    def validate_term(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            if not v or len(v) > 255:
                raise ValueError("Term must be between 1 and 255 characters")
            return v.strip()
        return v
    
    @field_validator("definition")
    @classmethod
    def validate_definition(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not v:
            raise ValueError("Definition cannot be empty")
        if v is not None:
            return v.strip()
        return v


class CompanyTermResponse(BaseModel):
    id: int
    company_id: int
    term: str
    definition: str
    source_document_id: Optional[int] = None
    source_document_title: Optional[str] = None  # Денормализовано для UI
    is_manual: bool = False
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CompanyTermListResponse(BaseModel):
    items: list[CompanyTermResponse]
    total: int
    page: int
    page_size: int
    pages: int
```

### 4.2 CompanyAbbreviation схемы

```python
# backend/app/schemas/company_abbreviation.py

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, field_validator


class CompanyAbbreviationCreate(BaseModel):
    abbreviation: str
    full_form: str
    
    @field_validator("abbreviation")
    @classmethod
    def validate_abbreviation(cls, v: str) -> str:
        if not v or len(v) > 50:
            raise ValueError("Abbreviation must be between 1 and 50 characters")
        return v.strip()
    
    @field_validator("full_form")
    @classmethod
    def validate_full_form(cls, v: str) -> str:
        if not v or len(v) > 500:
            raise ValueError("Full form must be between 1 and 500 characters")
        return v.strip()


class CompanyAbbreviationUpdate(BaseModel):
    abbreviation: Optional[str] = None
    full_form: Optional[str] = None
    
    @field_validator("abbreviation")
    @classmethod
    def validate_abbreviation(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            if not v or len(v) > 50:
                raise ValueError("Abbreviation must be between 1 and 50 characters")
            return v.strip()
        return v
    
    @field_validator("full_form")
    @classmethod
    def validate_full_form(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            if not v or len(v) > 500:
                raise ValueError("Full form must be between 1 and 500 characters")
            return v.strip()
        return v


class CompanyAbbreviationResponse(BaseModel):
    id: int
    company_id: int
    abbreviation: str
    full_form: str
    source_document_id: Optional[int] = None
    source_document_title: Optional[str] = None
    is_manual: bool = False
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CompanyAbbreviationListResponse(BaseModel):
    items: list[CompanyAbbreviationResponse]
    total: int
    page: int
    page_size: int
    pages: int
```

---

## 5. API CRUD

### 5.1 Термины

| Метод | Путь | Описание | Роль | Query params |
|-------|------|----------|------|-------------|
| GET | `/api/v1/terms` | Список терминов холдинга | viewer+ | `company_id`, `search`, `page`, `page_size` |
| POST | `/api/v1/terms` | Создать термин | editor+ | — |
| PUT | `/api/v1/terms/{id}` | Обновить термин | editor+ | — |
| DELETE | `/api/v1/terms/{id}` | Удалить термин | editor+ | — |

### 5.2 Сокращения

| Метод | Путь | Описание | Роль | Query params |
|-------|------|----------|------|-------------|
| GET | `/api/v1/abbreviations` | Список сокращений | viewer+ | `company_id`, `search`, `page`, `page_size` |
| POST | `/api/v1/abbreviations` | Создать сокращение | editor+ | — |
| PUT | `/api/v1/abbreviations/{id}` | Обновить сокращение | editor+ | — |
| DELETE | `/api/v1/abbreviations/{id}` | Удалить сокращение | editor+ | — |

### 5.3 Детальное описание endpoint'ов

#### GET /api/v1/terms

```
Query parameters:
  - company_id: int (обязательный, извлекается из активной компании пользователя)
  - search: str (опциональный, поиск по term LIKE)
  - page: int (default=1)
  - page_size: int (default=20, max=100)

Response 200:
```json
{
  "items": [
    {
      "id": 1,
      "company_id": 1,
      "term": "ГСМ",
      "definition": "Горюче-смазочные материалы...",
      "source_document_id": 5,
      "source_document_title": "Регламент по учёту ГСМ",
      "is_manual": false,
      "created_at": "2026-06-28T10:00:00Z",
      "updated_at": "2026-06-28T10:00:00Z"
    }
  ],
  "total": 1,
  "page": 1,
  "page_size": 20,
  "pages": 1
}
```

#### POST /api/v1/terms

```
Request body:
```json
{
  "term": "Новый термин",
  "definition": "Определение нового термина"
}
```

Response 201:
```json
{
  "id": 2,
  "company_id": 1,
  "term": "Новый термин",
  "definition": "Определение нового термина",
  "source_document_id": null,
  "source_document_title": null,
  "is_manual": true,
  "created_at": "2026-06-28T12:00:00Z",
  "updated_at": "2026-06-28T12:00:00Z"
}
```

Error 409:
```json
{
  "detail": {
    "code": "TERM_ALREADY_EXISTS",
    "message": "Термин 'Новый термин' уже существует в данном холдинге",
    "field": "term"
  }
}
```

#### PUT /api/v1/terms/{id}

```
Request body (partial):
```json
{
  "definition": "Обновлённое определение"
}
```

Response 200: CompanyTermResponse

Error 404: { "detail": { "code": "TERM_NOT_FOUND", ... } }
Error 403: если термин принадлежит другой компании
Error 409: если новый term конфликтует с существующим

#### DELETE /api/v1/terms/{id}

```
Response 204: No Content
Error 404: { "detail": { "code": "TERM_NOT_FOUND", ... } }
Error 403: если термин принадлежит другой компании
```

### 5.4 Ролевая модель

| Endpoint | viewer | editor | admin |
|----------|--------|--------|-------|
| GET /terms | ✅ | ✅ | ✅ |
| POST /terms | ❌ | ✅ | ✅ |
| PUT /terms/{id} | ❌ | ✅ | ✅ |
| DELETE /terms/{id} | ❌ | ✅ | ✅ |
| GET /abbreviations | ✅ | ✅ | ✅ |
| POST /abbreviations | ❌ | ✅ | ✅ |
| PUT /abbreviations/{id} | ❌ | ✅ | ✅ |
| DELETE /abbreviations/{id} | ❌ | ✅ | ✅ |

Используется существующая зависимость `require_editor` для мутирующих endpoint'ов.

### 5.5 Изоляция по компании

Все endpoint'ы проверяют `company_id`:

- **GET**: `company_id` извлекается из активной компании текущего пользователя (как в существующих endpoint'ах документов). Поиск выполняется только в рамках этой компании.
- **POST/CREATE**: `company_id` при создании — из active_company_id пользователя.
- **PUT/UPDATE**: Проверка, что запись принадлежит компании пользователя.
- **DELETE**: Проверка, что запись принадлежит компании пользователя.

### 5.6 Формат ошибок

Используется существующий `ApiError` формат:

```json
{
  "detail": {
    "code": "TERM_ALREADY_EXISTS",
    "message": "Термин 'ГСМ' уже существует в данном холдинге",
    "field": "term"
  }
}
```

Коды ошибок:

| HTTP | Code | Условие |
|------|------|---------|
| 404 | TERM_NOT_FOUND | Термин с указанным ID не найден |
| 404 | ABBREVIATION_NOT_FOUND | Сокращение не найдено |
| 409 | TERM_ALREADY_EXISTS | Термин с таким именем уже существует в холдинге |
| 409 | ABBREVIATION_ALREADY_EXISTS | Сокращение уже существует |
| 403 | FOREIGN_COMPANY | Попытка изменить запись другой компании |

---

## 6. DataLoader — новые методы

```python
# backend/app/services/generators/data_loader.py

class DataLoader:
    # ... существующие методы ...
    
    async def load_company_terms_list(
        self, company_id: int, db: AsyncSession
    ) -> list[dict]:
        """Load company-wide terms from CompanyTerm table.
        
        Returns list of {"term": str, "definition": str}.
        Limited to 50 most relevant terms.
        """
        from app.models.company_term import CompanyTerm
        
        stmt = select(CompanyTerm).where(
            CompanyTerm.company_id == company_id,
        ).order_by(CompanyTerm.term.asc()).limit(50)
        
        result = await db.execute(stmt)
        terms = result.scalars().all()
        
        return [
            {"term": t.term, "definition": t.definition}
            for t in terms
        ]
    
    async def load_company_abbreviations_list(
        self, company_id: int, db: AsyncSession
    ) -> list[dict]:
        """Load company-wide abbreviations from CompanyAbbreviation table.
        
        Returns list of {"abbreviation": str, "full_form": str}.
        Limited to 20 most relevant.
        """
        from app.models.company_abbreviation import CompanyAbbreviation
        
        stmt = select(CompanyAbbreviation).where(
            CompanyAbbreviation.company_id == company_id,
        ).order_by(CompanyAbbreviation.abbreviation.asc()).limit(20)
        
        result = await db.execute(stmt)
        abbreviations = result.scalars().all()
        
        return [
            {"abbreviation": a.abbreviation, "full_form": a.full_form}
            for a in abbreviations
        ]
```

**Важно:** Существующий `load_company_terms()` продолжает загружать термины из `DocumentTerm` (для обратной совместимости Phase 1-4). Новые методы грузят из `CompanyTerm`/`CompanyAbbreviation` для V2 генератора.

---

## 7. Alembic миграция

### 7.1 Новая ревизия

```
Файл: alembic/versions/XXXX_create_company_terms_and_abbreviations.py

Изменения:
1. CREATE TABLE company_terms (
     id INTEGER PRIMARY KEY AUTOINCREMENT,
     company_id INTEGER NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
     term VARCHAR(255) NOT NULL,
     definition TEXT NOT NULL,
     source_document_id INTEGER REFERENCES documents(id) ON DELETE SET NULL,
     is_manual BOOLEAN NOT NULL DEFAULT 0,
     created_at DATETIME NOT NULL DEFAULT (datetime('now')),
     updated_at DATETIME NOT NULL DEFAULT (datetime('now')),
     UNIQUE(company_id, term)
   )
2. CREATE INDEX ix_company_terms_company_id ON company_terms(company_id)
3. CREATE TABLE company_abbreviations (
     id INTEGER PRIMARY KEY AUTOINCREMENT,
     company_id INTEGER NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
     abbreviation VARCHAR(50) NOT NULL,
     full_form VARCHAR(500) NOT NULL,
     source_document_id INTEGER REFERENCES documents(id) ON DELETE SET NULL,
     is_manual BOOLEAN NOT NULL DEFAULT 0,
     created_at DATETIME NOT NULL DEFAULT (datetime('now')),
     updated_at DATETIME NOT NULL DEFAULT (datetime('now')),
     UNIQUE(company_id, abbreviation)
   )
4. CREATE INDEX ix_company_abbreviations_company_id ON company_abbreviations(company_id)
```

### 7.2 downgrade

```
DROP TABLE company_abbreviations
DROP TABLE company_terms
```
