# Stage Definition: Stage 1 / Increment B

## Name
Реестр документов + Загрузка и парсинг Word/PDF

## Goal
Пользователь может загрузить документ (Word/PDF), сервис парсит его структуру (оглавление, разделы, подразделы, таблицы) и извлекает термины/сокращения. Документ отображается в реестре со статусом, отображается карточка документа с древовидной структурой разделов.

## Business value
- Автоматизация анализа существующих регламентов — сокращение ручного труда
- Формирование базы знаний холдинга: каждый загруженный документ становится источником терминов и структуры
- Фундамент для генератора (Increment C): генератор будет использовать распаршенные документы как обучающие примеры

## Scope
### Backend
1. Новые модели БД: Document, DocumentVersion, DocumentSection, DocumentTable, DocumentTerm, DocumentAbbreviation
2. Alembic migration
3. File upload endpoint (multipart) — POST /api/v1/documents/upload
4. Document CRUD endpoints — list, get, update (status, title), delete (archive)
5. Document parser service:
   - Word (.docx): python-docx — извлечение заголовков (Heading 1-4), текста абзацев, таблиц
   - PDF (базовый): PyMuPDF + pdfplumber — извлечение текста, таблиц (простых)
   - Извлечение терминов и сокращений: поиск по шаблонам ("термин - определение") и секциям "Термины и определения"
6. Version history endpoint — GET /api/v1/documents/{id}/versions
7. File download endpoint — GET /api/v1/documents/versions/{version_id}/download
8. Local file storage service (хранение в /storage/documents/)

### Frontend
1. Страница «Реестр документов» — таблица с фильтрами (статус, поиск), сортировка, пагинация
2. Страница «Загрузка документа» — drag-and-drop upload + форма (название, описание)
3. Страница «Карточка документа» — просмотр метаданных, статус, древовидная структура разделов
4. Страница «Версии документа» — список версий с возможностью скачать
5. Компонент «Древовидная структура документа» — Ant Design Tree
6. Обновление Header — добавление навигации (Реестр, Загрузить)

### Database (SQLite + Alembic)
1. documents: id, holding_id (FK), title, description, status (draft/review/approved/archived), created_by (FK), created_at, updated_at
2. document_versions: id, document_id (FK), version_number, file_path, file_type (docx/pdf), file_size, mime_type, uploaded_by (FK), created_at
3. document_sections: id, document_version_id (FK), parent_id (FK, self-ref), title, level, order_num, content
4. document_tables: id, document_version_id (FK), section_id (FK), caption, order_num, html_content
5. document_terms: id, document_id (FK), term, definition
6. document_abbreviations: id, document_id (FK), abbreviation, full_form

## Out of scope
- Ручное добавление влияющих документов (Increment D)
- Версионность документов (новая версия при изменении — Increment D)
- Реестр внутренних приказов (Increment D)
- MCP-сервер (Increment E)
- Сложный парсинг PDF (таблицы с объединёнными ячейками, сноски)
- Семантический граф связей (визуальный — Stage 2)

## Backend work
1. Models: Document, DocumentVersion, DocumentSection, DocumentTable, DocumentTerm, DocumentAbbreviation
2. Migration: alembic revision
3. Schemas: Pydantic models for all entities
4. Storage service: LocalFileStorage (save/read/delete files in /storage/documents/)
5. Parser service: 
   - DocxParser (python-docx) — extract headings, paragraphs, tables
   - PdfParser (PyMuPDF + pdfplumber) — extract text, tables
   - TermExtractor — pattern matching for terms and abbreviations
6. Document service: CRUD, upload logic (save file → parse → store parsed data)
7. API router: /api/v1/documents with all sub-routes
8. Tests: pytest for upload, parsing, CRUD

## Frontend work
1. Document list page (реестр) — Ant Design Table with columns, filters, search
2. Upload page — Ant Design Upload (drag & drop), form with title/description, progress bar
3. Document detail page — Ant Design Descriptions, status Tag, Tree for sections, tabs for terms/tables
4. Version history — Ant Design Timeline or List
5. Navigation update — Header with links to /documents, /documents/upload
6. API service: documents.ts
7. Store: documentStore.ts (Zustand)

## Acceptance criteria
1. POST /api/v1/documents/upload (Word .docx) — file saved, parsed, structure extracted
2. POST /api/v1/documents/upload (PDF) — file saved, parsed (basic), structure extracted
3. GET /api/v1/documents — list of documents, filtered by holding (current user)
4. GET /api/v1/documents/{id} — full document metadata + parsed data
5. PUT /api/v1/documents/{id} — update title, description, status
6. GET /api/v1/documents/{id}/versions — list of all versions
7. GET /api/v1/documents/versions/{version_id}/download — file download
8. Extracted terms and abbreviations are stored and retrievable
9. Extracted sections form a proper tree (parent-child hierarchy)
10. Frontend upload works (drag & drop) with progress indication
11. Frontend reestr shows documents with status tags and filters
12. All tests pass

## Required tests
- unit: parser (docx mock, pdf mock), term extractor, storage service
- integration: upload → parse → verify extracted data, CRUD operations
- smoke: one e2e upload flow

## Risks
- R1 (из плана): качество парсинга PDF — разные форматы вёрстки
  - Mitigation: начинаем с Word как приоритет, PDF — best effort
- Размер файла: большие документы (>50MB) могут вызывать таймауты
  - Mitigation: ограничение 20MB на MVP, асинхронная обработка в перспективе
- Неоднозначность извлечения терминов: нет единого формата оформления
  - Mitigation: набор эвристик + ручная корректировка

## Dependencies
- python-docx
- PyMuPDF (fitz)
- pdfplumber
- python-multipart (для FastAPI)
- Increment A: холдинги и аутентификация уже работают

## Deliverables
- Код backend (models, services, api, tests)
- Код frontend (pages, components, api, store)
- Миграции БД
- Тестовые документы (sample.docx, sample.pdf)
- Stage report
- QA-чеклист
