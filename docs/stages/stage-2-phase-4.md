# Stage Definition: Stage 2 / Phase 4 — Анализ при статусе «Утверждён»

## Name
AnalysisPipeline — автоматический и ручной анализ утверждённых документов

## Goal
При установке статуса `approved` система автоматически запускает асинхронный pipeline анализа документа (структура, термины, сокращения, стиль, векторная индексация) и защищает от повторного анализа, если контент не изменился. Пользователь может просматривать историю анализов и принудительно перезапускать анализ.

## Business value
- **Автоматизация наполнения базы знаний:** каждый утверждённый документ автоматически учит систему (термины, сокращения, паттерны оформления, векторные embedding'и)
- **Идемпотентность:** повторное утверждение того же контента не вызывает повторный анализ
- **Прозрачность:** история анализов с детальным статусом каждого шага pipeline
- **Устойчивость:** ошибка одного шага не прерывает весь pipeline

## Scope

### Backend (Python / FastAPI)
1. **Модель `DocumentAnalysis`** (SQLAlchemy) — таблица для отслеживания каждого запуска анализа с детальным статусом по шагам
2. **AnalysisPipelineService** — единый асинхронный pipeline из 8 шагов, объединяющий PatternAnalysisService и RagService
3. **File hash idempotency** — SHA256(`full_text`) → проверка `DocumentAnalysis.file_hash` + `Document.analysis_hash`
4. **Изменения модели `Document`** — добавлены поля `analysis_hash` и `analysis_status`
5. **Три новых API endpoint'а:**
   - `GET /api/v1/documents/{id}/analyses` — история анализов документа
   - `GET /api/v1/analysis/{analysis_id}/status` — детальный статус pipeline по шагам
   - `POST /api/v1/documents/{id}/reanalyze` — принудительный перезапуск (сброс idempotency)
6. **Переработка триггера в `document_update_service.py`:** при approved → проверка хеша → запуск pipeline в `asyncio.create_task()`
7. **Стратегия «Replace» при повторном анализе:** старые данные удаляются, создаются новые
8. **Alembic миграция** — создание таблицы `document_analyses`, добавление полей `analysis_hash` и `analysis_status` в `documents`

### Database (SQLite + Alembic)
1. **Новая таблица:** `document_analyses` — id, document_id, document_version_id, file_hash, status, steps_status, error_message, result_summary, created_at, completed_at
2. **Изменение таблицы:** `documents` — `analysis_hash` (VARCHAR(64), nullable), `analysis_status` (VARCHAR(10), default='none')

### Infra / DevEx
1. Обновление триггера в `document_update_service.py` — замена синхронного вызова на background task
2. Тесты: unit-тесты pipeline, idempotency, API endpoint'ов

## Out of scope
- ❌ Frontend (будет в Инкременте A2)
- ❌ Уведомления пользователя о завершении анализа (WebSocket / email)
- ❌ Отмена запущенного pipeline
- ❌ Retry-логика для упавших шагов (базовая в первой версии — ручной перезапуск через reanalyze)
- ❌ Сложная оркестрация (Celery / Redis Queue) — `asyncio.create_task()` достаточно для MVP

## Backend work
1. **Модель `DocumentAnalysis`** (`backend/app/models/document_analysis.py`)
2. **Изменение модели `Document`** — добавление полей `analysis_hash` и `analysis_status`
3. **AnalysisPipelineService** (`backend/app/services/analysis_pipeline_service.py`) — 8 шагов pipeline
4. **Обновление `document_update_service.py`** — триггер на approved с проверкой file_hash и запуском background task
5. **Новый API router** — `backend/app/api/v1/analysis.py` (3 endpoint'а)
6. **Подключение router'а** в `backend/app/api/v1/router.py`
7. **Alembic миграция** — новая ревизия с созданием таблицы и добавлением колонок

## Frontend work
- Нет (Инкремент A2)

## Acceptance criteria
1. При смене статуса на `approved` создаётся `DocumentAnalysis(status=running)` и запускается pipeline в background
2. Если контент документа не менялся (SHA256 совпадает), повторный approved не запускает анализ
3. Все 8 шагов pipeline выполняются последовательно; ошибка одного шага не прерывает остальные
4. После завершения pipeline: `DocumentAnalysis.status=complete`, `Document.analysis_status=complete`, `Document.analysis_hash=SHA256`
5. Термины и сокращения извлечены и сохранены в `document_terms` / `document_abbreviations`
6. ChromaDB содержит чанки документа с корректными метаданными
7. `GET /api/v1/documents/{id}/analyses` возвращает историю анализов (включая running/error)
8. `GET /api/v1/analysis/{analysis_id}/status` возвращает статус каждого шага
9. `POST /api/v1/documents/{id}/reanalyze` принудительно перезапускает анализ (очищает старые данные)
10. После reanalyze старая запись анализа сохраняется в истории, создаётся новая
11. Если ChromaDB была очищена (чанки удалены), но `analysis_hash` совпадает — анализ перезапускается для восстановления чанков

## Required tests
- **unit:** pipeline шаги изолированно, проверка SHA256, формат steps_status JSON
- **integration:**
  - Upload документ → статус approved → pipeline завершён → термины/сокращения созданы → ChromaDB содержит чанки
  - Повторный approved без изменения контента → анализ НЕ запускается
  - Reanalyze → старые данные удалены → новые созданы
  - Ошибка шага 3 не влияет на шаги 4-8 (pipeline продолжается)
- **smoke:** один e2e-тест: upload → approved → ожидание анализа → проверка истории

## Risks

| Риск | Вероятность | Митигация |
|------|------------|-----------|
| ChromaDB нестабильна на Windows | Низкая | Шаг embedding обёрнут в try/except; pipeline продолжается |
| Анализ большого документа (>100 стр) занимает >10 минут | Средняя | Асинхронный pipeline; пользователь может проверять статус через GET endpoint |
| File hash не меняется, но пользователь хочет переанализировать | Низкая | `POST /reanalyze` принудительно сбрасывает idempotency |
| Ollama embedding timeout | Средняя | `httpx` timeout=30s на запрос; ошибка логируется, pipeline продолжается |
| Одновременный запуск pipeline для одного документа | Низкая | Проверка `Document.analysis_status != 'running'` перед запуском |

## Dependencies
- Фаза 2 (парсеры, PatternAnalysisService, RagService) — ✅ реализовано
- Фаза 3 (статусная модель, права доступа) — ✅ реализовано
- Python 3.11+
- asyncio (встроенный)

## Deliverables
- Код backend (модель, сервис, API, тесты)
- Миграция Alembic
- Pipeline spec (`docs/specs/phase-4-analysis-pipeline.md`)
- API spec (`docs/specs/phase-4-api-spec.md`)
- Stage report
- QA-чеклист
