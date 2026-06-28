# Phase 4: API Specification — Analysis Pipeline

> **Проект:** SRP (Service for Regulations and Policies)
> **Фаза:** 4 — Анализ при статусе «Утверждён» (Increment A1 — backend)
> **Дата:** 2026-06-28
> **Статус:** Черновик (готов к реализации)
> **Аудитория:** BE (Python/FastAPI), FE (React/TypeScript)

---

## Оглавление

1. [Контекст и цель](#1-контекст-и-цель)
2. [Базовый URL и формат](#2-базовый-url-и-формат)
3. [Pydantic схемы](#3-pydantic-схемы)
4. [REST API контракты](#4-rest-api-контракты)
   - 4.1 GET /api/v1/documents/{id}/analyses — история анализов
   - 4.2 GET /api/v1/analysis/{analysis_id}/status — статус pipeline
   - 4.3 POST /api/v1/documents/{id}/reanalyze — принудительный перезапуск
5. [Изменения в существующих endpoint'ах](#5-изменения-в-существующих-endpointах)
6. [Ролевая модель](#6-ролевая-модель)
7. [Формат ошибок](#7-формат-ошибок)
8. [Приложение A: Примеры ответов](#8-приложение-a-примеры-ответов)

---

## 1. Контекст и цель

### 1.1 Назначение

Данный документ описывает API-контракты для Phase 4 (Increment A1 — backend).
API обеспечивает:

- Просмотр истории запусков анализа документа
- Детальный мониторинг статуса pipeline (по шагам)
- Принудительный перезапуск анализа (сброс idempotency)

### 1.2 Базовые принципы

- **Все endpoint'ы** требуют аутентификации (JWT access token)
- **Изоляция по компании (холдингу):** пользователь видит только документы своей компании
- **Идемпотентность:** повторный approved без изменений контента не запускает анализ
- **Background pipeline:** анализ выполняется асинхронно, endpoint'ы возвращают управление немедленно

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

### 3.1 AnalysisStepStatus

```python
class AnalysisStepStatus(BaseModel):
    """Status of a single pipeline step."""
    status: str  # "waiting" | "running" | "done" | "error"
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error: Optional[str] = None
```

### 3.2 AnalysisStatusResponse

```python
class AnalysisStatusResponse(BaseModel):
    """Detailed status of an analysis pipeline run."""
    id: int
    document_id: int
    document_version_id: Optional[int] = None
    file_hash: Optional[str] = None
    status: str  # "running" | "complete" | "error"
    steps_status: dict[str, AnalysisStepStatus] = {}
    error_message: Optional[str] = None
    result_summary: Optional[dict] = None
    created_at: datetime
    completed_at: Optional[datetime] = None
```

### 3.3 AnalysisHistoryItem

```python
class AnalysisHistoryItem(BaseModel):
    """Summary of a single analysis run for history listing."""
    id: int
    document_id: int
    document_version_id: Optional[int] = None
    status: str  # "running" | "complete" | "error"
    error_message: Optional[str] = None
    result_summary: Optional[dict] = None
    created_at: datetime
    completed_at: Optional[datetime] = None
    
    model_config = {"from_attributes": True}
```

### 3.4 ReanalyzeResponse

```python
class ReanalyzeResponse(BaseModel):
    """Response after triggering a reanalysis."""
    analysis_id: int
    document_id: int
    status: str  # всегда "running"
    message: str  # "Reanalysis started"
```

### 3.5 ErrorResponse

(используется существующий единый формат ошибок)

---

## 4. REST API контракты

---

### 4.1 `GET /api/v1/documents/{document_id}/analyses`

Получить историю анализов документа.

**Path parameters:**

| Параметр | Тип | Описание |
|----------|-----|----------|
| document_id | int | ID документа |

**Заголовки:**

```
Authorization: Bearer <access_token>
```

**Успешный ответ:** `200 OK`

```json
[
  {
    "id": 1,
    "document_id": 5,
    "document_version_id": 3,
    "status": "complete",
    "error_message": null,
    "result_summary": {
      "sections_found": 15,
      "terms_found": 12,
      "abbreviations_found": 3,
      "chunks_indexed": 47
    },
    "created_at": "2026-06-28T10:00:00Z",
    "completed_at": "2026-06-28T10:00:31Z"
  },
  {
    "id": 2,
    "document_id": 5,
    "document_version_id": 4,
    "status": "running",
    "error_message": null,
    "result_summary": null,
    "created_at": "2026-06-28T11:00:00Z",
    "completed_at": null
  }
]
```

**Ответ — пустой список (нет анализов):**

```json
[]
```

**Ошибки:**

| Код | Условие | detail.code |
|-----|---------|-------------|
| 401 | Не авторизован | UNAUTHORIZED |
| 404 | Документ не найден или не принадлежит компании пользователя | NOT_FOUND |

**Пример cURL:**

```bash
curl -X GET http://localhost:8000/api/v1/documents/5/analyses \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..."
```

---

### 4.2 `GET /api/v1/analysis/{analysis_id}/status`

Получить детальный статус pipeline по шагам.

**Path parameters:**

| Параметр | Тип | Описание |
|----------|-----|----------|
| analysis_id | int | ID записи анализа |

**Заголовки:**

```
Authorization: Bearer <access_token>
```

**Успешный ответ:** `200 OK`

```json
{
  "id": 1,
  "document_id": 5,
  "document_version_id": 3,
  "file_hash": "a1b2c3d4e5f6...",
  "status": "running",
  "steps_status": {
    "extract_text": {
      "status": "done",
      "started_at": "2026-06-28T10:00:00Z",
      "completed_at": "2026-06-28T10:00:01Z",
      "error": null
    },
    "parse_structure": {
      "status": "done",
      "started_at": "2026-06-28T10:00:01Z",
      "completed_at": "2026-06-28T10:00:03Z",
      "error": null
    },
    "extract_terms": {
      "status": "error",
      "started_at": "2026-06-28T10:00:03Z",
      "completed_at": "2026-06-28T10:00:04Z",
      "error": "Term extraction failed: unexpected format"
    },
    "extract_abbr": {
      "status": "done",
      "started_at": "2026-06-28T10:00:04Z",
      "completed_at": "2026-06-28T10:00:05Z",
      "error": null
    },
    "extract_refs": {
      "status": "waiting",
      "started_at": null,
      "completed_at": null,
      "error": null
    },
    "pattern_analysis": {
      "status": "waiting",
      "started_at": null,
      "completed_at": null,
      "error": null
    },
    "embedding": {
      "status": "waiting",
      "started_at": null,
      "completed_at": null,
      "error": null
    },
    "mark_complete": {
      "status": "waiting",
      "started_at": null,
      "completed_at": null,
      "error": null
    }
  },
  "error_message": null,
  "result_summary": null,
  "created_at": "2026-06-28T10:00:00Z",
  "completed_at": null
}
```

**Ответ — анализ не найден:** `404 NOT_FOUND`

**Ошибки:**

| Код | Условие | detail.code |
|-----|---------|-------------|
| 401 | Не авторизован | UNAUTHORIZED |
| 403 | Пользователь не состоит в компании, к которой относится документ | FORBIDDEN |
| 404 | Анализ с указанным ID не найден | NOT_FOUND |

**Важно:** Проверка прав доступа: endpoint должен убедиться, что пользователь имеет доступ к компании, к которой относится документ (через `document_id` в анализе).

**Пример cURL:**

```bash
curl -X GET http://localhost:8000/api/v1/analysis/1/status \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..."
```

---

### 4.3 `POST /api/v1/documents/{document_id}/reanalyze`

Принудительный перезапуск анализа документа. Сбрасывает idempotency.

**Path parameters:**

| Параметр | Тип | Описание |
|----------|-----|----------|
| document_id | int | ID документа |

**Заголовки:**

```
Authorization: Bearer <access_token>
```

**Тело запроса:** не требуется (пустое тело)

**Успешный ответ:** `202 Accepted`

```json
{
  "analysis_id": 3,
  "document_id": 5,
  "status": "running",
  "message": "Reanalysis started"
}
```

**Логика работы:**

1. Проверить, что документ существует и принадлежит компании пользователя
2. Проверить права: требуется роль `editor` или `admin`
3. Проверить, что не запущен другой анализ (`Document.analysis_status != 'running'`)
   - Если уже running — вернуть `409 Conflict` (или `202` с ID текущего анализа — обсуждаемо)
4. Получить `latest_version` и вычислить `SHA256(full_text)`
5. Создать новую запись `DocumentAnalysis(status='running')`
6. Установить `Document.analysis_status = 'running'`
7. Запустить pipeline через `asyncio.create_task()`
8. Вернуть `202 Accepted` с `analysis_id`

**Ошибки:**

| Код | Условие | detail.code |
|-----|---------|-------------|
| 401 | Не авторизован | UNAUTHORIZED |
| 403 | Недостаточно прав (требуется editor+) | FORBIDDEN |
| 404 | Документ не найден или не принадлежит компании | NOT_FOUND |
| 409 | Анализ уже выполняется для этого документа | ALREADY_RUNNING |
| 400 | У документа нет версий с текстом | NO_CONTENT |

**Пример cURL:**

```bash
curl -X POST http://localhost:8000/api/v1/documents/5/reanalyze \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..." \
  -H "Content-Type: application/json" \
  -d "{}"
```

---

## 5. Изменения в существующих endpoint'ах

### 5.1 `POST /api/v1/documents/{id}/analyze` (существующий)

Поведение не меняется. Вызывает `PatternAnalysisService.analyze_document()` синхронно.
Остаётся как legacy endpoint для совместимости.

**Рекомендуется:** В будущем (Increment A2+) переключить этот endpoint на pipeline,
но в A1 оставить как есть.

### 5.2 `PUT /api/v1/documents/{id}` (существующий)

При смене статуса на `approved` теперь вызывает `_trigger_analysis_pipeline()`
вместо прямого вызова `PatternAnalysisService.analyze_document()` + `_trigger_rag_indexing()`.

Ответ не меняется — статус документа обновляется синхронно, анализ запускается в фоне.

### 5.3 `POST /api/v1/documents/{id}/status` (существующий)

Аналогично п. 5.2: триггер на approved теперь вызывает pipeline.

### 5.4 `GET /api/v1/documents/{id}` (существующий)

В ответ добавить поля `analysis_hash` и `analysis_status` в `DocumentResponse`.

**Изменение схемы `DocumentResponse`:**

```python
class DocumentResponse(BaseModel):
    # ... существующие поля ...
    was_analyzed: bool = False  # ОСТАЁТСЯ для обратной совместимости
    analysis_hash: Optional[str] = None    # НОВОЕ
    analysis_status: str = "none"          # НОВОЕ: none | running | complete | error
    # ...
```

**Пример дополненного ответа:**

```json
{
  "id": 5,
  "title": "Регламент по обработке ПДн",
  "status": "approved",
  "was_analyzed": true,
  "analysis_hash": "a1b2c3d4e5f6...",
  "analysis_status": "complete",
  ...
}
```

### 5.5 `POST /api/v1/documents/{id}/analyze` (существующий)

В будущем может быть переключён на pipeline, но в A1 остаётся как есть.

---

## 6. Ролевая модель

| Endpoint | Метод | Минимальная роль | Примечание |
|----------|-------|------------------|------------|
| `/documents/{id}/analyses` | GET | viewer | История анализов — информация только для чтения |
| `/analysis/{analysis_id}/status` | GET | viewer | Статус pipeline — информация только для чтения |
| `/documents/{id}/reanalyze` | POST | editor | Мутирующий endpoint: требуется редактор+ |

Проверка ролей использует существующие зависимости из `app.api.deps`:
- `require_active_company` — для viewer-level доступа (проверяет членство в компании)
- `require_editor` — для editor-level доступа
- `require_admin` — если потребуется admin-only (не требуется для A1)

---

## 7. Формат ошибок

Используется единый формат ошибок, принятый в проекте:

```json
{
  "detail": {
    "code": "ERROR_CODE",
    "message": "Human-readable description",
    "field": "field_name"
  }
}
```

### 7.1 Дополнительные коды ошибок для Phase 4

| Код | HTTP статус | Описание | Когда возникает |
|-----|-------------|----------|----------------|
| `ALREADY_RUNNING` | 409 | Анализ уже выполняется | Попытка запустить reanalyze, когда `Document.analysis_status == 'running'` |
| `NO_CONTENT` | 400 | У документа нет текста для анализа | `latest_version.full_text` пуст или отсутствует |

### 7.2 Примеры ошибок

**ALREADY_RUNNING (409):**
```json
{
  "detail": {
    "code": "ALREADY_RUNNING",
    "message": "Analysis is already running for this document. Wait for completion or check status at GET /api/v1/analysis/{id}/status",
    "field": null
  }
}
```

**NO_CONTENT (400):**
```json
{
  "detail": {
    "code": "NO_CONTENT",
    "message": "Document has no extracted text. Upload a new version with parseable content.",
    "field": "document_id"
  }
}
```

---

## 8. Приложение A: Примеры ответов

### A.1 Полный сценарий: Reanalyze

**1. Принудительный перезапуск анализа**
```bash
curl -X POST http://localhost:8000/api/v1/documents/5/reanalyze \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..." \
  -H "Content-Type: application/json" \
  -d "{}"
```

**Response 202:**
```json
{
  "analysis_id": 3,
  "document_id": 5,
  "status": "running",
  "message": "Reanalysis started"
}
```

**2. Проверка статуса pipeline через 5 секунд**
```bash
curl -X GET http://localhost:8000/api/v1/analysis/3/status \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..."
```

**Response 200 (pipeline running):**
```json
{
  "id": 3,
  "document_id": 5,
  "document_version_id": 4,
  "file_hash": "f6e5d4c3b2a1...",
  "status": "running",
  "steps_status": {
    "extract_text": {
      "status": "done",
      "started_at": "2026-06-28T11:00:00Z",
      "completed_at": "2026-06-28T11:00:01Z",
      "error": null
    },
    "parse_structure": {
      "status": "done",
      "started_at": "2026-06-28T11:00:01Z",
      "completed_at": "2026-06-28T11:00:03Z",
      "error": null
    },
    "extract_terms": {
      "status": "running",
      "started_at": "2026-06-28T11:00:03Z",
      "completed_at": null,
      "error": null
    },
    "extract_abbr": {
      "status": "waiting",
      "started_at": null,
      "completed_at": null,
      "error": null
    },
    "extract_refs": {
      "status": "waiting",
      "started_at": null,
      "completed_at": null,
      "error": null
    },
    "pattern_analysis": {
      "status": "waiting",
      "started_at": null,
      "completed_at": null,
      "error": null
    },
    "embedding": {
      "status": "waiting",
      "started_at": null,
      "completed_at": null,
      "error": null
    },
    "mark_complete": {
      "status": "waiting",
      "started_at": null,
      "completed_at": null,
      "error": null
    }
  },
  "error_message": null,
  "result_summary": null,
  "created_at": "2026-06-28T11:00:00Z",
  "completed_at": null
}
```

**3. Проверка статуса pipeline через 30 секунд (завершён)**
```bash
curl -X GET http://localhost:8000/api/v1/analysis/3/status \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..."
```

**Response 200 (pipeline complete):**
```json
{
  "id": 3,
  "document_id": 5,
  "document_version_id": 4,
  "file_hash": "f6e5d4c3b2a1...",
  "status": "complete",
  "steps_status": {
    "extract_text": { "status": "done", ... },
    "parse_structure": { "status": "done", ... },
    "extract_terms": { "status": "done", ... },
    "extract_abbr": { "status": "done", ... },
    "extract_refs": { "status": "done", ... },
    "pattern_analysis": { "status": "done", ... },
    "embedding": { "status": "done", ... },
    "mark_complete": { "status": "done", ... }
  },
  "error_message": null,
  "result_summary": {
    "sections_found": 15,
    "max_depth": 4,
    "terms_found": 12,
    "abbreviations_found": 3,
    "references_found": 5,
    "chunks_indexed": 47,
    "style_analyzed": true,
    "total_steps": 8,
    "failed_steps": 0,
    "completed_steps": 8
  },
  "created_at": "2026-06-28T11:00:00Z",
  "completed_at": "2026-06-28T11:00:31Z"
}
```

### A.2 История анализов

**4. Получение истории**
```bash
curl -X GET http://localhost:8000/api/v1/documents/5/analyses \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..."
```

**Response 200:**
```json
[
  {
    "id": 3,
    "document_id": 5,
    "document_version_id": 4,
    "status": "complete",
    "error_message": null,
    "result_summary": {
      "sections_found": 15,
      "terms_found": 12,
      "abbreviations_found": 3,
      "chunks_indexed": 47
    },
    "created_at": "2026-06-28T11:00:00Z",
    "completed_at": "2026-06-28T11:00:31Z"
  },
  {
    "id": 1,
    "document_id": 5,
    "document_version_id": 2,
    "status": "complete",
    "error_message": null,
    "result_summary": {
      "sections_found": 12,
      "terms_found": 8,
      "abbreviations_found": 2,
      "chunks_indexed": 35
    },
    "created_at": "2026-06-27T14:00:00Z",
    "completed_at": "2026-06-27T14:00:25Z"
  }
]
```

### A.3 Ошибка — анализ уже выполняется

```bash
curl -X POST http://localhost:8000/api/v1/documents/5/reanalyze \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..." \
  -H "Content-Type: application/json" \
  -d "{}"
```

**Response 409 (уже running):**
```json
{
  "detail": {
    "code": "ALREADY_RUNNING",
    "message": "Analysis is already running for this document. Check status at GET /api/v1/analysis/3/status",
    "field": null
  }
}
```

### A.4 Ошибка — нет текста для анализа

```bash
curl -X POST http://localhost:8000/api/v1/documents/6/reanalyze \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..." \
  -H "Content-Type: application/json" \
  -d "{}"
```

**Response 400:**
```json
{
  "detail": {
    "code": "NO_CONTENT",
    "message": "Document has no extracted text. Upload a new version with parseable content.",
    "field": "document_id"
  }
}
```
