# Phase 4: Analysis Pipeline Specification

> **Проект:** SRP (Service for Regulations and Policies)
> **Фаза:** 4 — Анализ при статусе «Утверждён» (Increment A1 — backend)
> **Дата:** 2026-06-28
> **Статус:** Черновик (готов к реализации)
> **Аудитория:** BE (Python/FastAPI)

---

## Оглавление

1. [Контекст и цель](#1-контекст-и-цель)
2. [Модель DocumentAnalysis](#2-модель-documentanalysis)
3. [Изменения модели Document](#3-изменения-модели-document)
4. [Pipeline — 8 шагов](#4-pipeline--8-шагов)
5. [Форматы steps_status и result_summary](#5-форматы-steps_status-и-result_summary)
6. [File hash idempotency](#6-file-hash-idempotency)
7. [Стратегия «Replace» при повторном анализе](#7-стратегия-replace-при-повторном-анализе)
8. [Интеграция с существующими сервисами](#8-интеграция-с-существующими-сервисами)
9. [Диаграмма последовательности](#9-диаграмма-последовательности)
10. [Обработка ошибок](#10-обработка-ошибок)
11. [Контракты сервисов](#11-контракты-сервисов)

---

## 1. Контекст и цель

### 1.1 Текущее состояние

На данный момент в кодовой базе существуют:

- **`PatternAnalysisService`** (`app/services/pattern_analysis_service.py`) — синхронный анализ структуры, стиля, терминов и сокращений документа; обновляет профиль компании (поля `document_structure`, `style_settings`). Вызывается **синхронно** в `document_update_service.py` при смене статуса на `approved`.
- **`RagService`** (`app/services/rag_service.py`) — индексация документа в ChromaDB: разбивка на чанки, получение embedding'ов через Ollama, сохранение в векторную БД. Вызывается отдельно после `PatternAnalysisService`.
- **Флаг `was_analyzed`** (bool) на модели `Document` — простая защита от повторного анализа.
- **Команда `POST /api/v1/documents/{id}/analyze`** — ручной запуск анализа.

### 1.2 Проблемы текущей реализации

1. **Анализ синхронный** — при большом документе HTTP-запрос на смену статуса может длиться минуты.
2. **RAG и PatternAnalysis запускаются раздельно** — нет единого pipeline с отслеживанием прогресса.
3. **`was_analyzed`** — бинарный флаг, не хранит информацию о том, *какая версия* была проанализирована.
4. **Нет idempotency по контенту** — если контент не изменился, но документ повторно переведён в approved, анализ всё равно выполняется (если только `was_analyzed=True` не сброшен).
5. **Нет истории анализов** — нельзя посмотреть, когда и с каким результатом выполнялся анализ.

### 1.3 Цель Phase 4

Создать единый асинхронный pipeline анализа с:
- Детальным отслеживанием статуса каждого шага
- Идемпотентностью по SHA256 контента
- Историей всех запусков
- Background-выполнением (не блокирует HTTP-ответ)
- Устойчивостью к ошибкам отдельных шагов

---

## 2. Модель DocumentAnalysis

### 2.1 SQLAlchemy модель

```python
class DocumentAnalysis(Base):
    __tablename__ = "document_analyses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    document_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("documents.id", ondelete="CASCADE"), index=True, nullable=False
    )
    document_version_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("document_versions.id", ondelete="SET NULL"), nullable=True
    )
    file_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)  # SHA256 full_text
    status: Mapped[str] = mapped_column(String(20), default="running", nullable=False)  # running | complete | error
    steps_status: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)  # {"step_name": "waiting"|"running"|"done"|"error"}
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)   # Общая ошибка pipeline
    result_summary: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True) # Итоговая сводка
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utcnow, nullable=False
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
```

### 2.2 Поля

| Поле | Тип | Описание |
|------|-----|----------|
| `id` | Integer, PK | Уникальный ID записи анализа |
| `document_id` | Integer, FK → documents.id | Документ, который анализируется |
| `document_version_id` | Integer, FK → document_versions.id, nullable | Версия документа на момент анализа (null, если версия была удалена) |
| `file_hash` | String(64), nullable | SHA256 хеш `full_text` latest_version на момент запуска анализа |
| `status` | String(20) | Статус pipeline: `running` / `complete` / `error` |
| `steps_status` | JSON, nullable | Словарь со статусами каждого шага (см. раздел 5) |
| `error_message` | Text, nullable | Сообщение об ошибке, если pipeline завершился с `error` |
| `result_summary` | JSON, nullable | Итоговая сводка результатов (см. раздел 5) |
| `created_at` | DateTime | Время создания записи (начало анализа) |
| `completed_at` | DateTime, nullable | Время завершения анализа (успех или ошибка) |

### 2.3 Индексы

- `ix_document_analyses_document_id` — по `document_id` для быстрого поиска истории
- `ix_document_analyses_file_hash` — по `file_hash` для проверки idempotency

### 2.4 Связи (relationships)

```python
document: Mapped["Document"] = relationship("Document", back_populates="analyses")
version: Mapped[Optional["DocumentVersion"]] = relationship("DocumentVersion", lazy="selectin")
```

В модели `Document` добавить:

```python
analyses: Mapped[list["DocumentAnalysis"]] = relationship(
    "DocumentAnalysis", back_populates="document", cascade="all, delete-orphan",
    lazy="selectin",
)
```

---

## 3. Изменения модели Document

### 3.1 Новые поля

```python
# В класс Document добавить:
analysis_hash: Mapped[Optional[str]] = mapped_column(
    String(64), nullable=True, default=None
)
analysis_status: Mapped[str] = mapped_column(
    String(10), default="none", nullable=False
)
```

### 3.2 Описание полей

| Поле | Тип | Default | Описание |
|------|-----|---------|----------|
| `analysis_hash` | String(64), nullable | `None` | SHA256 `full_text` последнего успешного анализа. Используется для быстрой проверки idempotency без запроса к DocumentAnalysis. |
| `analysis_status` | String(10) | `"none"` | Статус анализа документа: `none` (не анализировался), `running` (выполняется), `complete` (успешно), `error` (ошибка). Позволяет блокировать повторный запуск при already running. |

### 3.3 Статусная модель анализа документа

```
none → running → complete
               → error

running → complete  (pipeline завершился успешно)
running → error     (pipeline завершился с ошибкой)
error → running     (при reanalyze или повторном approved после исправления)
complete → running  (при reanalyze)
```

**Важно:** Переход `error → running` или `complete → running` возможен только через:
1. Принудительный `POST /api/v1/documents/{id}/reanalyze`
2. Автоматически, если при approved обнаружен новый file_hash (контент изменился)

---

## 4. Pipeline — 8 шагов

### 4.1 Общее описание

Pipeline состоит из 8 последовательных шагов. Каждый шаг:

- Имеет уникальное имя-ключ (slug): `extract_text`, `parse_structure`, и т.д.
- Имеет статус: `waiting` → `running` → `done` / `error`
- Обновляет `DocumentAnalysis.steps_status` в БД после каждого шага
- При ошибке: логирует ошибку, устанавливает статус шага `error`, НО pipeline продолжается к следующему шагу
- После завершения всех шагов: pipeline устанавливает финальный статус `complete` (если хотя бы один шаг выполнен успешно) или `error` (если все шаги упали)

### 4.2 Список шагов

| # | Шаг | Ключ | Описание | Использует | Длительность (оценка) |
|---|------|------|----------|------------|-----------------------|
| 1 | Извлечение текста | `extract_text` | Получить `full_text` из `latest_version`. Если текст пуст — шаг считается ошибкой. | SQLAlchemy | < 1 сек |
| 2 | Парсинг структуры | `parse_structure` | Парсинг заголовков/разделов документа (использует существующий parser_service). Разделы сохраняются в `document_sections`. | `parser_service` | 1-5 сек |
| 3 | Извлечение терминов | `extract_terms` | Извлечение терминов и определений. Сохранение в `document_terms`. | `parser_service._extract_terms_from_text` | 1-3 сек |
| 4 | Извлечение сокращений | `extract_abbr` | Извлечение сокращений и расшифровок. Сохранение в `document_abbreviations`. | `parser_service._extract_abbreviations_from_text` | 1-3 сек |
| 5 | Извлечение ссылок | `extract_refs` | Извлечение ссылок на внутренние/внешние документы. (NEW: добавить модель `DocumentReference`, если необходимо; на MVP — опционально, извлекается, но не сохраняется, если модели нет) | text pattern matching | 1-2 сек |
| 6 | Pattern analysis | `pattern_analysis` | Анализ структуры и стиля документа. Обновление профиля компании (поля `document_structure`, `style_settings`). | `PatternAnalysisService` (адаптированный) | 2-5 сек |
| 7 | Embedding | `embedding` | Разбивка текста на чанки, получение embedding'ов через Ollama, сохранение в ChromaDB. | `RagService.index_document` | 10-120+ сек (зависит от объёма) |
| 8 | Фиксация результата | `mark_complete` | Обновление `DocumentAnalysis.status=complete`, `Document.analysis_hash=file_hash`, `Document.analysis_status=complete`. Сохранение `result_summary`. | SQLAlchemy | < 1 сек |

### 4.3 Детальное описание шагов

#### Шаг 1: extract_text

```
Вход:  document_id (int)
Выход: full_text (str | None), version_id (int | None)

Логика:
1. Загрузить Document с versions
2. Найти latest_version (max by version_number)
3. Если нет версий → шаг error, message: "No versions found for document"
4. Если full_text пустой или None → шаг error, message: "Latest version has no full_text"
5. Сохранить document_version_id в DocumentAnalysis.document_version_id
6. Вернуть full_text, version_id
```

#### Шаг 2: parse_structure

```
Вход:  full_text (str), document_id (int), version_id (int)
Выход: sections_count (int)

Логика:
1. Использовать parser_service для разбора структуры документа
2. Удалить существующие секции для этой версии (если были)
3. Сохранить новые секции в document_sections
4. Вернуть количество секций

Примечание: parser_service уже умеет парсить структуру
из полного текста (см. docx_parser, pdf_parser).
Для повторного анализа: старые секции удаляются.
```

#### Шаг 3: extract_terms

```
Вход:  full_text (str), document_id (int)
Выход: terms_count (int)

Логика:
1. Использовать parser_service._extract_terms_from_text(full_text)
2. Если это повторный анализ: DELETE FROM document_terms WHERE document_id = ?
3. Сохранить новые термины в document_terms
4. Вернуть количество терминов
```

#### Шаг 4: extract_abbr

```
Вход:  full_text (str), document_id (int)
Выход: abbr_count (int)

Логика:
1. Использовать parser_service._extract_abbreviations_from_text(full_text)
2. Если это повторный анализ: DELETE FROM document_abbreviations WHERE document_id = ?
3. Сохранить новые сокращения
4. Вернуть количество сокращений
```

#### Шаг 5: extract_refs

```
Вход:  full_text (str)
Выход: refs_count (int)

Логика:
1. Поиск ссылок: "Регламент №...", "ФЗ №...", "Приказ №...", URL_patterns
2. На MVP: извлечение и подсчёт, без сохранения в отдельную модель
   (модель DocumentReference будет добавлена в одной из будущих фаз)
3. Вернуть количество найденных ссылок

Обсуждение: Если модель DocumentReference уже существует — сохранять.
В текущей кодовой базе такой модели нет, поэтому на этапе A1
только подсчёт и логирование.
```

#### Шаг 6: pattern_analysis

```
Вход:  document_id (int), db (AsyncSession)
Выход: структура результатов

Логика:
1. Использовать существующий PatternAnalysisService.analyze_document()
   с адаптацией: не проверять doc.was_analyzed (мы уже знаем, что это анализ)
2. Извлечение структуры, стиля, слияние с профилем компании
3. Вернуть сводку

Примечание: Существующий PatternAnalysisService.analyze_document()
проверяет doc.was_analyzed и прерывается, если True.
Для pipeline нужно либо вызвать отдельные методы (_extract_structure,
_extract_style, _collect_terms, _collect_abbr, _update_company_patterns),
либо передать параметр force=True.
Рекомендуется: выделить методы _update_company_patterns_from_document.
```

#### Шаг 7: embedding

```
Вход:  document_id (int), company_id (int), title (str), full_text (str)
Выход: chunks_indexed (int)

Логика:
1. Если это повторный анализ: rag_service.delete_document_chunks(document_id, company_id)
2. RagService.index_document(document_id, company_id, title, full_text)
3. Обновить ChromaDB метаданные: document_id, title, chunk_index
4. Вернуть количество проиндексированных чанков
```

#### Шаг 8: mark_complete

```
Вход:  analysis_id (int), file_hash (str), result_summary (dict),
       steps_status (dict), db (AsyncSession)
Выход: нет (фиксация в БД)

Логика:
1. Загрузить DocumentAnalysis по analysis_id
2. Установить status='complete', completed_at=utcnow()
3. Установить steps_status=steps_status, result_summary=result_summary
4. Обновить Document:
   - analysis_hash = file_hash
   - analysis_status = 'complete'
5. Если все шаги в steps_status имеют статус 'error':
   установить status='error', error_message='All pipeline steps failed'

Важно: Этот шаг выполняется всегда, даже если предыдущие шаги
были с ошибками. Единственное исключение — критическая ошибка
БД, которая обрабатывается на уровне pipeline.run().
```

---

## 5. Форматы steps_status и result_summary

### 5.1 steps_status

Формат: `dict[str, dict]`, где ключ — имя шага, значение — объект со статусом.

```json
{
  "extract_text": {
    "status": "done",
    "started_at": "2026-06-28T10:00:00Z",
    "completed_at": "2026-06-28T10:00:00Z",
    "error": null
  },
  "parse_structure": {
    "status": "done",
    "started_at": "2026-06-28T10:00:01Z",
    "completed_at": "2026-06-28T10:00:03Z",
    "error": null
  },
  "extract_terms": {
    "status": "done",
    "started_at": "2026-06-28T10:00:03Z",
    "completed_at": "2026-06-28T10:00:04Z",
    "error": null
  },
  "extract_abbr": {
    "status": "done",
    "started_at": "2026-06-28T10:00:04Z",
    "completed_at": "2026-06-28T10:00:05Z",
    "error": null
  },
  "extract_refs": {
    "status": "done",
    "started_at": "2026-06-28T10:00:05Z",
    "completed_at": "2026-06-28T10:00:05Z",
    "error": null
  },
  "pattern_analysis": {
    "status": "done",
    "started_at": "2026-06-28T10:00:05Z",
    "completed_at": "2026-06-28T10:00:06Z",
    "error": null
  },
  "embedding": {
    "status": "done",
    "started_at": "2026-06-28T10:00:06Z",
    "completed_at": "2026-06-28T10:00:30Z",
    "error": null
  },
  "mark_complete": {
    "status": "done",
    "started_at": "2026-06-28T10:00:30Z",
    "completed_at": "2026-06-28T10:00:31Z",
    "error": null
  }
}
```

**Допустимые статусы шага:** `waiting`, `running`, `done`, `error`.

### 5.2 result_summary

Формат: `dict` с итоговыми показателями анализа.

```json
{
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
}
```

**Поля:**

| Поле | Тип | Описание |
|------|-----|----------|
| `sections_found` | int | Количество распарсенных разделов |
| `max_depth` | int | Максимальная глубина вложенности разделов |
| `terms_found` | int | Количество извлечённых терминов |
| `abbreviations_found` | int | Количество извлечённых сокращений |
| `references_found` | int | Количество найденных ссылок |
| `chunks_indexed` | int | Количество чанков, проиндексированных в ChromaDB |
| `style_analyzed` | bool | Флаг успешного анализа стиля |
| `total_steps` | int | Всегда 8 |
| `failed_steps` | int | Количество шагов, завершившихся с ошибкой |
| `completed_steps` | int | Количество успешно выполненных шагов |

### 5.3 Статусы записи DocumentAnalysis

| Значение | Описание |
|----------|---------|
| `running` | Pipeline выполняется (один из шагов в статусе `running`) |
| `complete` | Все шаги выполнены (минимум один успешно) |
| `error` | Pipeline завершился: все шаги вернули ошибку, или критическая ошибка на уровне БД |

---

## 6. File hash idempotency

### 6.1 Алгоритм

При смене статуса документа на `approved`:

```
1. Загрузить Document по document_id + company_id
2. Проверить, что статус меняется на approved
   (если уже approved — ничего не делать, статус не изменился)
3. Получить latest_version
4. Вычислить current_hash = SHA256(latest_version.full_text)
5. Если Document.analysis_hash == current_hash
   И Document.analysis_status == 'complete':
   → SKIP (true idempotency)
6. Если Document.analysis_status == 'running':
   → SKIP (анализ уже выполняется)
7. ИНАЧЕ:
   a. Создать DocumentAnalysis(status='running', file_hash=current_hash,
        document_version_id=latest_version.id)
   b. Установить Document.analysis_status = 'running'
   c. Запустить pipeline через asyncio.create_task()
```

### 6.2 Дополнительная проверка (ChromaDB)

Даже если `analysis_hash` совпадает, выполняется дополнительная проверка наличия чанков 
в ChromaDB через `rag_service.get_document_chunks_count(document_id, company_id)`.

**Зачем:** При пересборке проекта или ручной очистке ChromaDB чанки могут быть удалены, 
но `analysis_hash` остаётся. Без этой проверки RAG (Фаза 5) не найдёт релевантные документы.

**Логика в `trigger_analysis()`:**

```
1. compute current_hash = SHA256(full_text)
2. if doc.analysis_hash == current_hash AND doc.analysis_status == 'complete':
   2a. chunks = rag_service.get_document_chunks_count(document_id, company_id)
   2b. if chunks > 0:
       → SKIP (true idempotency — и контент, и ChromaDB в порядке)
   2c. else:
       → RUN analysis (ChromaDB пуста, нужно переиндексировать)
3. else:
   → RUN analysis
```

**Метод `get_document_chunks_count()`:**
- Подсчитывает количество чанков с префиксом `doc_{document_id}_` в коллекции компании
- Возвращает 0 при ошибке (логирует warning) — в этом случае анализ будет перезапущен
- Не требует эмбеддинга или обращения к Ollama — только GET запрос к ChromaDB

**Важно:** Проверка ChromaDB выполняется ТОЛЬКО в автоматическом триггере (approved).
При принудительном reanalyze (`force=True`) проверка не выполняется — старые чанки удаляются 
и создаются заново.

### 6.3 Использование analysis_hash

Поле `Document.analysis_hash` служит быстрым кэшем для проверки idempotency:

- **Запись:** устанавливается в шаге `mark_complete` (`analysis_hash = file_hash`)
- **Чтение:** при триггере на approved сравниваем `SHA256(full_text) === Document.analysis_hash`
- **Сброс:** при reanalyze `analysis_hash` НЕ сбрасывается сразу; старый хеш остаётся, пока новый pipeline не завершится (шаг `mark_complete` перезапишет)

---

## 7. Стратегия «Replace» при повторном анализе

### 7.1 Когда применяется

1. **Принудительный reanalyze** (`POST /api/v1/documents/{id}/reanalyze`)
2. **Автоматический повторный анализ** — если контент изменился (новый file_hash) и документ снова переведён в approved

### 7.2 Что удаляется

| Данные | Действие | Сервис/Метод |
|--------|----------|-------------|
| Чанки в ChromaDB | Удалить все `doc_{document_id}_*` | `rag_service.delete_document_chunks(document_id, company_id)` |
| document_terms | `DELETE FROM document_terms WHERE document_id = ?` | SQLAlchemy delete |
| document_abbreviations | `DELETE FROM document_abbreviations WHERE document_id = ?` | SQLAlchemy delete |
| document_sections | `DELETE FROM document_sections WHERE document_version_id = ?` | SQLAlchemy delete (только для текущей версии) |
| Стиль компании | Дополнить (не удалять) — `PatternAnalysisService` уже добавляет без дублей | `_update_company_patterns` |

### 7.3 Что НЕ удаляется

- **Старые записи DocumentAnalysis** — остаются в истории
- **Профиль компании** (стиль, структура) — только дополняется
- **Файл документа** — не затрагивается

### 7.4 Важно

Анализ не удаляет существующие данные **до** успешного начала pipeline.
Порядок: создать новую DocumentAnalysis → запустить pipeline → 
в каждом шаге сначала удалить старые данные, потом создать новые.
Это гарантирует, что при ошибке pipeline старые данные останутся 
(если шаг не дошёл до удаления) или частично обновятся 
(если шаг удалил, но не успел создать — допустимо на MVP, 
поскольку reanalyze перезапускает всё заново).

---

## 8. Интеграция с существующими сервисами

### 8.1 AnalysisPipelineService

Новый сервис, который:

- Координирует выполнение 8 шагов
- Управляет обновлением `DocumentAnalysis.steps_status`
- Запускается через `asyncio.create_task(pipeline.run(...))`
- Создаёт собственную DB-сессию (чтобы не зависеть от сессии HTTP-запроса)

```python
class AnalysisPipelineService:
    async def run(
        self,
        analysis_id: int,
        document_id: int,
        company_id: int,
        db: AsyncSession,
    ) -> None:
        """Run the full analysis pipeline in background."""
        ...
    
    async def _run_step(
        self,
        step_name: str,
        analysis: DocumentAnalysis,
        func: Callable,
        db: AsyncSession,
    ) -> Any:
        """Execute a single pipeline step with status tracking."""
        ...
```

### 8.2 Изменения в document_update_service.py

1. Удалить прямой вызов `pattern_analysis_service.analyze_document()`
2. Удалить прямой вызов `_trigger_rag_indexing()`
3. Заменить на вызов `AnalysisPipelineService` с проверкой idempotency

```python
# В методе change_status (и update_document), при переходе в approved:
if new_status == DocumentStatus.APPROVED:
    await self._trigger_analysis_pipeline(document_id, company_id, db)
```

### 8.3 Изменения в PatternAnalysisService

- Метод `analyze_document()` будет по-прежнему доступен для обратной совместимости
- Для pipeline используем внутренние методы (`_extract_structure`, `_extract_style`, `_collect_terms`, `_collect_abbreviations`, `_update_company_patterns`)
- Убрать проверку `doc.was_analyzed` из внутренних методов (оставить в публичном API для ручного вызова)

### 8.4 Изменения в RagService

- Метод `index_document()` используется без изменений
- Метод `delete_document_chunks()` используется для очистки перед переиндексацией

---

## 9. Диаграмма последовательности

### 9.1 Автоматический анализ при approved

```
User                 API                 DocumentUpdateSvc       AnalysisPipelineSvc    ChromaDB
  │                    │                        │                       │                  │
  │ PUT /documents/1   │                        │                       │                  │
  │ (status=approved)  │                        │                       │                  │
  │───────────────────►│                        │                       │                  │
  │                    │ update_document()       │                       │                  │
  │                    │───────────────────────►│                       │                  │
  │                    │                        │                       │                  │
  │                    │  ┌─── check idempotency ────────────────────── │                  │
  │                    │  │ 1. Load document + latest_version           │                  │
  │                    │  │ 2. SHA256(full_text)                        │                  │
  │                    │  │ 3. Compare with doc.analysis_hash           │                  │
  │                    │  │ 4. If match → skip (return)                 │                  │
  │                    │  └─────────────────────────────────────────────│                  │
  │                    │                        │                       │                  │
  │                    │  Create DocumentAnalysis(status=running)       │                  │
  │                    │  Set doc.analysis_status=running               │                  │
  │                    │───────────────────────────────────────────────►│                  │
  │                    │                        │                       │                  │
  │                    │  asyncio.create_task(pipeline.run(...))        │                  │
  │                    │───────────────────────────────────────────────►│                  │
  │                    │                        │                       │                  │
  │ 200 OK (статус     │                        │     Pipeline starts   │                  │
  │ обновлён, анализ   │                        │     (background)      │                  │
  │ запущен в фоне)    │                        │                       │                  │
  │◄───────────────────│                        │                       │                  │
  │                    │                        │                       │                  │
  │                    │     ─── Pipeline (background) ───              │                  │
  │                    │                        │                       │                  │
  │                    │                        │ Step 1: extract_text  │                  │
  │                    │                        │◄──────────────────────│                  │
  │                    │                        │──── full_text ───────►│                  │
  │                    │                        │                       │                  │
  │                    │                        │ Step 2: parse_structure│                 │
  │                    │                        │──── sections ────────►│                  │
  │                    │                        │                       │                  │
  │                    │                        │ Step 3-5: extract     │                  │
  │                    │                        │ terms/abbr/refs       │                  │
  │                    │                        │──── data ────────────►│                  │
  │                    │                        │                       │                  │
  │                    │                        │ Step 6: pattern       │                  │
  │                    │                        │ analysis (company)    │                  │
  │                    │                        │◄──────────────────────│                  │
  │                    │                        │                       │                  │
  │                    │                        │ Step 7: embedding     │                  │
  │                    │                        │─────────────────────────────────────────►│
  │                    │                        │◄──── chunks_indexed ─────────────────────│
  │                    │                        │                       │                  │
  │                    │                        │ Step 8: mark_complete │                  │
  │                    │                        │ (update status, hash) │                  │
  │                    │                        │◄──────────────────────│                  │
```

### 9.2 Принудительный reanalyze

```
User                 API                 AnalysisPipelineSvc         DB/ChromaDB
  │                    │                        │                       │
  │ POST /documents/1  │                        │                       │
  │ /reanalyze         │                        │                       │
  │───────────────────►│                        │                       │
  │                    │  verify document exists │                      │
  │                    │  & user has editor role │                      │
  │                    │                        │                       │
  │                    │  get latest_version     │                      │
  │                    │  SHA256(full_text)      │                      │
  │                    │                        │                       │
  │                    │  Create DocumentAnalysis(status=running)       │
  │                    │───────────────────────►│                       │
  │                    │                        │                       │
  │                    │  asyncio.create_task()  │                      │
  │                    │───────────────────────►│                       │
  │                    │                        │                       │
  │ 202 Accepted      │                        │                       │
  │ { analysis_id }   │                        │                       │
  │◄───────────────────│                        │                       │
  │                    │                        │                       │
  │                    │     ─── Pipeline (background) ───              │
  │                    │                        │                       │
  │                    │                        │ Step 2-7:            │
  │                    │                        │ delete old data       │
  │                    │                        │ → create new data    │
  │                    │                        │──────────────────────►│
```

### 9.3 Проверка статуса pipeline

```
User                 API                 DB
  │                    │                  │
  │ GET /analysis/1    │                  │
  │ /status            │                  │
  │───────────────────►│                  │
  │                    │  SELECT          │
  │                    │  DocumentAnalysis│
  │                    │  WHERE id=1      │
  │                    │─────────────────►│
  │                    │◄─────────────────│
  │                    │                  │
  │ 200 OK            │                  │
  │ { steps_status,   │                  │
  │   status, ... }   │                  │
  │◄───────────────────│                  │
```

---

## 10. Обработка ошибок

### 10.1 Изолированные ошибки шагов

Каждый шаг обёрнут в try/except:

```python
async def _run_step(self, step_name, analysis, func, db, *args, **kwargs):
    step_info = analysis.steps_status.get(step_name, {})
    step_info["status"] = "running"
    step_info["started_at"] = datetime.utcnow().isoformat() + "Z"
    analysis.steps_status[step_name] = step_info
    await db.flush()
    
    try:
        result = await func(*args, **kwargs)
        step_info["status"] = "done"
        step_info["completed_at"] = datetime.utcnow().isoformat() + "Z"
        analysis.steps_status[step_name] = step_info
        await db.flush()
        return result
    except Exception as e:
        logger.error(f"Step {step_name} failed: {e}", exc_info=True)
        step_info["status"] = "error"
        step_info["completed_at"] = datetime.utcnow().isoformat() + "Z"
        step_info["error"] = str(e)[:500]  # Обрезаем до 500 символов
        analysis.steps_status[step_name] = step_info
        await db.flush()
        return None
```

### 10.2 Финальный статус pipeline

| Условие | Финальный статус |
|---------|-----------------|
| Все 8 шагов `done` | `complete` |
| ≥1 шаг `done`, остальные `error` | `complete` (pipeline выполнен частично) |
| Все 8 шагов `error` | `error` |
| Ошибка БД (не удалось сохранить steps_status) | `error` + error_message |

### 10.3 Критические ошибки

Pipeline считается **критически упавшим**, если:

1. Не удалось загрузить DocumentAnalysis из БД
2. Не удалось сохранить `steps_status` (ошибка БД на уровне сессии)
3. Ошибка в шаге `mark_complete`

В этих случаях pipeline логирует ошибку, но повторная попытка не выполняется.
Пользователь может запустить reanalyze вручную.

### 10.4 Таймауты

| Шаг | Таймаут | Поведение при превышении |
|-----|---------|-------------------------|
| extract_text | 5 сек | Шаг error |
| parse_structure | 30 сек | Шаг error |
| extract_terms | 30 сек | Шаг error |
| extract_abbr | 30 сек | Шаг error |
| extract_refs | 30 сек | Шаг error |
| pattern_analysis | 30 сек | Шаг error |
| embedding | 300 сек (5 мин) | Шаг error (может быть долгим для больших документов) |
| mark_complete | 10 сек | Шаг error |

Таймауты реализуются через `asyncio.wait_for()`.

---

## 11. Контракты сервисов

### 11.1 AnalysisPipelineService

```python
class AnalysisPipelineService:
    """Coordinates the 8-step analysis pipeline."""
    
    async def run(
        self,
        analysis_id: int,
        document_id: int,
        company_id: int,
        db: AsyncSession,
    ) -> None:
        """
        Run the full analysis pipeline in background.
        
        This method is called via asyncio.create_task() and manages
        the entire lifecycle of the analysis.
        
        Args:
            analysis_id: ID of the DocumentAnalysis record.
            document_id: ID of the document to analyze.
            company_id: ID of the company (holding) for tenant isolation.
            db: AsyncSession (fresh session for background task).
        """
        ...
    
    async def get_status(
        self,
        analysis_id: int,
        db: AsyncSession,
    ) -> Optional[dict]:
        """
        Get detailed status of an analysis pipeline run.
        
        Args:
            analysis_id: ID of the DocumentAnalysis record.
            db: Database session.
        
        Returns:
            Dict with status info, or None if not found.
        """
        ...

    async def get_history(
        self,
        document_id: int,
        db: AsyncSession,
    ) -> list[dict]:
        """
        Get analysis history for a document.
        
        Args:
            document_id: ID of the document.
            db: Database session.
        
        Returns:
            List of analysis records (ordered by created_at desc).
        """
        ...

    async def trigger_analysis(
        self,
        document_id: int,
        company_id: int,
        db: AsyncSession,
        force: bool = False,
    ) -> Optional[int]:
        """
        Trigger analysis for a document. Called from document_update_service.
        
        Args:
            document_id: ID of the document.
            company_id: ID of the company.
            db: Database session.
            force: If True, skip idempotency check (for reanalyze).
        
        Returns:
            analysis_id if analysis was started, None if skipped (idempotency).
        """
        ...

    # ─── Private step methods ──────────────────────────────────────
    
    async def _step_extract_text(
        self, document_id: int, db: AsyncSession
    ) -> tuple[Optional[str], Optional[int], Optional[str]]:
        """Step 1: Extract full_text from latest version.
        Returns: (full_text, version_id, file_hash)"""
        ...

    async def _step_parse_structure(
        self, full_text: str, version_id: int, db: AsyncSession
    ) -> int:
        """Step 2: Parse document structure."""
        ...

    async def _step_extract_terms(
        self, full_text: str, document_id: int, db: AsyncSession
    ) -> int:
        """Step 3: Extract terms and definitions."""
        ...

    async def _step_extract_abbr(
        self, full_text: str, document_id: int, db: AsyncSession
    ) -> int:
        """Step 4: Extract abbreviations."""
        ...

    async def _step_extract_refs(
        self, full_text: str
    ) -> int:
        """Step 5: Extract references (count only, no storage on MVP)."""
        ...

    async def _step_pattern_analysis(
        self, document_id: int, db: AsyncSession
    ) -> dict:
        """Step 6: Analyze document patterns and update company profile."""
        ...

    async def _step_embedding(
        self, document_id: int, company_id: int, title: str,
        full_text: str, is_reanalysis: bool = False
    ) -> int:
        """Step 7: Chunk, embed, and index in ChromaDB."""
        ...

    async def _step_mark_complete(
        self, analysis_id: int, file_hash: str,
        result_summary: dict, db: AsyncSession
    ) -> None:
        """Step 8: Finalize analysis record."""
        ...
```

### 11.2 Триггер в DocumentUpdateService

```python
# В классе DocumentUpdateService:

async def _trigger_analysis_pipeline(
    self,
    document_id: int,
    company_id: int,
    db: AsyncSession,
) -> None:
    """
    Trigger the analysis pipeline when a document is approved.
    
    Idempotency: if the document content hasn't changed since the last
    successful analysis, the pipeline is not triggered.
    """
    from app.services.analysis_pipeline_service import analysis_pipeline_service
    
    try:
        analysis_id = await analysis_pipeline_service.trigger_analysis(
            document_id=document_id,
            company_id=company_id,
            db=db,
            force=False,
        )
        if analysis_id:
            logger.info(f"Analysis pipeline triggered: analysis_id={analysis_id}")
        else:
            logger.info(f"Analysis skipped (idempotency): document_id={document_id}")
    except Exception as e:
        logger.error(f"Failed to trigger analysis pipeline: {e}", exc_info=True)
```

### 11.3 Адаптация PatternAnalysisService

```python
# Новый метод (или выделение из analyze_document):

async def analyze_document_patterns(
    self,
    document_id: int,
    db: AsyncSession,
) -> dict:
    """
    Analyze document patterns and update company profile.
    Does NOT check was_analyzed (for pipeline use).
    """
    doc = await self._load_document(document_id, db)
    if doc is None:
        return {"error": "Document not found"}
    
    latest_version = await self._get_latest_version(doc.id, db)
    if latest_version is None:
        return {"error": "No versions found"}
    
    structure = await self._extract_structure(latest_version, db)
    style = await self._extract_style(latest_version, db)
    terms_data = await self._collect_terms(doc.id, db)
    abbrs_data = await self._collect_abbreviations(doc.id, db)
    
    company = await self._load_company(doc.company_id, db)
    if company:
        await self._update_company_patterns(
            company, structure, style, terms_data, abbrs_data, db
        )
    
    return {
        "structure_extracted": bool(structure.get("sections")),
        "style_extracted": bool(style.get("typical_phrases")),
        "terms_collected": len(terms_data),
        "abbreviations_collected": len(abbrs_data),
    }
```

### 11.4 RagService (без изменений)

```python
# Используется как есть:
rag_service.index_document(document_id, company_id, title, full_text) -> int
rag_service.delete_document_chunks(document_id, company_id) -> bool
rag_service.search(query, company_id, top_k) -> list[dict]
```

### 11.5 Парсер (используется как есть)

```python
# Из parser_service:
parser_service._extract_terms_from_text(full_text) -> list[dict]
parser_service._extract_abbreviations_from_text(full_text) -> list[dict]
# Примечание: парсинг структуры выполняется через DocumentParser,
# который обрабатывает загруженный файл, а не full_text.
# Для pipeline: используем существующие секции (они уже созданы при загрузке)
# или парсим full_text заново (на MVP — используем существующие секции,
# на шаге parse_structure просто подсчитываем их).
```

---

## Приложение A: Пример работы pipeline

### A.1 Успешный сценарий

```
1. Пользователь меняет статус документа #5 на "approved"
2. document_update_service.calculate_idempotency():
   - analysis_hash = None (никогда не анализировался)
   - file_hash = "a1b2c3d4..."
   - Решение: запустить анализ
3. Создаётся DocumentAnalysis(id=100, document_id=5, status="running")
4. Document.analysis_status = "running"
5. asyncio.create_task(pipeline.run(analysis_id=100, document_id=5, company_id=1, db=...))
6. HTTP-ответ: 200 OK (статус изменён, анализ запущен)
7. Pipeline выполняется (8 шагов, ~30 секунд для документа 20 стр.)
8. DocumentAnalysis.status = "complete"
9. Document.analysis_hash = "a1b2c3d4..."
10. Document.analysis_status = "complete"
```

### A.2 Частичная ошибка

```
1. Шаг 3 (extract_terms) упал с ошибкой "Unexpected token"
2. Шаг 4 (extract_abbr) выполнен успешно
3. Все остальные шаги успешны
4. steps_status: {extract_text: done, parse_structure: done,
   extract_terms: error, extract_abbr: done, ..., mark_complete: done}
5. result_summary.failed_steps = 1
6. DocumentAnalysis.status = "complete" (частично успешно)
7. Пользователь видит, что термины не извлечены, может запустить reanalyze
```

### A.3 Идемпотентность

```
1. Документ #5 уже утверждён, analysis_hash="a1b2c3d4...", analysis_status="complete"
2. Пользователь случайно меняет статус на "archived", потом снова на "approved"
3. document_update_service.calculate_idempotency():
   - SHA256(full_text) = "a1b2c3d4..." (контент не изменился)
   - doc.analysis_hash = "a1b2c3d4..."
   - Совпадают → SKIP
4. Статус документа меняется на approved
5. Анализ НЕ запускается
6. В логе: "Analysis skipped (idempotency): document_id=5"
```

---

## Приложение B: Зависимости и новые файлы

### B.1 Новые файлы

| Файл | Назначение |
|------|-----------|
| `backend/app/models/document_analysis.py` | SQLAlchemy модель DocumentAnalysis |
| `backend/app/services/analysis_pipeline_service.py` | Сервис pipeline из 8 шагов |
| `backend/app/api/v1/analysis.py` | API router для endpoint'ов анализа |

### B.2 Изменяемые файлы

| Файл | Изменения |
|------|-----------|
| `backend/app/models/document.py` | Добавить `analysis_hash`, `analysis_status`, связь с `DocumentAnalysis` |
| `backend/app/models/__init__.py` | Добавить импорт `DocumentAnalysis` |
| `backend/app/services/document_update_service.py` | Заменить прямой вызов на `_trigger_analysis_pipeline()` |
| `backend/app/services/pattern_analysis_service.py` | Выделить `analyze_document_patterns()` без проверки `was_analyzed` |
| `backend/app/api/v1/router.py` | Подключить `analysis_router` |
| `backend/app/schemas/document.py` | Добавить `AnalysisStatusResponse`, `AnalysisHistoryResponse` и т.д. (если нужно — или в отдельном schemas/analysis.py) |
