# Stage Definition: Stage 1 / Increment C

## Name
Генератор документов + Интеграция с GigaChat Pro

## Goal
Пользователь может описать контекст нового регламента, прикрепить черновики, указать влияющие документы — и получить готовый Word-документ, оформленный по шаблону холдинга. Сервис использует GigaChat Pro для генерации контента и python-docx для оформления.

## Business value
- Скорость создания регламента: месяцы → часы
- Единообразие: документ следует шаблону холдинга
- Связность: автоматически учитывает связанные документы и термины

## Scope
### Backend
1. Holding profile — добавить поля: document_structure (JSON), style_settings (JSON), use_gost (bool)
2. Alembic migration для новых полей холдинга
3. GigaChat Pro client:
   - OAuth 2.0 client credentials → access token
   - Chat completion API (GigaChat-Pro model)
   - Retry logic, error handling, rate limiting
4. Prompt builder service:
   - Сбор контекста: профиль холдинга, связанные документы, термины, черновики
   - Построение системного промпта с шаблоном JSON-ответа
   - Форматирование результатов
5. Document generator service:
   - Приём контекстного описания + файлов черновиков + ID влияющих документов
   - Вызов GigaChat → получение структурированного ответа (JSON)
   - Конвертация JSON → .docx через python-docx (заголовки, абзацы, таблицы, нумерация)
   - Сохранение результата как Document + DocumentVersion (переиспользование моделей Increment B)
6. API endpoint:
   - POST /api/v1/generator/generate — генерация документа
   - GET /api/v1/generator/status/{task_id} — статус (если async)

### Frontend
1. Страница «Генератор» — `/generator`
   - Контекстное окно (textarea/rich editor) для описания
   - Загрузка черновиков (drag & drop, docx/pdf)
   - Выбор влияющих документов (select с поиском из реестра)
   - Кнопка «Сгенерировать»
2. Процесс генерации:
   - Progress/Spinner с сообщениями («Анализируем контекст...», «Генерируем текст...», «Оформляем документ...»)
   - Отображение результата (ссылка на скачивание + кнопка открыть в реестре)
3. Обновление Header — добавить ссылку «Генератор»

### Database
- Holding: добавить поля document_structure (JSON), style_settings (JSON), use_gost (bool)
- Миграция Alembic

## Out of scope
- Поиск внешнего законодательства (Increment E)
- MCP-сервер (Increment E)
- Онлайн-редактор документа
- Сохранение черновиков генерации

## Acceptance criteria
1. POST /api/v1/generator/generate принимает контекстное описание + черновики + влияющие документы
2. GigaChat Pro вызывается с корректным промптом
3. Результат парсится из JSON-ответа GigaChat
4. .docx создаётся с правильной структурой (заголовки, параграфы)
5. Документ сохраняется в реестре с первым версией
6. Фронтенд показывает прогресс генерации
7. Фронтенд предлагает скачать или открыть документ
8. Учитываются поля холдинга (структура, стиль, ГОСТ)
9. Все тесты проходят

## Risks
- GigaChat API может быть недоступен / медленный
- LLM-галлюцинации в содержании (выдуманные законы)
- JSON-ответ может быть невалидным
- Ограничения по токенам у GigaChat

## Dependencies
- GigaChat Pro API key (client_id, client_secret)
- python-docx (уже установлен)
- httpx или aiohttp для API-вызовов
- Increment A: холдинги, аутентификация
- Increment B: реестр документов, термины, структура

## Deliverables
- GigaChat client
- Prompt builder
- Document generator service
- API endpoints
- Frontend: страница генератора
- Миграция БД
- Тесты
- Stage report
