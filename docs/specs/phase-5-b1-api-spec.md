# Phase 5 B1: API Specification — Company Terms, Abbreviations, Generator V2

> **Проект:** SRP (Service for Regulations and Policies)
> **Фаза:** 5 / Инкремент B1 — API контракты
> **Дата:** 2026-06-28
> **Статус:** Черновик (готов к реализации)
> **Аудитория:** BE (Python/FastAPI), FE (React/TypeScript)

---

## Оглавление

1. [Контекст и цель](#1-контекст-и-цель)
2. [Базовый URL и формат](#2-базовый-url-и-формат)
3. [Pydantic схемы](#3-pydantic-схемы)
   - 3.1 CompanyTerm схемы
   - 3.2 CompanyAbbreviation схемы
   - 3.3 GenerateRequestV2
4. [REST API контракты](#4-rest-api-контракты)
   - 4.1 Company Terms CRUD
   - 4.2 Company Abbreviations CRUD
   - 4.3 Generator V2 — расширение
5. [Изменения в существующих endpoint'ах](#5-изменения-в-существующих-endpointах)
6. [Ролевая модель](#6-ролевая-модель)
7. [Формат ошибок](#7-формат-ошибок)
8. [Приложение A: Примеры ответов](#8-приложение-a-примеры-ответов)

---

## 1. Контекст и цель

### 1.1 Назначение

Данный документ описывает API-контракты для Phase 5 Increment B1.

**Новые endpoint'ы:**
- CRUD для `CompanyTerm` (общехолдинговые термины)
- CRUD для `CompanyAbbreviation` (общехолдинговые сокращения)
- Расширение `POST /api/v1/generator/generate` (V2 — новое тело запроса)

**Принципы:**
- Все endpoint'ы требуют аутентификации (JWT access token)
- Изоляция по компании (холдингу): пользователь видит/изменяет только данные своей компании
- Ролевая модель: viewer — чтение, editor+ — запись

---

## 2. Базовый URL и формат

### 2.1 Base URL

```
/api/v1
```

### 2.2 Формат дат

ISO 8601: `2026-06-28T10:00:00Z`

### 2.3 Content-Type

- Запросы: `application/json`
- Ответы: `application/json`

### 2.4 Аутентификация

Все защищённые endpoint'ы требуют заголовок:

```
Authorization: Bearer <access_token>
```

---

## 3. Pydantic схемы

### 3.1 CompanyTerm схемы

Полное описание схем в [`phase-5-b1-company-terms.md`](phase-5-b1-company-terms.md#4-pydantic-схемы).

Кратко:

| Схема | Назначение |
|-------|-----------|
| `CompanyTermCreate` | Создание термина: `{term: str, definition: str}` |
| `CompanyTermUpdate` | Обновление термина: `{term?: str, definition?: str}` (partial) |
| `CompanyTermResponse` | Ответ: `{id, company_id, term, definition, source_document_id, source_document_title, is_manual, created_at, updated_at}` |
| `CompanyTermListResponse` | Пагинированный список: `{items: CompanyTermResponse[], total, page, page_size, pages}` |

### 3.2 CompanyAbbreviation схемы

| Схема | Назначение |
|-------|-----------|
| `CompanyAbbreviationCreate` | Создание: `{abbreviation: str, full_form: str}` |
| `CompanyAbbreviationUpdate` | Обновление: `{abbreviation?: str, full_form?: str}` (partial) |
| `CompanyAbbreviationResponse` | Ответ: `{id, company_id, abbreviation, full_form, source_document_id, source_document_title, is_manual, created_at, updated_at}` |
| `CompanyAbbreviationListResponse` | Пагинированный список |

### 3.3 GenerateRequestV2

```python
# backend/app/schemas/generator.py

from typing import Optional

from pydantic import BaseModel, field_validator


class GenerateRequestV2(BaseModel):
    """Request body for V2 generation endpoint."""
    topic: str
    document_type: str = "regulation"
    company_id: int
    draft_file_id: Optional[int] = None
    influence_document_ids: Optional[list[int]] = None
    search_enabled: bool = True

    @field_validator("topic")
    @classmethod
    def validate_topic(cls, v: str) -> str:
        if not v or len(v) < 20:
            raise ValueError("Topic must be at least 20 characters")
        return v.strip()

    @field_validator("document_type")
    @classmethod
    def validate_document_type(cls, v: str) -> str:
        allowed = {"regulation", "order", "provision", "policy", "directive"}
        if v not in allowed:
            raise ValueError(
                f"Invalid document_type '{v}'. "
                f"Allowed: {', '.join(sorted(allowed))}"
            )
        return v
    
    @field_validator("company_id")
    @classmethod
    def validate_company_id(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("company_id must be a positive integer")
        return v
```

**Ответ** — без изменений, используется существующий `DocumentResponse`.

---

## 4. REST API контракты

### 4.1 Company Terms CRUD

#### GET /api/v1/terms — список терминов

```
GET /api/v1/terms?company_id=1&search=ГСМ&page=1&page_size=20

Query parameters:
  - company_id: int (обязательный, если не указан — берётся из active_company пользователя)
  - search: str (опциональный, поиск по term, регистронезависимый)
  - page: int (default=1, min=1)
  - page_size: int (default=20, min=1, max=100)

Response 200:
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

Errors:
  - 401: Not authenticated
  - 403: No active company (если company_id не указан и нет active_company)
```

#### POST /api/v1/terms — создать термин

```
POST /api/v1/terms
Content-Type: application/json

{
  "term": "Новый термин",
  "definition": "Определение нового термина"
}

Response 201:
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

Errors:
  - 400: Validation error (пустой term, пустое определение)
  - 401: Not authenticated
  - 403: No active company или роль ниже editor
  - 409: TERM_ALREADY_EXISTS
```

#### PUT /api/v1/terms/{id} — обновить термин

```
PUT /api/v1/terms/2
Content-Type: application/json

{
  "definition": "Обновлённое определение"
}

Response 200: CompanyTermResponse

Errors:
  - 400: Validation error
  - 401: Not authenticated
  - 403: FOREIGN_COMPANY (термин другой компании) или роль ниже editor
  - 404: TERM_NOT_FOUND
  - 409: TERM_ALREADY_EXISTS (при смене term на существующий)
```

#### DELETE /api/v1/terms/{id} — удалить термин

```
DELETE /api/v1/terms/2

Response 204: No Content

Errors:
  - 401: Not authenticated
  - 403: FOREIGN_COMPANY или роль ниже editor
  - 404: TERM_NOT_FOUND
```

### 4.2 Company Abbreviations CRUD

#### GET /api/v1/abbreviations — список сокращений

```
GET /api/v1/abbreviations?company_id=1&search=ГСМ&page=1&page_size=20

Response 200:
{
  "items": [
    {
      "id": 1,
      "company_id": 1,
      "abbreviation": "ГСМ",
      "full_form": "Горюче-смазочные материалы",
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

#### POST /api/v1/abbreviations — создать сокращение

```
POST /api/v1/abbreviations
Content-Type: application/json

{
  "abbreviation": "МОЛ",
  "full_form": "Материально-ответственное лицо"
}

Response 201: CompanyAbbreviationResponse (is_manual=true)

Errors:
  - 400: Validation error
  - 401: Not authenticated
  - 403: No active company или роль ниже editor
  - 409: ABBREVIATION_ALREADY_EXISTS
```

#### PUT /api/v1/abbreviations/{id} — обновить сокращение

```
PUT /api/v1/abbreviations/2
Content-Type: application/json

{
  "full_form": "Обновлённая расшифровка"
}

Response 200: CompanyAbbreviationResponse

Errors:
  - 400, 401, 403, 404, 409 (аналогично терминам)
```

#### DELETE /api/v1/abbreviations/{id} — удалить сокращение

```
DELETE /api/v1/abbreviations/2

Response 204: No Content

Errors:
  - 401, 403, 404
```

### 4.3 Generator V2 — расширение POST /api/v1/generator/generate

#### Текущий endpoint (Phase 1 — сохраняется для обратной совместимости)

```
POST /api/v1/generator/generate
Content-Type: multipart/form-data

Параметры (form-data):
  - context: str (обязательный)
  - draft_files: File[] (опциональный)
  - influencing_document_ids: str (JSON-массив, опциональный)
```

#### Новый endpoint V2 (Phase 5 B1)

Новый endpoint может быть реализован двумя способами:

**Вариант A (рекомендуемый):** Новый путь `/api/v1/generator/generate-v2` с JSON body.

```
POST /api/v1/generator/generate-v2
Content-Type: application/json

{
  "topic": "Регламент по ГСМ",
  "document_type": "regulation",
  "company_id": 1,
  "draft_file_id": null,
  "influence_document_ids": [5, 12],
  "search_enabled": true
}

Response 200: DocumentResponse
{
  "id": 42,
  "company_id": 1,
  "title": "Регламент по горюче-смазочным материалам",
  "description": "Настоящий регламент...",
  "status": "draft",
  "current_version": {
    "id": 100,
    "version_number": 1,
    "file_type": "docx",
    "file_size": 45000,
    "created_at": "2026-06-28T12:00:00Z"
  },
  "stats": {
    "sections_count": 8,
    "terms_count": 5,
    "abbreviations_count": 3,
    "versions_count": 1
  },
  "created_at": "2026-06-28T12:00:00Z",
  "updated_at": "2026-06-28T12:00:00Z"
}

Errors:
  - 400: Validation error (topic < 20 chars, invalid document_type)
  - 401: Not authenticated
  - 403: No active company
  - 422: LLM generation failed (после retries)
```

**Вариант B:** Модифицировать существующий endpoint, добавив новые поля. **Не рекомендуется**, так как сломает обратную совместимость.

> **Решение:** Используем Вариант A — новый endpoint `/generate-v2`. Существующий `/generate` остаётся для Phase 1 клиентов (если есть).

#### Детали реализации generate-v2

```python
# backend/app/api/v1/generator.py (дополнение)

from app.schemas.generator import GenerateRequestV2

@router.post("/generate-v2", response_model=DocumentResponse)
async def generate_document_v2(
    request: GenerateRequestV2,
    user: User = Depends(require_active_company),
    db: AsyncSession = Depends(get_db),
):
    """Generate a document using all available knowledge sources (V2).
    
    Accepts JSON body with:
    - topic: Document topic description
    - document_type: Type of document (regulation, order, provision, policy, directive)
    - company_id: Company (holding) ID
    - draft_file_id: Optional ID of an uploaded draft file
    - influence_document_ids: Optional list of influencing document IDs
    - search_enabled: Whether to search the web (default: true)
    
    Returns the generated document metadata.
    """
    # Verify user belongs to the requested company
    if request.company_id != user.active_company_id:
        raise ForbiddenException(message="Company mismatch")
    
    # Resolve draft file path if draft_file_id provided
    draft_file_path = None
    if request.draft_file_id:
        draft_file_path = await _resolve_draft_file(
            request.draft_file_id, request.company_id, db
        )
    
    result = await generator_service.generate_document(
        topic=request.topic,
        company_id=request.company_id,
        document_type=request.document_type,
        user_id=user.id,
        draft_file_path=draft_file_path,
        influence_document_ids=request.influence_document_ids,
        search_enabled=request.search_enabled,
        db=db,
    )
    return result


async def _resolve_draft_file(
    file_id: int, company_id: int, db: AsyncSession
) -> str | None:
    """Resolve draft file ID to file path in storage.
    
    Loads DocumentVersion or temp upload by ID, verifies ownership,
    returns the file path on disk.
    """
    from app.models.document_version import DocumentVersion
    
    stmt = select(DocumentVersion).where(
        DocumentVersion.id == file_id,
        DocumentVersion.document.has(company_id=company_id),
    )
    result = await db.execute(stmt)
    version = result.scalar_one_or_none()
    
    if version and version.file_path:
        return version.file_path
    
    return None
```

---

## 5. Изменения в существующих endpoint'ах

### 5.1 Никаких изменений

Следующие endpoint'ы **не изменяются** в B1:

| Endpoint | Причина |
|----------|---------|
| `GET /api/v1/documents/...` | Весь CRUD документов остаётся без изменений |
| `POST /api/v1/generator/generate` | Сохраняется для обратной совместимости |
| `GET /api/v1/analysis/...` | Анализ pipeline остаётся без изменений |
| `POST /api/v1/auth/...` | Аутентификация без изменений |

### 5.2 Подключение нового router

В `backend/app/api/v1/router.py` добавляем:

```python
from app.api.v1.company_terms import router as company_terms_router

# ...

router.include_router(company_terms_router)  # /api/v1/terms, /api/v1/abbreviations
```

### 5.3 Router структура

```python
# backend/app/api/v1/company_terms.py

from fastapi import APIRouter

router = APIRouter(tags=["company-terms"])

# GET /api/v1/terms
# POST /api/v1/terms
# PUT /api/v1/terms/{id}
# DELETE /api/v1/terms/{id}
# GET /api/v1/abbreviations
# POST /api/v1/abbreviations
# PUT /api/v1/abbreviations/{id}
# DELETE /api/v1/abbreviations/{id}
```

---

## 6. Ролевая модель

| Endpoint | viewer | editor | admin | Deps |
|----------|--------|--------|-------|------|
| GET /terms | ✅ | ✅ | ✅ | `require_active_company` |
| POST /terms | ❌ | ✅ | ✅ | `require_editor` |
| PUT /terms/{id} | ❌ | ✅ | ✅ | `require_editor` |
| DELETE /terms/{id} | ❌ | ✅ | ✅ | `require_editor` |
| GET /abbreviations | ✅ | ✅ | ✅ | `require_active_company` |
| POST /abbreviations | ❌ | ✅ | ✅ | `require_editor` |
| PUT /abbreviations/{id} | ❌ | ✅ | ✅ | `require_editor` |
| DELETE /abbreviations/{id} | ❌ | ✅ | ✅ | `require_editor` |
| POST /generator/generate-v2 | ❌ | ✅ | ✅ | `require_editor` |

**Примечание:** Для V2 генерации требуется `editor+` (создание документа — мутирующая операция). Существующий `POST /generator/generate` использует `require_active_company` (чтобы viewer мог загружать в реестр).

---

## 7. Формат ошибок

Используется существующий формат `ApiError`:

```json
{
  "detail": {
    "code": "ERROR_CODE",
    "message": "Human-readable error message",
    "field": "field_name"
  }
}
```

### 7.1 Коды ошибок для CompanyTerm/CompanyAbbreviation

| HTTP | Code | Field | Описание |
|------|------|-------|----------|
| 400 | VALIDATION_ERROR | term | Пустой term или >255 символов |
| 400 | VALIDATION_ERROR | definition | Пустое определение |
| 400 | VALIDATION_ERROR | abbreviation | Пустое сокращение или >50 символов |
| 400 | VALIDATION_ERROR | full_form | Пустая расшифровка или >500 символов |
| 404 | TERM_NOT_FOUND | id | Термин с указанным ID не найден |
| 404 | ABBREVIATION_NOT_FOUND | id | Сокращение с указанным ID не найден |
| 409 | TERM_ALREADY_EXISTS | term | Термин уже существует в данном холдинге |
| 409 | ABBREVIATION_ALREADY_EXISTS | abbreviation | Сокращение уже существует в данном холдинге |
| 403 | FOREIGN_COMPANY | id | Попытка изменить запись другой компании |

### 7.2 Коды ошибок для Generator V2

| HTTP | Code | Field | Описание |
|------|------|-------|----------|
| 400 | VALIDATION_ERROR | topic | Пустая тема или <20 символов |
| 400 | VALIDATION_ERROR | document_type | Недопустимый тип документа |
| 400 | VALIDATION_ERROR | company_id | Отрицательный или нулевой company_id |
| 403 | COMPANY_MISMATCH | company_id | user.active_company_id != request.company_id |
| 422 | GENERATION_FAILED | — | Ошибка LLM после всех retries |

---

## 8. Приложение A: Примеры ответов

### A.1 Успешное создание термина

```
Request:
POST /api/v1/terms
Authorization: Bearer eyJ...
Content-Type: application/json

{
  "term": "ERP-система",
  "definition": "Корпоративная информационная система управления ресурсами предприятия"
}

Response: 201
{
  "id": 10,
  "company_id": 1,
  "term": "ERP-система",
  "definition": "Корпоративная информационная система управления ресурсами предприятия",
  "source_document_id": null,
  "source_document_title": null,
  "is_manual": true,
  "created_at": "2026-06-28T14:30:00Z",
  "updated_at": "2026-06-28T14:30:00Z"
}
```

### A.2 Конфликт при создании дубликата

```
Request:
POST /api/v1/terms
{
  "term": "ERP-система",
  "definition": "Другое определение"
}

Response: 409
{
  "detail": {
    "code": "TERM_ALREADY_EXISTS",
    "message": "Термин 'ERP-система' уже существует в данном холдинге",
    "field": "term"
  }
}
```

### A.3 Поиск терминов

```
Request:
GET /api/v1/terms?search=ерп&page=1&page_size=10

Response: 200
{
  "items": [
    {
      "id": 10,
      "company_id": 1,
      "term": "ERP-система",
      "definition": "Корпоративная информационная система...",
      "source_document_id": null,
      "source_document_title": null,
      "is_manual": true,
      "created_at": "2026-06-28T14:30:00Z",
      "updated_at": "2026-06-28T14:30:00Z"
    }
  ],
  "total": 1,
  "page": 1,
  "page_size": 10,
  "pages": 1
}
```

### A.4 Генерация документа V2 (успех)

```
Request:
POST /api/v1/generator/generate-v2
{
  "topic": "Регламент по ведению учёта горюче-смазочных материалов на предприятии",
  "document_type": "regulation",
  "company_id": 1,
  "draft_file_id": null,
  "influence_document_ids": [5, 12],
  "search_enabled": true
}

Response: 200
{
  "id": 50,
  "company_id": 1,
  "title": "Регламент по учёту горюче-смазочных материалов",
  "description": "Настоящий регламент устанавливает порядок приобретения, хранения, учёта и списания ГСМ...",
  "status": "draft",
  "created_by": {"id": 1, "email": "user@example.com"},
  "was_analyzed": false,
  "analysis_status": "none",
  "current_version": {
    "id": 120,
    "version_number": 1,
    "file_type": "docx",
    "file_size": 52300,
    "created_at": "2026-06-28T15:00:00Z"
  },
  "stats": {
    "sections_count": 10,
    "tables_count": 3,
    "terms_count": 6,
    "abbreviations_count": 4,
    "versions_count": 1
  },
  "created_at": "2026-06-28T15:00:00Z",
  "updated_at": "2026-06-28T15:00:00Z"
}
```

### A.5 Валидационная ошибка генератора V2

```
Request:
POST /api/v1/generator/generate-v2
{
  "topic": "ГСМ",
  "document_type": "invalid_type",
  "company_id": 1
}

Response: 400
{
  "detail": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid document_type 'invalid_type'. Allowed: directive, order, policy, provision, regulation",
    "field": "document_type"
  }
}
```
