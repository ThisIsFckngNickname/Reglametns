# Stage Definition: Stage 3 / Phase 5 / Increment B1 — RAG-enhanced генератор + общехолдинговые термины

## Name
RAG-enhanced генератор с общехолдинговым перечнем терминов и веб-поиском

## Goal
Генератор документов использует проанализированные документы холдинга (из Фаз 2+4), общехолдинговый перечень терминов и сокращений, веб-поиск актуального законодательства и загруженные пользователем черновики для создания документов в корпоративном стиле. Пользователь может управлять общехолдинговыми терминами и сокращениями через отдельную страницу.

## Business value
- **Качество генерации:** документы пишутся с использованием реальных терминов холдинга, ссылок на внутренние документы и актуальное законодательство
- **Единая терминология:** общехолдинговый перечень терминов обеспечивает согласованность терминологии во всех документах
- **Автоматическое пополнение:** при анализе утверждённых документов термины автоматически добавляются в общехолдинговый перечень
- **Информированность LLM:** модель получает результаты поиска в интернете, что повышает актуальность ссылок на законодательство

## Scope

### Backend (Python / FastAPI)

#### Блок 1: CompanyTerm и CompanyAbbreviation — общехолдинговый перечень терминов
1. **Модели `CompanyTerm` и `CompanyAbbreviation`** (SQLAlchemy) — таблицы `company_terms` и `company_abbreviations` с unique constraint `(company_id, term)` / `(company_id, abbreviation)`
2. **CRUD API** — 8 endpoint'ов для управления терминами и сокращениями холдинга (список с пагинацией/поиском, создание, обновление, удаление)
3. **Pipeline integration** — расширение шагов `extract_terms` и `extract_abbr` в AnalysisPipelineService: после извлечения терминов/сокращений документа → синхронизация с общехолдинговым перечнем (INSERT if not exists, skip if exists with different definition)
4. **Pydantic схемы** — `CompanyTermResponse`, `CompanyTermCreate`, `CompanyTermUpdate`, аналогично для Abbreviation

#### Блок 2: RAG-enhanced генератор (PromptBuilder V2)
1. **PromptBuilder V2** — новый формат супер-промпта из 6 источников:
   - Структура документа (из company.document_structure)
   - Термины и сокращения холдинга (из company_terms, company_abbreviations)
   - Похожие документы (из ChromaDB через RagService.search, top-k=5)
   - Информация из интернета (WebSearchService)
   - Черновик пользователя (если загружен)
   - Влияющие документы (существующее)
2. **Новый системный промпт** — LLM позиционируется как юрист холдинга, обязана использовать термины холдинга, ссылаться на внутренние документы

#### Блок 3: WebSearchService (доработка)
1. **Обязательный сервис** (не опциональный) — поиск информации в интернете перед генерацией
2. **DuckDuckGo поиск** — уже реализован, проверить работоспособность
3. **Парсинг страниц** — извлечение текста из топ-3 результатов через httpx + BeautifulSoup
4. **Обработка ошибок** — если поиск упал (rate limit, нет сети) — не блокировать генерацию, пропустить блок
5. **Метод `enrich_prompt()`** — поиск и форматирование результатов для промпта

#### Блок 4: GeneratorService V2
1. **Новый метод `generate_document()`** — полный pipeline сбора контекста из 6 источников
2. **Новый API `POST /api/v1/generator/generate`** — расширенное тело запроса:
   - `topic` (обязательное) — тема документа
   - `document_type` (regulation/order/provision/policy/directive)
   - `company_id` (обязательное)
   - `draft_file_id` (опционально)
   - `influence_document_ids` (опционально)
   - `search_enabled` (по умолчанию true)
3. **Ответ** — без изменений: `{document_id, filename, status: "draft", version: 1}`

#### Блок 5: Frontend — Генератор V2
1. **Селект типа документа** — выбор типа влияет на структуру промпта
2. **Загрузка черновика** — drag-and-drop .docx / .txt, отображение загруженного файла
3. **Выбор влияющих документов** — мультиселект с поиском из GET /api/v1/documents?company_id=X (только approved)
4. **Чекбокс «Искать информацию в интернете»** — включён по умолчанию
5. **Расширенные шаги генерации** — «Подготовка» → «Поиск информации» → «Анализ документов компании» → «Генерация» → «Оформление»
6. **Результат** — скачать + ссылка в реестр (как сейчас)

#### Блок 6: Frontend — Страница «Термины и сокращения»
1. **Новая страница `TermsPage.tsx`** — доступна по пути `/terms`
2. **Вкладки** — «Термины» | «Сокращения»
3. **Таблица терминов** — колонки: Термин, Определение, Источник, Ручной, Действия
4. **Поиск по названию** — фильтрация
5. **Пагинация**
6. **CRUD через модалки** — создание, редактирование, удаление с подтверждением
7. **Защита** — только editor+ могут создавать/редактировать/удалять
8. **Навигация** — пункт в Header/Sidebar «Термины и сокращения» (между Генератором и Документами)

### Database (SQLite + Alembic)
1. **Новая таблица:** `company_terms` — id, company_id (FK), term, definition, source_document_id (FK, nullable), is_manual, created_at, updated_at. Unique: (company_id, term)
2. **Новая таблица:** `company_abbreviations` — id, company_id (FK), abbreviation, full_form, source_document_id (FK, nullable), is_manual, created_at, updated_at. Unique: (company_id, abbreviation)

### Infra / DevEx
1. Alembic миграция — создание таблиц company_terms и company_abbreviations
2. Тесты: unit-тесты сервисов, API endpoint'ов, pipeline integration

