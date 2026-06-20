# Stage Definition: Stage 1 / Increment E

## Name
MCP-сервер + Поиск законодательства + Карта влияний

## Goal
Сервис является MCP-сервером для AI-агентов, умеет искать актуальное законодательство на pravo.gov.ru и показывает полную карту влияний документа (какие документы на него влияют и на какие он влияет).

## Scope
### Backend
1. MCP-сервер:
   - Интеграция через @modelcontextprotocol/sdk (Python)
   - Инструменты:
     - get_holding_profile(holding_id: int) → HoldingProfile
     - search_documents(query: str, holding_id: int, status: str | None) → Document[]
     - get_document_relationships(document_id: int) → Relationship[]
     - generate_draft(context: str, holding_id: int, draft_file_ids: int[] | None, influencing_doc_ids: int[] | None) → DocumentResponse
   - MCP-сервер запускается как отдельный процесс или subprocess
   - Использует те же сервисы, что и REST API

2. Legislation Search:
   - Адаптер для pravo.gov.ru:
   - Поиск по ключевым словам → парсинг результатов
   - Поиск по официальному API или парсинг HTML (если API нет)
   - Результаты: название, номер, дата, URL, текст (начало)
   - GET /api/v1/legislation/search?query=...&page=1&page_size=10
   - GET /api/v1/legislation/sources — список доступных источников
   - Кеширование результатов (in-memory, TTL 1 час)

3. Impact Map:
   - GET /api/v1/documents/{id}/impact-map — полная карта влияний
   - Возвращает: входящие связи (что влияет на документ) + исходящие (на что влияет документ)
   - Группировка по типам: amendments, references, orders

### Frontend
1. MCP-сервер — без UI (инструмент для AI-агентов)
2. Страница «Карта влияний»:
   - Вкладка в DocumentDetailPage или отдельная страница
   - Две таблицы: «Влияющие документы» и «Затрагиваемые документы»
   - Группировка по типу связи
3. Страница «Поиск законодательства»:
   - Поисковая строка
   - Результаты поиска (таблица: название, номер, дата, источник)
   - Ссылка на оригинал
   - Кнопка «Добавить в реестр» (сохранить как документ)
4. Header: обновить навигацию

## Out of scope
- Визуальный граф (Stage 2)
- Платные источники (Консультант+, Гарант) — Stage 2
- Конструктор источников — Stage 2

## Acceptance criteria
1. MCP-клиент может вызвать get_holding_profile и получить профиль
2. MCP-клиент может вызвать search_documents и найти документы
3. MCP-клиент может вызвать get_document_relationships и получить связи
4. MCP-клиент может вызвать generate_draft и получить готовый документ
5. GET /api/v1/legislation/search возвращает результаты с pravo.gov.ru
6. Карта влияний показывает входящие и исходящие связи
7. Все тесты проходят

## Risks
- pravo.gov.ru может не иметь стабильного API — парсинг HTML
- MCP SDK может быть нестабильным (молодой протокол)
- CORS при поиске законодательства

## Dependencies
- @modelcontextprotocol/sdk (Python)
- httpx/requests для pravo.gov.ru
- BeautifulSoup для парсинга HTML
- Все предыдущие инкременты
