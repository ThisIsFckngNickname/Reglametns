# Increment B: API и контракты данных — Реестр документов + Загрузка и парсинг Word/PDF

> **Проект:** SRP (Service for Regulations and Policies)
> **Инкремент:** B — Реестр документов + Загрузка и парсинг Word/PDF
> **Дата:** 2026-06-20
> **Статус:** Черновик (готов к реализации)
> **Аудитория:** BE (Python/FastAPI), FE (React/TypeScript)
> **Зависимости:** Increment A (аутентификация, холдинги, мультитенантность)

---

## Оглавление

1. [Контекст и цель](#1-контекст-и-цель)
2. [Базовый URL и формат](#2-базовый-url-и-формат)
3. [Новые модели данных (SQLAlchemy)](#3-новые-модели-данных-sqlalchemy)
4. [Pydantic схемы (Request/Response)](#4-pydantic-схемы-requestresponse)
5. [REST API контракты](#5-rest-api-контракты)
6. [Storage Service — LocalFileStorage](#6-storage-service--localfilestorage)
7. [Parser Service — DocumentParser](#7-parser-service--documentparser)
8. [Бизнес-логика: Upload Flow](#8-бизнес-логика-upload-flow)
9. [Дополнительные зависимости](#9-дополнительные-зависимости)
10. [Единый формат ошибок — расширение](#10-единый-формат-ошибок--расширение)
11. [Приложение A: Примеры ответов](#11-приложение-a-примеры-ответов)
12. [Приложение B: Статус-коды](#12-приложение-b-статус-коды)
13. [Приложение C: Рекомендации по реализации](#13-приложение-c-рекомендации-по-реализации)

---

## 1. Контекст и цель

### 1.1 Назначение инкремента

Пользователь может загрузить документ (Word .docx или PDF), сервис парсит его структуру (оглавление, разделы, подразделы, таблицы) и извлекает термины/сокращения. Документ отображается в реестре со статусом, отображается карточка документа с древовидной структурой разделов.

### 1.2 Бизнес-ценность

- Автоматизация анализа существующих регламентов — сокращение ручного труда
- Формирование базы знаний холдинга: каждый загруженный документ становится источником терминов и структуры
- Фундамент для генератора (Increment C): генератор будет использовать распаршенные документы как обучающие примеры

### 1.3 Принятые решения (ADR-0001)

- **Приоритет парсинга:** Word (.docx) — первый, PDF — второй (best effort)
- **PDF:** таблицы извлекаем; сноски, колонтитулы — нет
- **Хранение:** локальная файловая система (`/storage/documents/`)
- **Ограничение размера файла:** 20MB на MVP
- **Мультитенантность:** документы изолированы по `holding_id`

### 1.4 Границы инкремента

**Входит в Scope:**
- Загрузка Word/PDF + парсинг структуры (разделы, таблицы)
- Извлечение терминов и определений, сокращений
- CRUD документов (реестр, карточка, обновление статуса, архивирование)
- Версионность: первая версия создаётся при загрузке
- Скачивание файла версии
- Просмотр древовидной структуры разделов, таблиц, терминов, сокращений
- Локальное файловое хранилище

**Не входит в Scope (Out of scope):**
- Ручное добавление влияющих документов (Increment D)
- Создание новой версии при редактировании (Increment D)
- Реестр внутренних приказов (Increment D)
- MCP-сервер (Increment E)
- Сложный парсинг PDF (объединённые ячейки, сноски)
- Семантический граф связей (визуальный — Stage 2)
- Сравнение версий (diff)

---

## 2. Базовый URL и формат

### 2.1 Base URL

```
/api/v1
```

Все endpoint'ы реестра документов монтируются на `/api/v1/documents`.

### 2.2 Формат дат

Даты передаются в ISO 8601: `2026-06-20T14:30:00Z`

### 2.3 Content-Type

| Направление | Content-Type |
|-------------|-------------|
| Запросы (кроме upload) | `application/json` |
| Upload запрос | `multipart/form-data` |
| Ответы (кроме download) | `application/json` |
| Download ответ | `application/octet-stream` или оригинальный MIME |

### 2.4 Аутентификация

Все защищённые endpoint'ы требуют заголовок:

```
Authorization: Bearer <access_token>
```

Исключений нет — все документы привязаны к холдингу и пользователю.

### 2.5 Мультитенантность

- Все документы привязаны к `holding_id`
- `holding_id` определяется по `user.active_holding_id` из JWT-пользователя
- Если у пользователя не выбран активный холдинг → ошибка `NO_ACTIVE_HOLDING`
- Пользователь видит только документы своего текущего холдинга

---

## 3. Новые модели данных (SQLAlchemy)

### 3.1 `documents`

Основная таблица реестра документов.

| Колонка       | Тип                | Constraints                                        | Описание                              |
|---------------|-------------------|----------------------------------------------------|---------------------------------------|
| id            | Integer            | PK, autoincrement                                  | Уникальный ID                         |
| holding_id    | Integer            | FK -> holdings.id, NOT NULL, INDEX                 | Холдинг-владелец документа            |
| title         | String(500)        | NOT NULL                                           | Название документа                    |
| description   | Text               | NULLABLE                                           | Описание документа                    |
| status        | String(20)         | NOT NULL, default='draft'                          | Статус: draft/review/approved/archived|
| created_by    | Integer            | FK -> users.id, NOT NULL                           | Кто создал документ                   |
| created_at    | DateTime           | NOT NULL, default=_utcnow                          | Дата создания                         |
| updated_at    | DateTime           | NOT NULL, default=_utcnow, onupdate=_utcnow        | Дата обновления                       |

**Индексы:**
- `ix_documents_holding_id` — по `holding_id` для фильтрации по холдингу
- `ix_documents_status` — по `status` для фильтрации по статусу
- `ix_documents_created_at` — по `created_at` для сортировки

**Ограничения:**
- `status` — CHECK IN ('draft', 'review', 'approved', 'archived')
- `FK -> holdings.id` ON DELETE RESTRICT (нельзя удалить холдинг с документами)
- `FK -> users.id` ON DELETE RESTRICT

### 3.2 `document_versions`

Версии файлов документа. Каждый документ может иметь несколько версий.

| Колонка        | Тип                | Constraints                                        | Описание                              |
|----------------|-------------------|----------------------------------------------------|---------------------------------------|
| id             | Integer            | PK, autoincrement                                  | Уникальный ID                         |
| document_id    | Integer            | FK -> documents.id, NOT NULL, INDEX                | Документ                              |
| version_number | Integer            | NOT NULL                                           | Номер версии (1, 2, 3...)             |
| file_path      | String(500)        | NOT NULL                                           | Относительный путь в storage          |
| file_type      | String(10)         | NOT NULL                                           | `docx` или `pdf`                      |
| file_size      | Integer            | NOT NULL                                           | Размер в байтах                       |
| mime_type      | String(100)        | NOT NULL                                           | MIME-тип файла                        |
| uploaded_by    | Integer            | FK -> users.id, NOT NULL                           | Кто загрузил версию                   |
| created_at     | DateTime           | NOT NULL, default=_utcnow                          | Дата загрузки                         |

**Индексы:**
- `ix_document_versions_document_id` — по `document_id`
- `uq_document_version` — UNIQUE(document_id, version_number)

**Ограничения:**
- `FK -> documents.id` ON DELETE CASCADE
- `FK -> users.id` ON DELETE RESTRICT
- `UNIQUE (document_id, version_number)` — уникальная пара

### 3.3 `document_sections`

Разделы документа с поддержкой иерархии (parent-child).

| Колонка              | Тип                | Constraints                                        | Описание                              |
|----------------------|-------------------|----------------------------------------------------|---------------------------------------|
| id                   | Integer            | PK, autoincrement                                  | Уникальный ID                         |
| document_version_id  | Integer            | FK -> document_versions.id, NOT NULL, INDEX        | Версия документа                      |
| parent_id            | Integer            | FK -> document_sections.id, NULLABLE               | Родительский раздел (self-ref)        |
| title                | String(500)        | NOT NULL                                           | Заголовок раздела                     |
| level                | Integer            | NOT NULL                                           | Уровень вложенности (1-6)             |
| order_num            | Integer            | NOT NULL                                           | Порядок в рамках parent               |
| content              | Text               | NULLABLE                                           | Текст секции/параграфа                |

**Индексы:**
- `ix_document_sections_version_id` — по `document_version_id`
- `ix_document_sections_parent_id` — по `parent_id`
- `ix_document_sections_version_parent` — композитный (document_version_id, parent_id)

**Ограничения:**
- `FK -> document_versions.id` ON DELETE CASCADE
- `FK -> document_sections.id` (self-ref) ON DELETE SET NULL
- `level` — CHECK BETWEEN 1 AND 6

### 3.4 `document_tables`

Таблицы, извлечённые из документа.

| Колонка              | Тип                | Constraints                                        | Описание                              |
|----------------------|-------------------|----------------------------------------------------|---------------------------------------|
| id                   | Integer            | PK, autoincrement                                  | Уникальный ID                         |
| document_version_id  | Integer            | FK -> document_versions.id, NOT NULL               | Версия документа                      |
| section_id           | Integer            | FK -> document_sections.id, NULLABLE               | Раздел, в котором находится таблица   |
| caption              | String(500)        | NULLABLE                                           | Подпись/название таблицы              |
| order_num            | Integer            | NOT NULL                                           | Порядковый номер таблицы              |
| html_content         | Text               | NOT NULL                                           | Таблица в HTML-формате                |
| rows_count           | Integer            | NULLABLE                                           | Количество строк                      |
| cols_count           | Integer            | NULLABLE                                           | Количество столбцов                   |

**Индексы:**
- `ix_document_tables_version_id` — по `document_version_id`
- `ix_document_tables_section_id` — по `section_id`

**Ограничения:**
- `FK -> document_versions.id` ON DELETE CASCADE
- `FK -> document_sections.id` ON DELETE SET NULL

### 3.5 `document_terms`

Термины и определения, извлечённые из документа.

| Колонка    | Тип                | Constraints                                        | Описание                  |
|-----------|--------------------|----------------------------------------------------|---------------------------|
| id         | Integer            | PK, autoincrement                                  | Уникальный ID             |
| document_id| Integer            | FK -> documents.id, NOT NULL                      | Документ                  |
| term       | String(500)        | NOT NULL                                           | Термин                    |
| definition | Text               | NOT NULL                                           | Определение термина       |

**Индексы:**
- `ix_document_terms_document_id` — по `document_id`
- `ix_document_terms_term` — по `term` для поиска

**Примечание:** Один и тот же термин может по-разному определяться в разных документах, поэтому UNIQUE constraint на (document_id, term) не устанавливаем.

**Ограничения:**
- `FK -> documents.id` ON DELETE CASCADE

### 3.6 `document_abbreviations`

Сокращения и их расшифровки, извлечённые из документа.

| Колонка      | Тип                | Constraints                                        | Описание                  |
|-------------|--------------------|----------------------------------------------------|---------------------------|
| id           | Integer            | PK, autoincrement                                  | Уникальный ID             |
| document_id  | Integer            | FK -> documents.id, NOT NULL                      | Документ                  |
| abbreviation | String(50)         | NOT NULL                                           | Сокращение                |
| full_form    | String(500)        | NOT NULL                                           | Полная форма/расшифровка  |

**Индексы:**
- `ix_document_abbreviations_document_id` — по `document_id`
- `ix_document_abbreviations_abbr` — по `abbreviation` для поиска

**Ограничения:**
- `FK -> documents.id` ON DELETE CASCADE

### 3.7 ER-диаграмма

```
┌────────────────────┐
│     documents       │
├────────────────────┤
│ id (PK)            │──1:N──┐
│ holding_id (FK)    │       │
│ title              │       │
│ description        │       │
│ status             │       │
│ created_by (FK)    │       │
│ created_at         │       │
│ updated_at         │       │
└────────────────────┘       │
        │ 1:N                │
        ▼                    │
┌────────────────────┐       │
│  document_versions  │       │
├────────────────────┤       │
│ id (PK)            │       │
│ document_id (FK)   │──1:N──┘
│ version_number(UQ) │
│ file_path          │
│ file_type          │
│ file_size          │
│ mime_type          │
│ uploaded_by (FK)   │
│ created_at         │
│ UNIQUE(doc,ver)    │
└────────────────────┘
        │ 1:N
        ▼
┌────────────────────┐       ┌────────────────────┐
│ document_sections   │       │  document_tables    │
├────────────────────┤       ├────────────────────┤
│ id (PK)            │       │ id (PK)            │
│ document_version_id│       │ document_version_id│
│ parent_id (FK,self)│       │ section_id (FK)    │
│ title              │       │ caption            │
│ level (1-6)        │       │ order_num          │
│ order_num          │       │ html_content       │
│ content            │       │ rows_count         │
└────────────────────┘       │ cols_count         │
                             └────────────────────┘

┌────────────────────┐       ┌────────────────────┐
│  document_terms     │       │document_abbreviations│
├────────────────────┤       ├────────────────────┤
│ id (PK)            │       │ id (PK)            │
│ document_id (FK)   │       │ document_id (FK)   │
│ term               │       │ abbreviation       │
│ definition         │       │ full_form          │
└────────────────────┘       └────────────────────┘
```

---

## 4. Pydantic схемы (Request/Response)

### 4.1 Document Schemas

```python
# app/schemas/document.py

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


# ---- Enums ----

class DocumentStatus(str, enum.Enum):
    DRAFT = "draft"
    REVIEW = "review"
    APPROVED = "approved"
    ARCHIVED = "archived"


# ---- Request ----

class DocumentUploadResponse(BaseModel):
    id: int
    title: str
    status: DocumentStatus
    file_type: str
    file_size: int
    sections_count: int = 0
    tables_count: int = 0
    terms_count: int = 0
    abbreviations_count: int = 0
    created_at: datetime

    model_config = {"from_attributes": True}


class DocumentUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=500)
    description: Optional[str] = None
    status: Optional[DocumentStatus] = None


# ---- Responses ----

class UserBrief(BaseModel):
    id: int
    email: str

    model_config = {"from_attributes": True}


class DocumentListItem(BaseModel):
    id: int
    title: str
    status: DocumentStatus
    file_type: str
    file_size: int
    version_number: int
    has_terms: bool = False
    has_abbreviations: bool = False
    created_by: UserBrief
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DocumentListResponse(BaseModel):
    items: list[DocumentListItem]
    total: int
    page: int
    page_size: int
    pages: int


class VersionBrief(BaseModel):
    id: int
    version_number: int
    file_type: str
    file_size: int
    created_at: datetime

    model_config = {"from_attributes": True}


class DocumentStats(BaseModel):
    sections_count: int = 0
    tables_count: int = 0
    terms_count: int = 0
    abbreviations_count: int = 0
    versions_count: int = 0


class DocumentDetail(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    status: DocumentStatus
    holding_id: int
    created_by: UserBrief
    current_version: Optional[VersionBrief] = None
    stats: DocumentStats
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ---- Version ----

class VersionListItem(BaseModel):
    id: int
    version_number: int
    file_type: str
    file_size: int
    uploaded_by: UserBrief
    sections_count: int = 0
    tables_count: int = 0
    created_at: datetime

    model_config = {"from_attributes": True}


class VersionListResponse(BaseModel):
    items: list[VersionListItem]


# ---- Section ----

class SectionNode(BaseModel):
    id: int
    title: str
    level: int
    order_num: int
    content: Optional[str] = None
    children: list["SectionNode"] = []

    model_config = {"from_attributes": True}


class SectionTreeResponse(BaseModel):
    document_id: int
    version_id: int
    sections: list[SectionNode]


# ---- Term ----

class TermItem(BaseModel):
    id: int
    term: str
    definition: str

    model_config = {"from_attributes": True}


class TermsResponse(BaseModel):
    document_id: int
    terms: list[TermItem]


# ---- Abbreviation ----

class AbbreviationItem(BaseModel):
    id: int
    abbreviation: str
    full_form: str

    model_config = {"from_attributes": True}


class AbbreviationsResponse(BaseModel):
    document_id: int
    abbreviations: list[AbbreviationItem]


# ---- Table ----

class TableItem(BaseModel):
    id: int
    caption: Optional[str] = None
    section_title: Optional[str] = None
    order_num: int
    rows_count: Optional[int] = None
    cols_count: Optional[int] = None
    html_content: str

    model_config = {"from_attributes": True}


class TablesResponse(BaseModel):
    document_id: int
    version_id: int
    tables: list[TableItem]
```

### 4.2 Parse Schemas

```python
# app/schemas/parse.py

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ParsedSection:
    title: str
    level: int  # 1-6
    order_num: int
    content: Optional[str] = None
    parent_order_path: Optional[str] = None  # путь для восстановления иерархии
    children: list["ParsedSection"] = field(default_factory=list)


@dataclass
class ParsedTable:
    caption: Optional[str]
    order_num: int
    html_content: str
    rows_count: Optional[int] = None
    cols_count: Optional[int] = None
    section_order_path: Optional[str] = None  # привязка к разделу


@dataclass
class ParsedTerm:
    term: str
    definition: str


@dataclass
class ParsedAbbreviation:
    abbreviation: str
    full_form: str


@dataclass
class ParseResult:
    sections: list[ParsedSection]
    tables: list[ParsedTable]
    terms: list[ParsedTerm]
    abbreviations: list[ParsedAbbreviation]
```

---

## 5. REST API контракты

### 5.1 Загрузка документа

#### `POST /api/v1/documents/upload`

Загружает новый документ (Word .docx или PDF), парсит его структуру, сохраняет метаданные и извлечённые элементы (разделы, таблицы, термины, сокращения).

**Заголовки:**

```
Authorization: Bearer <access_token>
Content-Type: multipart/form-data
```

**Request (multipart/form-data):**

| Поле         | Тип    | Обязательно | Описание                                    |
|-------------|--------|-------------|---------------------------------------------|
| file        | File   | да          | Файл документа (.docx или .pdf), макс 20MB  |
| title       | string | нет         | Название документа. Если не указан — имя файла без расширения |
| description | string | нет         | Описание документа                          |

**Успешный ответ:** `201 Created`

```json
{
  "id": 1,
  "title": "Регламент документооборота",
  "status": "draft",
  "file_type": "docx",
  "file_size": 102400,
  "sections_count": 12,
  "tables_count": 3,
  "terms_count": 25,
  "abbreviations_count": 5,
  "created_at": "2026-06-20T10:00:00Z"
}
```

| Поле                | Тип    | Описание                                   |
|---------------------|--------|--------------------------------------------|
| id                  | int    | ID созданного документа                    |
| title               | string | Название документа                         |
| status              | string | Всегда `"draft"` при первой загрузке       |
| file_type           | string | `"docx"` или `"pdf"`                       |
| file_size           | int    | Размер файла в байтах                      |
| sections_count      | int    | Количество извлечённых разделов            |
| tables_count        | int    | Количество извлечённых таблиц              |
| terms_count         | int    | Количество извлечённых терминов            |
| abbreviations_count | int    | Количество извлечённых сокращений          |
| created_at          | string | ISO 8601 дата создания                     |

**Ошибки:**

| Код  | Условие                                | detail.code          |
|------|----------------------------------------|----------------------|
| 400  | Неверный формат файла (не docx/pdf)    | INVALID_FILE_TYPE    |
| 400  | Файл повреждён или не читается         | PARSE_ERROR          |
| 400  | Не выбран активный холдинг             | NO_ACTIVE_HOLDING    |
| 401  | Не авторизован                         | UNAUTHORIZED         |
| 413  | Файл превышает 20MB                    | FILE_TOO_LARGE       |
| 422  | Невалидные данные (например, имя пустое после трима) | VALIDATION_ERROR |

**Пример cURL:**

```bash
curl -X POST http://localhost:8000/api/v1/documents/upload \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..." \
  -F "file=@reglament.docx" \
  -F "title=Регламент документооборота" \
  -F "description=Основной регламент компании"
```

---

### 5.2 Список документов (Реестр)

#### `GET /api/v1/documents`

Возвращает список документов текущего холдинга с пагинацией, фильтрацией и поиском.

**Заголовки:**

```
Authorization: Bearer <access_token>
```

**Query parameters:**

| Параметр  | Тип    | Обязательно | Дефолт   | Описание                                      |
|-----------|--------|-------------|----------|-----------------------------------------------|
| status    | string | нет         | —        | Фильтр по статусу: draft/review/approved/archived |
| search    | string | нет         | —        | Поиск по title (частичное совпадение)         |
| page      | int    | нет         | 1        | Номер страницы                                |
| page_size | int    | нет         | 20       | Размер страницы (макс 100)                    |

**Успешный ответ:** `200 OK`

```json
{
  "items": [
    {
      "id": 1,
      "title": "Регламент документооборота",
      "status": "draft",
      "file_type": "docx",
      "file_size": 102400,
      "version_number": 1,
      "has_terms": true,
      "has_abbreviations": true,
      "created_by": {
        "id": 1,
        "email": "user@example.com"
      },
      "created_at": "2026-06-20T10:00:00Z",
      "updated_at": "2026-06-20T11:00:00Z"
    }
  ],
  "total": 1,
  "page": 1,
  "page_size": 20,
  "pages": 1
}
```

| Поле         | Тип       | Описание                                   |
|-------------|-----------|--------------------------------------------|
| items       | array     | Массив документов                          |
| total       | int       | Общее количество записей (без пагинации)   |
| page        | int       | Текущая страница                           |
| page_size   | int       | Размер страницы                            |
| pages       | int       | Количество страниц                         |

**Поля `items[]`:**

| Поле              | Тип       | Описание                                   |
|------------------|-----------|--------------------------------------------|
| id               | int       | ID документа                               |
| title            | string    | Название                                   |
| status           | string    | Статус                                     |
| file_type        | string    | Тип файла последней версии                 |
| file_size        | int       | Размер файла последней версии              |
| version_number   | int       | Номер последней версии                     |
| has_terms        | bool      | Есть ли извлечённые термины                |
| has_abbreviations| bool      | Есть ли извлечённые сокращения             |
| created_by       | object    | { id, email } — кто создал                 |
| created_at       | string    | Дата создания                              |
| updated_at       | string    | Дата обновления                            |

**Сортировка (default):** по `created_at DESC`

**Ошибки:**

| Код  | Условие                    | detail.code      |
|------|----------------------------|------------------|
| 400  | Не выбран активный холдинг | NO_ACTIVE_HOLDING|
| 401  | Не авторизован             | UNAUTHORIZED     |

**Пример cURL:**

```bash
curl -X GET "http://localhost:8000/api/v1/documents?status=draft&search=регламент&page=1&page_size=20" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..."
```

---

### 5.3 Карточка документа

#### `GET /api/v1/documents/{id}`

Возвращает полную информацию о документе: метаданные, текущую версию, статистику.

**Заголовки:**

```
Authorization: Bearer <access_token>
```

**Path parameters:**

| Параметр | Тип | Описание    |
|----------|-----|-------------|
| id       | int | ID документа |

**Успешный ответ:** `200 OK`

```json
{
  "id": 1,
  "title": "Регламент документооборота",
  "description": "Описание документа",
  "status": "draft",
  "holding_id": 1,
  "created_by": {
    "id": 1,
    "email": "user@example.com"
  },
  "current_version": {
    "id": 1,
    "version_number": 1,
    "file_type": "docx",
    "file_size": 102400,
    "created_at": "2026-06-20T10:00:00Z"
  },
  "stats": {
    "sections_count": 12,
    "tables_count": 3,
    "terms_count": 25,
    "abbreviations_count": 5,
    "versions_count": 1
  },
  "created_at": "2026-06-20T10:00:00Z",
  "updated_at": "2026-06-20T11:00:00Z"
}
```

| Поле            | Тип       | Описание                                   |
|-----------------|-----------|--------------------------------------------|
| id              | int       | ID документа                               |
| title           | string    | Название                                   |
| description     | string|null| Описание                                   |
| status          | string    | Статус                                     |
| holding_id      | int       | ID холдинга                                |
| created_by      | object    | { id, email }                              |
| current_version | object|null| Информация о последней версии или null     |
| stats           | object    | Статистика (см. ниже)                      |
| created_at      | string    | Дата создания                              |
| updated_at      | string    | Дата обновления                            |

**Поля `stats`:**

| Поле                | Тип | Описание                           |
|---------------------|-----|------------------------------------|
| sections_count      | int | Количество разделов                |
| tables_count        | int | Количество таблиц                  |
| terms_count         | int | Количество терминов                |
| abbreviations_count | int | Количество сокращений              |
| versions_count      | int | Количество версий                  |

**Ошибки:**

| Код  | Условие                    | detail.code      |
|------|----------------------------|------------------|
| 401  | Не авторизован             | UNAUTHORIZED     |
| 404  | Документ не найден         | NOT_FOUND        |

**Пример cURL:**

```bash
curl -X GET http://localhost:8000/api/v1/documents/1 \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..."
```

---

### 5.4 Обновление документа

#### `PUT /api/v1/documents/{id}`

Обновляет метаданные документа: название, описание, статус. Все поля опциональны (частичное обновление).

**Заголовки:**

```
Authorization: Bearer <access_token>
Content-Type: application/json
```

**Path parameters:**

| Параметр | Тип | Описание    |
|----------|-----|-------------|
| id       | int | ID документа |

**Request Body:**

```json
{
  "title": "Новое название",
  "description": "Новое описание",
  "status": "review"
}
```

| Поле        | Тип    | Обязательно | Описание                                    |
|-------------|--------|-------------|---------------------------------------------|
| title       | string | нет         | Новое название (1-500 символов)             |
| description | string | нет         | Новое описание                              |
| status      | string | нет         | Новый статус: draft/review/approved/archived |

**Валидация:**
- `title` — если указан, то 1-500 символов, не пустой после трима
- `status` — если указан, то одно из: `draft`, `review`, `approved`, `archived`
- Нельзя сменить статус с `archived` на другой (документ архивируется безвозвратно на MVP). Для переоткрытия — удалить и загрузить заново.

**Успешный ответ:** `200 OK`

Тело ответа идентично `GET /api/v1/documents/{id}` (DocumentDetail).

**Ошибки:**

| Код  | Условие                                    | detail.code      |
|------|--------------------------------------------|------------------|
| 400  | Попытка снять archived статус              | BAD_REQUEST      |
| 401  | Не авторизован                             | UNAUTHORIZED     |
| 404  | Документ не найден                         | NOT_FOUND        |
| 422  | Невалидный статус или пустой title         | VALIDATION_ERROR |

**Пример cURL:**

```bash
curl -X PUT http://localhost:8000/api/v1/documents/1 \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..." \
  -d '{"title": "Новое название", "status": "review"}'
```

---

### 5.5 Удаление (Архивирование) документа

#### `DELETE /api/v1/documents/{id}`

Переводит документ в статус `archived`. Физического удаления данных не происходит — это soft-delete.
При повторном вызове на уже archived документе возвращается 204 без ошибок (идемпотентность).

**Заголовки:**

```
Authorization: Bearer <access_token>
```

**Path parameters:**

| Параметр | Тип | Описание    |
|----------|-----|-------------|
| id       | int | ID документа |

**Успешный ответ:** `204 No Content` (без тела)

**Ошибки:**

| Код  | Условие                    | detail.code      |
|------|----------------------------|------------------|
| 401  | Не авторизован             | UNAUTHORIZED     |
| 404  | Документ не найден         | NOT_FOUND        |

**Пример cURL:**

```bash
curl -X DELETE http://localhost:8000/api/v1/documents/1 \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..."
```

---

### 5.6 Список версий документа

#### `GET /api/v1/documents/{id}/versions`

Возвращает историю всех версий файла документа.

**Заголовки:**

```
Authorization: Bearer <access_token>
```

**Path parameters:**

| Параметр | Тип | Описание    |
|----------|-----|-------------|
| id       | int | ID документа |

**Успешный ответ:** `200 OK`

```json
{
  "items": [
    {
      "id": 1,
      "version_number": 1,
      "file_type": "docx",
      "file_size": 102400,
      "uploaded_by": {
        "id": 1,
        "email": "user@example.com"
      },
      "sections_count": 12,
      "tables_count": 3,
      "created_at": "2026-06-20T10:00:00Z"
    }
  ]
}
```

| Поле              | Тип       | Описание                              |
|------------------|-----------|---------------------------------------|
| items            | array     | Массив версий                         |

**Поля `items[]`:**

| Поле             | Тип       | Описание                              |
|------------------|-----------|---------------------------------------|
| id               | int       | ID версии                             |
| version_number   | int       | Номер версии                          |
| file_type        | string    | `"docx"` или `"pdf"`                  |
| file_size        | int       | Размер файла                          |
| uploaded_by      | object    | { id, email } — кто загрузил          |
| sections_count   | int       | Количество разделов в этой версии     |
| tables_count     | int       | Количество таблиц в этой версии       |
| created_at       | string    | Дата загрузки версии                  |

**Сортировка:** по `version_number DESC` (сначала новые)

**Ошибки:**

| Код  | Условие                    | detail.code      |
|------|----------------------------|------------------|
| 401  | Не авторизован             | UNAUTHORIZED     |
| 404  | Документ не найден         | NOT_FOUND        |

**Пример cURL:**

```bash
curl -X GET http://localhost:8000/api/v1/documents/1/versions \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..."
```

---

### 5.7 Скачивание файла версии

#### `GET /api/v1/documents/versions/{version_id}/download`

Скачивает оригинальный файл документа для указанной версии.

**Заголовки:**

```
Authorization: Bearer <access_token>
```

**Path parameters:**

| Параметр  | Тип | Описание      |
|-----------|-----|---------------|
| version_id| int | ID версии     |

**Успешный ответ:** `200 OK`

Ответ возвращается как бинарный поток (streaming response) с соответствующими заголовками:

```
Content-Type: application/vnd.openxmlformats-officedocument.wordprocessingml.document
Content-Disposition: attachment; filename="reglament_v1.docx"
Content-Length: 102400
```

или для PDF:

```
Content-Type: application/pdf
Content-Disposition: attachment; filename="reglament_v1.pdf"
Content-Length: 102400
```

**Ошибки:**

| Код  | Условие                    | detail.code      |
|------|----------------------------|------------------|
| 401  | Не авторизован             | UNAUTHORIZED     |
| 404  | Версия не найдена          | NOT_FOUND        |

**Пример cURL:**

```bash
curl -X GET http://localhost:8000/api/v1/documents/versions/1/download \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..." \
  -o reglament_v1.docx
```

---

### 5.8 Древовидная структура разделов

#### `GET /api/v1/documents/{id}/sections`

Возвращает иерархическое дерево разделов последней версии документа.

**Заголовки:**

```
Authorization: Bearer <access_token>
```

**Path parameters:**

| Параметр | Тип | Описание    |
|----------|-----|-------------|
| id       | int | ID документа |

**Успешный ответ:** `200 OK`

```json
{
  "document_id": 1,
  "version_id": 1,
  "sections": [
    {
      "id": 1,
      "title": "1. Общие положения",
      "level": 1,
      "order_num": 1,
      "content": "Текст раздела...",
      "children": [
        {
          "id": 2,
          "title": "1.1. Область применения",
          "level": 2,
          "order_num": 1,
          "content": "Текст подраздела...",
          "children": []
        },
        {
          "id": 3,
          "title": "1.2. Нормативные ссылки",
          "level": 2,
          "order_num": 2,
          "content": "Текст подраздела...",
          "children": [
            {
              "id": 4,
              "title": "1.2.1. Внутренние документы",
              "level": 3,
              "order_num": 1,
              "content": "Текст...",
              "children": []
            }
          ]
        }
      ]
    },
    {
      "id": 5,
      "title": "2. Термины и определения",
      "level": 1,
      "order_num": 2,
      "content": "Текст раздела...",
      "children": []
    }
  ]
}
```

| Поле         | Тип    | Описание                              |
|-------------|--------|---------------------------------------|
| document_id | int    | ID документа                          |
| version_id  | int    | ID последней версии                   |
| sections    | array  | Массив корневых разделов (level=1)    |

**Поля `sections[]` (SectionNode):**

| Поле     | Тип       | Описание                                   |
|----------|-----------|--------------------------------------------|
| id       | int       | ID раздела                                 |
| title    | string    | Заголовок раздела                          |
| level    | int       | Уровень вложенности (1-6)                  |
| order_num| int       | Порядковый номер в рамках родителя         |
| content  | string|null| Текст секции/параграфа                     |
| children | array     | Дочерние разделы (SectionNode[])           |

**Если документ не имеет версий (не загружен файл):** `200 OK` с пустым массивом sections.

**Ошибки:**

| Код  | Условие                    | detail.code      |
|------|----------------------------|------------------|
| 401  | Не авторизован             | UNAUTHORIZED     |
| 404  | Документ не найден         | NOT_FOUND        |

**Пример cURL:**

```bash
curl -X GET http://localhost:8000/api/v1/documents/1/sections \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..."
```

---

### 5.9 Термины документа

#### `GET /api/v1/documents/{id}/terms`

Возвращает список терминов и определений, извлечённых из документа.

**Заголовки:**

```
Authorization: Bearer <access_token>
```

**Path parameters:**

| Параметр | Тип | Описание    |
|----------|-----|-------------|
| id       | int | ID документа |

**Успешный ответ:** `200 OK`

```json
{
  "document_id": 1,
  "terms": [
    {
      "id": 1,
      "term": "Регламент",
      "definition": "Документ, устанавливающий правила..."
    },
    {
      "id": 2,
      "term": "Холдинг",
      "definition": "Совокупность юридических лиц..."
    }
  ]
}
```

**Ошибки:**

| Код  | Условие                    | detail.code      |
|------|----------------------------|------------------|
| 401  | Не авторизован             | UNAUTHORIZED     |
| 404  | Документ не найден         | NOT_FOUND        |

**Пример cURL:**

```bash
curl -X GET http://localhost:8000/api/v1/documents/1/terms \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..."
```

---

### 5.10 Сокращения документа

#### `GET /api/v1/documents/{id}/abbreviations`

Возвращает список сокращений и их расшифровок, извлечённых из документа.

**Заголовки:**

```
Authorization: Bearer <access_token>
```

**Path parameters:**

| Параметр | Тип | Описание    |
|----------|-----|-------------|
| id       | int | ID документа |

**Успешный ответ:** `200 OK`

```json
{
  "document_id": 1,
  "abbreviations": [
    {
      "id": 1,
      "abbreviation": "ООО",
      "full_form": "Общество с ограниченной ответственностью"
    },
    {
      "id": 2,
      "abbreviation": "АО",
      "full_form": "Акционерное общество"
    }
  ]
}
```

**Ошибки:**

| Код  | Условие                    | detail.code      |
|------|----------------------------|------------------|
| 401  | Не авторизован             | UNAUTHORIZED     |
| 404  | Документ не найден         | NOT_FOUND        |

**Пример cURL:**

```bash
curl -X GET http://localhost:8000/api/v1/documents/1/abbreviations \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..."
```

---

### 5.11 Таблицы документа

#### `GET /api/v1/documents/{id}/tables`

Возвращает список таблиц, извлечённых из документа, в HTML-формате.

**Заголовки:**

```
Authorization: Bearer <access_token>
```

**Path parameters:**

| Параметр | Тип | Описание    |
|----------|-----|-------------|
| id       | int | ID документа |

**Успешный ответ:** `200 OK`

```json
{
  "document_id": 1,
  "version_id": 1,
  "tables": [
    {
      "id": 1,
      "caption": "Таблица 1 — Параметры",
      "section_title": "2.1. Параметры",
      "order_num": 1,
      "rows_count": 5,
      "cols_count": 3,
      "html_content": "<table><thead><tr><th>Параметр</th><th>Значение</th><th>Примечание</th></tr></thead><tbody><tr><td>...</td><td>...</td><td>...</td></tr></tbody></table>"
    }
  ]
}
```

| Поле          | Тип       | Описание                                   |
|--------------|-----------|--------------------------------------------|
| document_id  | int       | ID документа                               |
| version_id   | int       | ID версии                                  |
| tables       | array     | Массив таблиц                              |

**Поля `tables[]`:**

| Поле          | Тип       | Описание                                   |
|--------------|-----------|--------------------------------------------|
| id           | int       | ID таблицы                                 |
| caption      | string|null| Подпись/название таблицы                   |
| section_title| string|null| Название раздела, где находится таблица    |
| order_num    | int       | Порядковый номер таблицы                   |
| rows_count   | int|null  | Количество строк                           |
| cols_count   | int|null  | Количество столбцов                        |
| html_content | string    | Таблица в HTML-формате                     |

**Ошибки:**

| Код  | Условие                    | detail.code      |
|------|----------------------------|------------------|
| 401  | Не авторизован             | UNAUTHORIZED     |
| 404  | Документ не найден         | NOT_FOUND        |

**Пример cURL:**

```bash
curl -X GET http://localhost:8000/api/v1/documents/1/tables \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..."
```

---

## 6. Storage Service — LocalFileStorage

### 6.1 Интерфейс

```python
# app/services/storage_service.py

from typing import BinaryIO
from fastapi import UploadFile


class LocalFileStorage:
    """
    Локальное файловое хранилище для документов.

    Base path: /storage/documents/{holding_id}/{document_id}/
    File naming: {version_number}_{timestamp}.{ext}
    """

    def __init__(self, base_path: str = "/storage/documents") -> None:
        self.base_path = base_path

    async def save(
        self,
        file: UploadFile,
        holding_id: int,
        document_id: int,
        version_number: int,
    ) -> str:
        """
        Сохраняет файл на диск.

        Args:
            file: Загруженный файл (FastAPI UploadFile)
            holding_id: ID холдинга
            document_id: ID документа
            version_number: Номер версии

        Returns:
            str: Относительный путь к файлу (для хранения в БД)

        Формат пути:
            {holding_id}/{document_id}/{version_number}_{timestamp}.{ext}
        Пример:
            "1/5/1_20260620_100000.docx"
        """
        ...

    def get_full_path(self, file_path: str) -> str:
        """
        Возвращает абсолютный путь к файлу на диске.

        Args:
            file_path: Относительный путь из БД

        Returns:
            str: Абсолютный путь

        Пример:
            "/storage/documents/1/5/1_20260620_100000.docx"
        """
        ...

    async def read(self, file_path: str) -> bytes:
        """
        Читает файл с диска.

        Args:
            file_path: Относительный путь из БД

        Returns:
            bytes: Содержимое файла

        Raises:
            FileNotFoundError: если файл не найден
        """
        ...

    async def delete(self, file_path: str) -> None:
        """
        Удаляет файл с диска.

        Args:
            file_path: Относительный путь из БД

        Raises:
            FileNotFoundError: если файл не найден
        """
        ...
```

### 6.2 Структура директорий

```
/storage/documents/
└── {holding_id}/
    └── {document_id}/
        ├── 1_20260620_100000.docx
        ├── 2_20260621_143000.pdf
        └── ...
```

### 6.3 Правила именования файлов

Формат: `{version_number}_{timestamp}.{ext}`

- `version_number` — Int, номер версии (1, 2, 3...)
- `timestamp` — `YYYYMMDD_HHMMSS` в UTC
- `ext` — оригинальное расширение файла (`docx` или `pdf`)

Пример: `1_20260620_100000.docx`

### 6.4 Безопасность

- Путь к файлу формируется только из доверенных данных (holding_id, document_id, version_number — все из БД)
- Не использовать имя файла от пользователя для формирования пути на диске (предотвращение path traversal)
- Проверять, что итоговый абсолютный путь находится внутри `base_path` (защита от обхода)

---

## 7. Parser Service — DocumentParser

### 7.1 Интерфейс

```python
# app/services/parser_service.py

from abc import ABC, abstractmethod
from app.schemas.parse import ParseResult


class DocumentParser(ABC):
    """Абстрактный парсер документов."""

    @abstractmethod
    async def parse(self, file_path: str, file_type: str) -> ParseResult:
        """
        Парсит документ и извлекает структуру.

        Args:
            file_path: Абсолютный путь к файлу на диске
            file_type: Тип файла ('docx' или 'pdf')

        Returns:
            ParseResult: Результат парсинга

        Raises:
            ParseError: если не удалось распарсить файл
        """
        ...


class ParseError(Exception):
    """Ошибка парсинга документа."""
    pass
```

### 7.2 DocxParser (python-docx)

#### Входные данные
- Файл .docx (Office Open XML)

#### Алгоритм извлечения разделов

1. Итерация по всем элементам документа в порядке следования
2. Определение заголовков: `paragraph.style.name` начинается с `'Heading'`
   - `Heading 1` → level=1
   - `Heading 2` → level=2
   - `Heading 3` → level=3
   - `Heading 4` → level=4
   - `Heading 5` → level=5
   - `Heading 6` → level=6
3. Обычные параграфы → content последнего открытого заголовка (конкатенация)
4. Построение иерархии: parent определяется как ближайший заголовок меньшего уровня

#### Алгоритм извлечения таблиц

1. Итерация по `document.tables`
2. Каждая таблица → HTML (через построчную конвертацию: `<table><tr><th>/<td>`)
3. Привязка к разделу: таблица принадлежит последнему открытому заголовку
4. Поиск подписи: параграф перед таблицей, содержащий слово "Таблица"

#### Алгоритм извлечения терминов

1. Поиск секций с заголовками: "Термины и определения", "Глоссарий", "Terms and Definitions"
2. Внутри найденных секций — парсинг параграфов по шаблонам:
   - `"термин — определение"` (тире)
   - `"термин – определение"` (короткое тире)
   - `"термин - определение"` (дефис)
   - `"термин: определение"` (двоеточие)
3. Для табличного формата: таблица с колонками "Термин" / "Определение"

#### Алгоритм извлечения сокращений

1. Поиск секций с заголовками: "Сокращения", "Обозначения и сокращения", "Abbreviations"
2. Парсинг по шаблонам:
   - `"СОКРАЩЕНИЕ — расшифровка"`
   - `"СОКРАЩЕНИЕ – расшифровка"`
3. Для табличного формата: таблица с колонками "Сокращение" / "Расшифровка"

### 7.3 PdfParser (PyMuPDF + pdfplumber)

#### Входные данные
- Файл .pdf

#### Алгоритм извлечения разделов

1. Извлечение текста постранично через PyMuPDF (`fitz`)
2. Определение заголовков по эвристикам:
   - Шрифт: жирный (`bold`) и/или размер больше baseline
   - Строка не заканчивается точкой (обычно заголовки без точки)
   - Нумерация в начале строки (1., 1.1., 1.1.1., Раздел 1, Глава 1, Статья 1)
3. Уровень заголовка определяется:
   - По размеру шрифта (чем больше — тем выше уровень)
   - По глубине нумерации (1. → level 1, 1.1. → level 2, 1.1.1. → level 3)
4. Обычный текст → content последнего заголовка

#### Алгоритм извлечения таблиц (pdfplumber)

1. Извлечение таблиц с каждой страницы через `page.extract_tables()`
2. Конвертация в HTML
3. Привязка к разделу по позиции на странице

#### Алгоритм извлечения терминов и сокращений

Аналогично DocxParser (поиск секций, шаблонов и таблиц).

### 7.4 TermExtractor (отдельный компонент)

```python
# app/services/term_extractor.py

import re
from app.schemas.parse import ParsedTerm, ParsedAbbreviation


class TermExtractor:
    """
    Извлекает термины и сокращения из текста.

    Паттерны:
    - Термин — Определение (U+2014 em dash / U+2013 en dash)
    - Термин - Определение (ASCII hyphen)
    - Термин: Определение (колонка)
    """

    TERM_PATTERNS = [
        re.compile(r"^(.+?)\s*[—–-]\s*(.+)", re.MULTILINE),
        re.compile(r"^(.+?)\s*:\s*(.+)", re.MULTILINE),
    ]

    ABBREVIATION_PATTERNS = [
        # АББРЕВИАТУРА (заглавные, 2-10 букв) — расшифровка
        re.compile(r"^([А-ЯA-Z]{2,10})\s*[—–-]\s*(.+)", re.MULTILINE),
        # Расшифровка (Аббревиатура)
        re.compile(r"^(.+?)\s*\(([А-ЯA-Z]{2,10})\)\s*$", re.MULTILINE),
    ]

    TERM_SECTION_TITLES = [
        "термины и определения",
        "глоссарий",
        "terms and definitions",
        "glossary",
    ]

    ABBREVIATION_SECTION_TITLES = [
        "сокращения",
        "обозначения и сокращения",
        "abbreviations",
        "notation",
    ]

    @classmethod
    def extract_terms_from_text(cls, text: str) -> list[ParsedTerm]:
        """Извлекает термины из текста по паттернам."""
        ...

    @classmethod
    def extract_abbreviations_from_text(cls, text: str) -> list[ParsedAbbreviation]:
        """Извлекает сокращения из текста по паттернам."""
        ...

    @classmethod
    def is_term_section(cls, section_title: str) -> bool:
        """Проверяет, является ли секция секцией терминов."""
        ...

    @classmethod
    def is_abbreviation_section(cls, section_title: str) -> bool:
        """Проверяет, является ли секция секцией сокращений."""
        ...
```

---

## 8. Бизнес-логика: Upload Flow

### 8.1 Полный флоу загрузки документа

```
POST /api/v1/documents/upload  [Auth required]
│
├─ 1. Аутентификация (JWT)
│   └─ Извлечение user.id из токена
│
├─ 2. Проверка активного холдинга
│   ├─ user.active_holding_id must be not null
│   └─ Если null → 400 NO_ACTIVE_HOLDING
│
├─ 3. Валидация файла
│   ├─ Расширение: .docx или .pdf (по Content-Type и расширению)
│   │   └─ Если иное → 400 INVALID_FILE_TYPE
│   ├─ Размер: ≤ 20MB (20 * 1024 * 1024 bytes)
│   │   └─ Если больше → 413 FILE_TOO_LARGE
│   └─ MIME-тип проверка:
│       ├─ .docx → application/vnd.openxmlformats-officedocument.wordprocessingml.document
│       └─ .pdf → application/pdf
│
├─ 4. Определение title
│   └─ Если title не указан → filename без расширения
│
├─ 5. Создание Document
│   ├─ holding_id = user.active_holding_id
│   ├─ title = из шага 4
│   ├─ description = из запроса (или None)
│   ├─ status = 'draft'
│   ├─ created_by = user.id
│   ├─ created_at = now
│   └─ updated_at = now
│
├─ 6. Определение version_number
│   └─ max(existing version_number for this document) + 1
│   └─ Если версий нет → 1
│
├─ 7. Сохранение файла через LocalFileStorage
│   ├─ file_path = storage.save(file, holding_id, document_id, version_number)
│   └─ В случае ошибки → откат создания документа (rollback)
│
├─ 8. Создание DocumentVersion
│   ├─ document_id = из шага 5
│   ├─ version_number = из шага 6
│   ├─ file_path = из шага 7
│   ├─ file_type = 'docx' или 'pdf'
│   ├─ file_size = размер файла
│   ├─ mime_type = MIME-тип файла
│   ├─ uploaded_by = user.id
│   └─ created_at = now
│
├─ 9. Парсинг документа
│   ├─ parser = DocxParser() если file_type='docx'
│   │         или PdfParser() если file_type='pdf'
│   ├─ result = parser.parse(full_path, file_type)
│   └─ В случае ошибки парсинга:
│       ├─ Документ и версия сохраняются (файл уже на диске)
│       ├─ Статус: draft
│       ├─ Логируем ошибку (logger.error)
│       └─ Возвращаем ответ с sections_count=0, tables_count=0 и т.д.
│       └─ НЕ возвращаем ошибку пользователю — файл сохранён
│
├─ 10. Сохранение результатов парсинга
│   ├─ sections: bulk insert document_sections (с иерархией parent-child)
│   ├─ tables: bulk insert document_tables
│   ├─ terms: bulk insert document_terms
│   └─ abbreviations: bulk insert document_abbreviations
│
└─ 11. Response 201 { id, title, status, file_type, file_size,
                      sections_count, tables_count,
                      terms_count, abbreviations_count, created_at }
```

### 8.2 Блок-схема принятия решений по парсингу

```
Файл загружен
    │
    ├── file_type == "docx" ──→ DocxParser.parse()
    │                               │
    │                               ├── python-docx: итерация по document.paragraphs
    │                               ├── Heading 1-6 → document_sections
    │                               ├── Обычный текст → content
    │                               ├── document.tables → document_tables
    │                               ├── TermExtractor → terms
    │                               └── TermExtractor → abbreviations
    │
    └── file_type == "pdf" ───→ PdfParser.parse()
                                    │
                                    ├── PyMuPDF: извлечение текста + шрифты
                                    ├── pdfplumber: извлечение таблиц
                                    ├── Эвристики: размер шрифта, жирность → sections
                                    ├── Конвертация таблиц → HTML
                                    ├── TermExtractor → terms
                                    └── TermExtractor → abbreviations
```

### 8.3 Обработка ошибок парсинга

Парсинг — **некритичная** операция с точки зрения сохранения файла. Если парсинг не удался:

1. Файл сохранён на диске ✓
2. Документ создан в БД ✓
3. Версия создана в БД ✓
4. Парсинг не удался — логируем, но **не прерываем** upload
5. В ответе: `sections_count=0`, `tables_count=0`, `terms_count=0`, `abbreviations_count=0`
6. Пользователь может повторно запустить парсинг через отдельный endpoint (в перспективе)

---

## 9. Дополнительные зависимости

### 9.1 Python-пакеты

Добавить в `requirements.txt` / `pyproject.toml`:

```toml
# Обработка документов
python-docx>=1.1.0,<2.0.0       # Word .docx
PyMuPDF>=1.24.0,<2.0.0          # PDF (fitz)
pdfplumber>=0.11.0,<1.0.0       # PDF таблицы

# FastAPI
python-multipart>=0.0.9,<1.0.0  # multipart uploads
```

### 9.2 Группировка зависимостей

| Группа          | Пакеты                                      | Назначение                    |
|-----------------|---------------------------------------------|-------------------------------|
| core            | fastapi, uvicorn, sqlalchemy, alembic       | Базовый фреймворк             |
| auth            | python-jose, pydantic, pydantic-settings    | JWT, валидация                |
| documents       | **python-docx, PyMuPDF, pdfplumber**        | Парсинг Word/PDF              |
| upload          | **python-multipart**                        | Загрузка файлов через API     |
| test            | pytest, httpx, pytest-asyncio               | Тестирование                  |

---

## 10. Единый формат ошибок — расширение

### 10.1 Структура (наследуется из Increment A)

Все ошибки возвращаются в едином формате:

```json
{
  "detail": {
    "code": "ERROR_CODE",
    "message": "Human-readable message",
    "field": "field_name"
  }
}
```

### 10.2 Новые коды ошибок (Increment B)

| Код                 | HTTP статус | Описание                                      | Когда возникает                                |
|---------------------|-------------|-----------------------------------------------|------------------------------------------------|
| `INVALID_FILE_TYPE` | 400         | Неподдерживаемый формат файла                 | Загружен не .docx и не .pdf                    |
| `FILE_TOO_LARGE`    | 413         | Файл превышает максимальный размер (20MB)     | Размер файла > 20MB                            |
| `NO_ACTIVE_HOLDING` | 400         | Пользователь не выбрал активный холдинг       | user.active_holding_id === null                |
| `PARSE_ERROR`       | 400         | Ошибка парсинга документа (файл повреждён)    | Невозможно прочитать/распарсить файл           |

### 10.3 Полная таблица кодов ошибок (Increment A + B)

| Код                 | HTTP статус | Инкремент | Описание                                      |
|---------------------|-------------|-----------|-----------------------------------------------|
| `VALIDATION_ERROR`  | 422         | A         | Невалидные данные в запросе                   |
| `NOT_FOUND`         | 404         | A         | Ресурс не найден                              |
| `CONFLICT`          | 409         | A         | Конфликт дубликата                            |
| `UNAUTHORIZED`      | 401 / 400   | A         | Неверный токен или код                        |
| `CODE_EXPIRED`      | 400         | A         | Код подтверждения истёк                       |
| `FORBIDDEN`         | 403         | A         | Недостаточно прав                             |
| `RATE_LIMITED`      | 429         | A         | Превышен лимит запросов                       |
| `INVALID_FILE_TYPE` | 400         | B         | Неподдерживаемый формат файла                 |
| `FILE_TOO_LARGE`    | 413         | B         | Файл превышает максимальный размер (20MB)     |
| `NO_ACTIVE_HOLDING` | 400         | B         | Пользователь не выбрал активный холдинг       |
| `PARSE_ERROR`       | 400         | B         | Ошибка парсинга документа                     |

### 10.4 Примеры новых ошибок

**INVALID_FILE_TYPE (400):**
```json
{
  "detail": {
    "code": "INVALID_FILE_TYPE",
    "message": "Unsupported file type. Only .docx and .pdf are allowed.",
    "field": "file"
  }
}
```

**FILE_TOO_LARGE (413):**
```json
{
  "detail": {
    "code": "FILE_TOO_LARGE",
    "message": "File size exceeds the maximum allowed size of 20MB.",
    "field": "file"
  }
}
```

**NO_ACTIVE_HOLDING (400):**
```json
{
  "detail": {
    "code": "NO_ACTIVE_HOLDING",
    "message": "Please select an active holding before uploading documents.",
    "field": null
  }
}
```

**PARSE_ERROR (400):**
```json
{
  "detail": {
    "code": "PARSE_ERROR",
    "message": "Failed to parse the document. The file may be corrupted.",
    "field": "file"
  }
}
```

---

## 11. Приложение A: Примеры ответов

### A.1 Полный сценарий: загрузка документа

**1. Загружаем Word-документ**

```bash
curl -X POST http://localhost:8000/api/v1/documents/upload \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..." \
  -F "file=@reglament.docx" \
  -F "title=Регламент документооборота" \
  -F "description=Основной регламент компании"
```

**Response 201:**
```json
{
  "id": 1,
  "title": "Регламент документооборота",
  "status": "draft",
  "file_type": "docx",
  "file_size": 102400,
  "sections_count": 12,
  "tables_count": 3,
  "terms_count": 25,
  "abbreviations_count": 5,
  "created_at": "2026-06-20T10:00:00Z"
}
```

**2. Получаем список документов**

```bash
curl -X GET "http://localhost:8000/api/v1/documents?status=draft" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..."
```

**Response 200:**
```json
{
  "items": [
    {
      "id": 1,
      "title": "Регламент документооборота",
      "status": "draft",
      "file_type": "docx",
      "file_size": 102400,
      "version_number": 1,
      "has_terms": true,
      "has_abbreviations": true,
      "created_by": {
        "id": 1,
        "email": "analyst@holding.ru"
      },
      "created_at": "2026-06-20T10:00:00Z",
      "updated_at": "2026-06-20T10:00:00Z"
    }
  ],
  "total": 1,
  "page": 1,
  "page_size": 20,
  "pages": 1
}
```

**3. Получаем карточку документа**

```bash
curl -X GET http://localhost:8000/api/v1/documents/1 \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..."
```

**Response 200:**
```json
{
  "id": 1,
  "title": "Регламент документооборота",
  "description": "Основной регламент компании",
  "status": "draft",
  "holding_id": 1,
  "created_by": {
    "id": 1,
    "email": "analyst@holding.ru"
  },
  "current_version": {
    "id": 1,
    "version_number": 1,
    "file_type": "docx",
    "file_size": 102400,
    "created_at": "2026-06-20T10:00:00Z"
  },
  "stats": {
    "sections_count": 12,
    "tables_count": 3,
    "terms_count": 25,
    "abbreviations_count": 5,
    "versions_count": 1
  },
  "created_at": "2026-06-20T10:00:00Z",
  "updated_at": "2026-06-20T10:00:00Z"
}
```

**4. Получаем дерево разделов**

```bash
curl -X GET http://localhost:8000/api/v1/documents/1/sections \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..."
```

**Response 200:**
```json
{
  "document_id": 1,
  "version_id": 1,
  "sections": [
    {
      "id": 1,
      "title": "1. Общие положения",
      "level": 1,
      "order_num": 1,
      "content": "Настоящий регламент устанавливает порядок...",
      "children": [
        {
          "id": 2,
          "title": "1.1. Область применения",
          "level": 2,
          "order_num": 1,
          "content": "Данный регламент распространяется на...",
          "children": []
        }
      ]
    }
  ]
}
```

**5. Получаем термины**

```bash
curl -X GET http://localhost:8000/api/v1/documents/1/terms \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..."
```

**Response 200:**
```json
{
  "document_id": 1,
  "terms": [
    {
      "id": 1,
      "term": "Регламент",
      "definition": "Документ, устанавливающий правила..."
    },
    {
      "id": 2,
      "term": "Холдинг",
      "definition": "Совокупность юридических лиц..."
    }
  ]
}
```

**6. Получаем сокращения**

```bash
curl -X GET http://localhost:8000/api/v1/documents/1/abbreviations \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..."
```

**Response 200:**
```json
{
  "document_id": 1,
  "abbreviations": [
    {
      "id": 1,
      "abbreviation": "ООО",
      "full_form": "Общество с ограниченной ответственностью"
    }
  ]
}
```

**7. Получаем таблицы**

```bash
curl -X GET http://localhost:8000/api/v1/documents/1/tables \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..."
```

**Response 200:**
```json
{
  "document_id": 1,
  "version_id": 1,
  "tables": [
    {
      "id": 1,
      "caption": "Таблица 1 — Параметры",
      "section_title": "2.1. Параметры",
      "order_num": 1,
      "rows_count": 5,
      "cols_count": 3,
      "html_content": "<table><thead><tr><th>Параметр</th><th>Значение</th><th>Примечание</th></tr></thead><tbody><tr><td>...</td><td>...</td><td>...</td></tr></tbody></table>"
    }
  ]
}
```

**8. Обновляем статус документа**

```bash
curl -X PUT http://localhost:8000/api/v1/documents/1 \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..." \
  -d '{"status": "review"}'
```

**Response 200:**
(тело ответа — полный DocumentDetail с обновлённым статусом)

**9. Скачиваем файл**

```bash
curl -X GET http://localhost:8000/api/v1/documents/versions/1/download \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..." \
  -o reglament_v1.docx
```

**Response 200:** бинарный файл с Content-Disposition

**10. Архивируем документ**

```bash
curl -X DELETE http://localhost:8000/api/v1/documents/1 \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..."
```

**Response 204:** No Content

### A.2 Ошибка: неверный формат файла

```bash
curl -X POST http://localhost:8000/api/v1/documents/upload \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..." \
  -F "file=@image.png"
```

**Response 400:**
```json
{
  "detail": {
    "code": "INVALID_FILE_TYPE",
    "message": "Unsupported file type. Only .docx and .pdf are allowed.",
    "field": "file"
  }
}
```

### A.3 Ошибка: файл слишком большой

```bash
curl -X POST http://localhost:8000/api/v1/documents/upload \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..." \
  -F "file=@huge_document.pdf"
```

**Response 413:**
```json
{
  "detail": {
    "code": "FILE_TOO_LARGE",
    "message": "File size exceeds the maximum allowed size of 20MB.",
    "field": "file"
  }
}
```

### A.4 Ошибка: не выбран активный холдинг

```bash
curl -X POST http://localhost:8000/api/v1/documents/upload \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..." \
  -F "file=@doc.docx"
```

**Response 400:**
```json
{
  "detail": {
    "code": "NO_ACTIVE_HOLDING",
    "message": "Please select an active holding before uploading documents.",
    "field": null
  }
}
```

### A.5 Ошибка: документ не найден

```bash
curl -X GET http://localhost:8000/api/v1/documents/999 \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..."
```

**Response 404:**
```json
{
  "detail": {
    "code": "NOT_FOUND",
    "message": "Document not found",
    "field": "id"
  }
}
```

---

## 12. Приложение B: Статус-коды

Сводная таблица endpoint'ов Increment B и возвращаемых статус-кодов.

| # | Endpoint                                        | Метод   | 200 | 201 | 204 | 400 | 401 | 404 | 413 | 422 |
|---|------------------------------------------------|---------|-----|-----|-----|-----|-----|-----|-----|-----|
| 1 | `/documents/upload`                             | POST    |     |  ✓  |     |  ✓  |  ✓  |     |  ✓  |  ✓  |
| 2 | `/documents`                                    | GET     |  ✓  |     |     |  ✓  |  ✓  |     |     |     |
| 3 | `/documents/{id}`                               | GET     |  ✓  |     |     |     |  ✓  |  ✓  |     |     |
| 4 | `/documents/{id}`                               | PUT     |  ✓  |     |     |  ✓  |  ✓  |  ✓  |     |  ✓  |
| 5 | `/documents/{id}`                               | DELETE  |     |     |  ✓  |     |  ✓  |  ✓  |     |     |
| 6 | `/documents/{id}/versions`                      | GET     |  ✓  |     |     |     |  ✓  |  ✓  |     |     |
| 7 | `/documents/versions/{version_id}/download`     | GET     |  ✓  |     |     |     |  ✓  |  ✓  |     |     |
| 8 | `/documents/{id}/sections`                      | GET     |  ✓  |     |     |     |  ✓  |  ✓  |     |     |
| 9 | `/documents/{id}/terms`                         | GET     |  ✓  |     |     |     |  ✓  |  ✓  |     |     |
|10 | `/documents/{id}/abbreviations`                 | GET     |  ✓  |     |     |     |  ✓  |  ✓  |     |     |
|11 | `/documents/{id}/tables`                        | GET     |  ✓  |     |     |     |  ✓  |  ✓  |     |     |

**Итого:** 11 endpoint'ов, 7 уникальных статус-кодов (+200, +201, +204, +400, +401, +404, +413, +422).

---

## 13. Приложение C: Рекомендации по реализации

### C.1 Структура проекта (дополнение к Increment A)

```
backend/
├── app/
│   ├── api/
│   │   └── v1/
│   │       ├── ...                 # из Increment A
│   │       └── documents.py        # NEW: document router (все endpoint'ы)
│   ├── models/
│   │   ├── ...                     # из Increment A
│   │   ├── document.py             # NEW: Document, DocumentVersion
│   │   ├── document_section.py     # NEW: DocumentSection
│   │   ├── document_table.py       # NEW: DocumentTable
│   │   ├── document_term.py        # NEW: DocumentTerm
│   │   └── document_abbreviation.py # NEW: DocumentAbbreviation
│   ├── schemas/
│   │   ├── ...                     # из Increment A
│   │   └── document.py             # NEW: Pydantic схемы
│   │   └── parse.py                # NEW: Dataclasses для парсинга
│   ├── services/
│   │   ├── ...                     # из Increment A
│   │   ├── document_service.py     # NEW: бизнес-логика документов
│   │   ├── storage_service.py      # NEW: LocalFileStorage
│   │   ├── parser_service.py       # NEW: DocumentParser (ABC)
│   │   ├── docx_parser.py          # NEW: DocxParser
│   │   ├── pdf_parser.py           # NEW: PdfParser
│   │   └── term_extractor.py       # NEW: TermExtractor
│   └── main.py                     # обновить lifespan + добавить роутер
├── storage/
│   └── documents/                  # NEW: директория для файлов
├── tests/
│   ├── ...                         # из Increment A
│   ├── test_documents.py           # NEW: API tests
│   ├── test_parsers.py             # NEW: unit tests парсеров
│   ├── test_storage.py             # NEW: unit tests storage
│   └── test_term_extractor.py      # NEW: unit tests term extractor
└── test_data/
    ├── sample.docx                 # NEW: тестовый Word-документ
    └── sample.pdf                  # NEW: тестовый PDF-документ
```

### C.2 Рекомендации по реализации для BE

#### Document Service (document_service.py)

```python
class DocumentService:
    """
    Бизнес-логика для работы с документами.
    Координирует: StorageService + DocumentParser + ORM.
    """

    def __init__(
        self,
        db: AsyncSession,
        storage: LocalFileStorage,
        parser: DocumentParser,
    ):
        ...

    async def upload_document(
        self,
        file: UploadFile,
        title: Optional[str],
        description: Optional[str],
        user: User,
    ) -> DocumentUploadResponse:
        """Полный флоу загрузки (шаги 1-11 из раздела 8.1)."""
        ...

    async def list_documents(
        self,
        holding_id: int,
        status: Optional[str],
        search: Optional[str],
        page: int,
        page_size: int,
    ) -> DocumentListResponse:
        """Список документов с фильтрацией и пагинацией."""
        ...

    async def get_document(self, document_id: int, holding_id: int) -> DocumentDetail:
        """Карточка документа."""
        ...

    async def update_document(
        self,
        document_id: int,
        holding_id: int,
        updates: DocumentUpdate,
    ) -> DocumentDetail:
        """Обновление метаданных документа."""
        ...

    async def archive_document(self, document_id: int, holding_id: int) -> None:
        """Архивирование документа (soft-delete)."""
        ...

    async def get_versions(
        self, document_id: int, holding_id: int
    ) -> VersionListResponse:
        """Список версий документа."""
        ...

    async def download_version(
        self, version_id: int, holding_id: int
    ) -> tuple[bytes, str, str]:
        """Скачивание файла версии. Возвращает (bytes, filename, mime_type)."""
        ...

    async def get_section_tree(
        self, document_id: int, holding_id: int
    ) -> SectionTreeResponse:
        """Дерево разделов."""
        ...

    async def get_terms(
        self, document_id: int, holding_id: int
    ) -> TermsResponse:
        """Термины документа."""
        ...

    async def get_abbreviations(
        self, document_id: int, holding_id: int
    ) -> AbbreviationsResponse:
        """Сокращения документа."""
        ...

    async def get_tables(
        self, document_id: int, holding_id: int
    ) -> TablesResponse:
        """Таблицы документа."""
        ...
```

#### Построение дерева разделов

Алгоритм построения иерархии `SectionNode` из плоского списка `DocumentSection`:

1. Загрузить все секции для `document_version_id`, отсортированные по `order_num`
2. Создать словарь `{section_id: SectionNode}`
3. Для каждой секции:
   - Если `parent_id` is None → добавить в корневой список
   - Если `parent_id` is not None → найти parent в словаре и добавить в `children`
4. Вернуть корневой список

#### Ограничение размера файла на уровне FastAPI

```python
from fastapi import FastAPI, Request
from starlette.exceptions import HTTPException as StarletteHTTPException

app = FastAPI(max_request_size=20 * 1024 * 1024)  # 20MB

# Или через middleware:
@app.middleware("http")
async def limit_content_length(request: Request, call_next):
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > 20 * 1024 * 1024:
        raise HTTPException(status_code=413, detail={
            "code": "FILE_TOO_LARGE",
            "message": "File size exceeds the maximum allowed size of 20MB.",
            "field": "file",
        })
    return await call_next(request)
```

### C.3 Рекомендации по тестированию

| Тип теста            | Инструмент    | Что тестировать |
|----------------------|--------------|-----------------|
| Unit (парсеры)       | pytest       | DocxParser с mock-документом, PdfParser с mock-страницей, TermExtractor с текстом |
| Unit (storage)       | pytest + tmpdir | LocalFileStorage: save, read, delete, get_full_path |
| Unit (term_extractor)| pytest       | Паттерны: термин—определение, сокращение—расшифровка, секции терминов |
| Integration (API)    | pytest + httpx | Все 11 endpoint'ов: upload, list, get, update, delete, versions, sections, terms, abbreviations, tables, download |
| Smoke (e2e)          | Playwright   | Загрузить документ → проверить реестр → открыть карточку → проверить дерево разделов |

**Покрытие API-тестов:**
- Каждый endpoint: минимум 1 success + 2 error сценария
- Upload: валидный .docx, валидный .pdf, невалидный формат, слишком большой файл, без холдинга, без авторизации
- CRUD: создание, обновление статуса, обновление названия, архивирование, повторное архивирование
- Версии: список версий, скачивание, скачивание несуществующей версии
- Парсинг: документ с 1 разделом, документ с иерархией (3 уровня), документ с таблицами, документ с терминами, документ без терминов

### C.4 Мок-документы для тестирования

Создать тестовые файлы в `backend/test_data/`:

- `sample.docx` — документ с 3 уровнями заголовков, 2 таблицами, секцией "Термины и определения"
- `sample.pdf` — аналогичная структура в PDF
- `empty.docx` — пустой документ (без заголовков)
- `corrupted.docx` — повреждённый файл (не читается)
- `sample_image_only.pdf` — PDF только с изображениями (без текста)

### C.5 Рекомендации по обработке ошибок парсинга

- Парсинг не должен блокировать загрузку документа
- Если парсинг не удался — документ сохраняется, в статистике нули
- Ошибка парсинга логируется с level ERROR и stack trace
- Пользователю возвращается успешный ответ 201 с нулевой статистикой
- В перспективе — endpoint для повторного парсинга

### C.6 Производительность

- При загрузке большого документа (близкого к 20MB) парсинг может занимать несколько секунд
- На MVP — синхронный парсинг внутри запроса (пользователь ждёт)
- В Stage 2 — фоновый парсинг через Celery / ARQ
- Bulk insert для sections/tables/terms/abbreviations через `db.execute_all()` для ускорения

---

*Конец документа.*