## Out of scope
- ❌ Фильтрация реестра по типу документа (B2)
- ❌ Связи приказов с документами (B3)
- ❌ DocumentType в модели Document (будет в B2)
- ❌ WebSocket уведомления о прогрессе генерации
- ❌ Отмена запущенной генерации
- ❌ История изменений общехолдинговых терминов (audit log)

## Backend work
1. **Модели:** `CompanyTerm`, `CompanyAbbreviation` (`backend/app/models/company_term.py`, `backend/app/models/company_abbreviation.py`)
2. **Обновление `models/__init__.py`** — регистрация новых моделей
3. **Pydantic схемы:** `company_term.py` — 6 схем (Create, Update, Response, List)
4. **API router:** `backend/app/api/v1/company_terms.py` — 8 endpoint'ов
5. **Подключение router'а** в `backend/app/api/v1/router.py`
6. **Расширение `PromptBuilder`** — новый формат супер-промпта (PromptBuilder V2)
7. **Расширение `GeneratorService`** — новый метод `generate_document()` с полным сбором контекста
8. **Расширение `POST /api/v1/generator/generate`** — новое тело запроса
9. **Доработка `WebSearchService`** — парсинг страниц, enrich_prompt, обязательный режим
10. **Расширение `DataLoader`** — загрузка `CompanyTerm` / `CompanyAbbreviation`
11. **Pipeline integration** — обновление шагов `extract_terms` и `extract_abbr` в `AnalysisPipelineService`
12. **Alembic миграция** — две новые таблицы

## Frontend work
1. **GeneratorPage V2** — селект типа документа, загрузка черновика, выбор влияющих документов, чекбокс поиска, расширенные шаги
2. **TermsPage** — новая страница с вкладками, таблицами, модалками CRUD
3. **Header** — новый пункт навигации «Термины и сокращения»
4. **App.tsx** — новый route `/terms`
5. **API service:** `companyTerms.ts` — CRUD для терминов и сокращений
6. **Store:** `companyTermsStore.ts` (Zustand) — управление состоянием
7. **Types:** расширение `types/index.ts` — `CompanyTerm`, `CompanyAbbreviation`, `GenerateRequestV2`

## Acceptance criteria
1. Термины и сокращения автоматически добавляются в общехолдинговый перечень при анализе утверждённых документов
2. Существующий термин с другим определением не перезаписывается (пропускается)
3. Пользователь может создавать, редактировать, удалять термины и сокращения через UI
4. Только editor+ могут изменять общехолдинговый перечень
5. PromptBuilder V2 собирает промпт из 6 источников: структура, термины холдинга, похожие документы, результаты поиска, черновик, влияющие документы
6. WebSearchService находит информацию по теме документа, парсит топ-3 страницы и добавляет в промпт
7. При ошибке веб-поиска генерация продолжается без него
8. Пользователь может загрузить черновик (.docx, .txt) и выбрать влияющие документы
9. Селект типа документа влияет на структуру промпта
10. Шаги генерации отображают прогресс: Подготовка → Поиск информации → Анализ документов → Генерация → Оформление

## Required tests
- **unit:**
  - Модели CompanyTerm, CompanyAbbreviation (unique constraint, relationships)
  - PromptBuilder V2 — сборка промпта с разными комбинациями источников
  - WebSearchService.enrich_prompt — форматирование результатов
  - Pipeline integration — синхронизация терминов с общехолдинговым перечнем
- **integration:**
  - CRUD API: создание, получение списка, обновление, удаление терминов/сокращений
  - Генерация с черновиком + влияющими документами + поиском
  - Генерация при ошибке веб-поиска (не блокируется)
  - Pipeline: approved → анализ → термины документа → синхронизация с company_terms
- **e2e/smoke:**
  - Создать термин вручную → отображается в списке → редактировать → удалить
  - Загрузить документ → approved → проверить что термины появились в company_terms

## Risks

| Риск | Вероятность | Митигация |
|------|------------|-----------|
| DuckDuckGo блокирует частые запросы (rate limiting) | Средняя | Graceful degradation: пропуск блока при ошибке; кэширование результатов |
| Веб-парсинг через BeautifulSoup ломается при изменении структуры сайтов | Высокая | Fallback только на snippet (без парсинга страницы); логирование ошибок |
| Prompt V2 превышает лимит контекста LLM (256K токенов) | Низкая | Обрезка по параграфам; пропорциональное распределение бюджета токенов |
| Одновременная генерация нескольких документов нагружает Ollama | Средняя | Постановка в очередь (asyncio); ограничение 1 concurrent generation на company |
| Большой общехолдинговый перечень (>1000 терминов) делает промпт огромным | Средняя | Выборка только релевантных терминов (по semantic search); ограничение top-N по релевантности |

## Dependencies
- Фаза 2 (парсеры, PatternAnalysisService, RagService) — ✅ реализовано
- Фаза 3 (статусная модель, права доступа, JWT) — ✅ реализовано
- Фаза 4 (AnalysisPipelineService, ChromaDB idempotency) — ✅ реализовано
- Python 3.11+
- duckduckgo_search (уже есть в требованиях)
- beautifulsoup4 + lxml (для парсинга страниц)

## Deliverables
- Код backend (модели, схемы, сервисы, API, тесты)
- Код frontend (страницы, компоненты, API, store)
- Миграция Alembic
- Pipeline spec (`docs/specs/phase-5-b1-rag-generator.md`)
- WebSearch spec (`docs/specs/phase-5-b1-websearch.md`)
- Company terms spec (`docs/specs/phase-5-b1-company-terms.md`)
- API spec (`docs/specs/phase-5-b1-api-spec.md`)
- Stage report
- QA-чеклист
