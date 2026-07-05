# SRP — Системные спецификации (SA Document)

> **Проект**: Service for Regulations and Policies (SRP)
> **Версия**: 0.1.0 (MVP)
> **Дата**: 2026-06-30
> **Аудитория**: BE (Backend Engineer), FE (Frontend Engineer)

---

## Оглавление

1. [Контекст и цели](#1-контекст-и-цели)
2. [API Contracts (OpenAPI-стиль)](#2-api-contracts-openapi-стиль)
3. [Архитектура LLM-провайдеров](#3-архитектура-llm-провайдеров)
4. [Схема БД](#4-схема-бд)
5. [Структура промптов](#5-структура-промптов)
6. [Модульная структура backend](#6-модульная-структура-backend)
7. [Модульная структура frontend](#7-модульная-структура-frontend)
8. [План реализации по Stage](#8-план-реализации-по-stage)
9. [Edge Cases, Risks, Open Questions](#9-edge-cases-risks-open-questions)

---

## 1. Контекст и цели

### 1.1. Продукт

**SRP** — веб-сервис для генерации корпоративных регламентов в формате Word (.docx) через AI. Пользователь описывает тему регламента текстом, сервис отправляет запрос к LLM, получает структурированный ответ, преобразует его в .docx и отдаёт на скачивание.

### 1.2. Ограничения MVP

- Только один пользователь (без авторизации, ролей, мультитенантности)
- Синхронная генерация (пользователь ждёт ответ)
- .docx без полноценного титульника (заголовок + разделы)
- Хранение .docx локально в `generated/{uuid}.docx`
- База данных — SQLite

### 1.3. Ключевые нефункциональные требования

| Требование | Цель |
|---|---|
| Время генерации | ≤ 60 сек (таймаут на провайдера: 60 сек) |
| Поддерживаемые AI | Groq (Llama 3.3 70B / Qwen3 32B), YandexGPT (5 Pro), Ollama (Qwen2.5-7B) |
| Размер файла .docx | ≤ 5 MB |
| Язык | Русский (системный промпт + генерация) |
| Доступность | Сервис падает, если все провайдеры недоступны |

---

## 2. API Contracts (OpenAPI-стиль)

### 2.1. POST /api/generate — Генерация регламента

**Request**

```
POST /api/generate
Content-Type: application/json
```

```json
{
  "topic": "Регламент по учёту ГСМ на АЗС",
  "provider": "auto"
}
```

**Поля запроса**

| Поле | Тип | Обязат. | По умолчанию | Описание |
|---|---|---|---|---|
| `topic` | string | да | — | Тема регламента (1–2000 символов) |
| `provider` | enum | нет | `"auto"` | Выбор AI-провайдера: `"auto"`, `"groq"`, `"yandexgpt"`, `"ollama"` |

**Успешный ответ (201 Created)**

```json
{
  "id": "a1b2c3d4-...",
  "topic": "Регламент по учёту ГСМ на АЗС",
  "filename": "Reglament-po-uchetu-GSM-na-AZS.docx",
  "provider_used": "groq",
  "status": "completed",
  "created_at": "2026-06-30T12:00:00Z"
}
```

**Поля ответа**

| Поле | Тип | Описание |
|---|---|---|
| `id` | UUIDv4 | Уникальный идентификатор документа |
| `topic` | string | Тема (эхо запроса) |
| `filename` | string | Имя файла для скачивания (латиница, безопасное) |
| `provider_used` | string | Провайдер, который фактически исполнил запрос |
| `status` | enum | `"completed"` / `"failed"` |
| `created_at` | datetime (ISO 8601) | Время создания |

**Ошибки**

| Код | Описание | Тело ответа |
|---|---|---|
| 422 | Некорректный запрос (topic пустой/слишком длинный, неверный provider) | `{"detail": [{"field": "topic", "message": "..."}]}` |
| 503 | Все провайдеры недоступны или таймаут | `{"detail": "No AI providers available. Please try again later."}` |
| 500 | Внутренняя ошибка (ошибка генерации .docx, БД и т.д.) | `{"detail": "Internal server error"}` |

**Ограничения запроса**

- `topic` min 1 символ, max 2000 символов
- `provider` строго из набора: `auto`, `groq`, `yandexgpt`, `ollama`

### 2.2. GET /api/documents — История генераций

**Request**

```
GET /api/documents?limit=20&offset=0
```

| Параметр | Тип | Обязат. | По умолч. | Описание |
|---|---|---|---|---|
| `limit` | integer | нет | 20 | Максимум записей (1–100) |
| `offset` | integer | нет | 0 | Смещение для пагинации |

**Успешный ответ (200 OK)**

```json
{
  "items": [
    {
      "id": "a1b2c3d4-...",
      "topic": "Регламент по учёту ГСМ на АЗС",
      "provider_used": "groq",
      "status": "completed",
      "created_at": "2026-06-30T12:00:00Z"
    }
  ],
  "total": 42
}
```

**Поля `items[]`**

| Поле | Тип | Описание |
|---|---|---|
| `id` | UUIDv4 | Идентификатор |
| `topic` | string | Тема |
| `provider_used` | string | Провайдер |
| `status` | enum | `"completed"` / `"failed"` |
| `created_at` | datetime | Время |

> **Примечание**: В списке не возвращаются `prompt`, `raw_response`, `docx_path` — только метаданные.

### 2.3. GET /api/documents/{id} — Детали документа

**Request**

```
GET /api/documents/a1b2c3d4-...-1234
```

**Успешный ответ (200 OK)**

```json
{
  "id": "a1b2c3d4-...",
  "topic": "Регламент по учёту ГСМ на АЗС",
  "prompt": "Регламент по учёту ГСМ на АЗС",
  "provider_used": "groq",
  "status": "completed",
  "error_message": null,
  "created_at": "2026-06-30T12:00:00Z"
}
```

**Ошибки**

| Код | Описание |
|---|---|
| 404 | Документ с таким id не найден |

> **Примечание**: `raw_response` и `docx_path` не возвращаются в API — они внутренние.

### 2.4. GET /api/documents/{id}/download — Скачать .docx

**Request**

```
GET /api/documents/a1b2c3d4-.../download
```

**Успешный ответ (200 OK)**

- Content-Type: `application/vnd.openxmlformats-officedocument.wordprocessingml.document`
- Content-Disposition: `attachment; filename="Reglament-po-uchetu-GSM-na-AZS.docx"`
- Тело: бинарный .docx файл

**Ошибки**

| Код | Описание |
|---|---|
| 404 | Документ не найден |
| 404 | Файл .docx не найден на диске (например, удалён) |
| 400 | Статус документа `"failed"` — файл не создан |

### 2.5. GET /api/providers — Статус провайдеров

**Request**

```
GET /api/providers
```

**Успешный ответ (200 OK)**

```json
{
  "providers": [
    {
      "id": "ollama",
      "name": "Ollama (локальный)",
      "available": false,
      "model": "qwen2.5:7b",
      "error": "Ollama service not running on localhost:11434"
    },
    {
      "id": "groq",
      "name": "Groq Cloud",
      "available": true,
      "model": "llama-3.3-70b-versatile",
      "error": null
    },
    {
      "id": "yandexgpt",
      "name": "YandexGPT",
      "available": true,
      "model": "yandexgpt/5-pro",
      "error": null
    }
  ]
}
```

**Детали**

- `id` — строковый идентификатор для поля `provider` в запросе генерации
- `available` — результат health-check на момент запроса
- `model` — название используемой модели (из конфига)
- `error` — описание ошибки, если провайдер недоступен (null при доступности)

> **Примечание**: Этот эндпоинт не требует авторизации и должен отвечать быстро (< 1 сек). Для проверки каждого провайдера используется лёгкий health-check (см. раздел 3.3), кешированный на 30–60 секунд.

---

## 3. Архитектура LLM-провайдеров

### 3.1. Диаграмма классов (описание)

```
                ┌──────────────────────┐
                │   BaseLLMProvider    │ (abc.ABC)
                ├──────────────────────┤
                │ + name: str          │
                │ + model: str         │
                │ + generate() -> str  │
                │ + health_check() -> bool
                └──────────┬───────────┘
                           │
          ┌────────────────┼────────────────┐
          │                │                │
   ┌──────┴──────┐  ┌─────┴──────┐  ┌──────┴──────┐
   │ GroqProvider│  │YandexGPT   │  │OllamaProvider│
   │             │  │Provider    │  │             │
   ├─────────────┤  ├────────────┤  ├─────────────┤
   │ api_key     │  │ api_key    │  │ base_url    │
   │ base_url    │  │ folder_id  │  │ model       │
   │ model       │  │ model      │  │             │
   │ timeout=60  │  │ timeout=60 │  │ timeout=60  │
   └─────────────┘  └────────────┘  └─────────────┘


   ┌─────────────────────────────────────┐
   │        ProviderSelector             │
   ├─────────────────────────────────────┤
   │ providers: List[BaseLLMProvider]    │
   ├─────────────────────────────────────┤
   │ + select(topic, preference)         │
   │   -> BaseLLMProvider                │
   │ + refresh_health()                  │
   │ + list_available()                  │
   └─────────────────────────────────────┘
```

### 3.2. Контракт BaseLLMProvider

```python
class BaseLLMProvider(ABC):
    """Абстрактный базовый класс для всех LLM-провайдеров."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Человекочитаемое имя провайдера (например, 'groq')."""
        ...

    @property
    @abstractmethod
    def model(self) -> str:
        """Идентификатор модели (например, 'llama-3.3-70b-versatile')."""
        ...

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 8192,
    ) -> str:
        """
        Отправить запрос к LLM и получить ответ.

        Args:
            prompt: Пользовательский промпт (тема регламента).
            system_prompt: Системный промпт (инструкция для LLM).
            temperature: Температура генерации (по умолч. 0.7).
            max_tokens: Максимум токенов в ответе.

        Returns:
            Сырой текст ответа от LLM.

        Raises:
            ProviderTimeoutError: Таймаут запроса (>60 сек).
            ProviderAuthError: Ошибка аутентификации (ключ/project_id).
            ProviderRateLimitError: Превышен лимит запросов.
            ProviderUnavailableError: Сервис недоступен (5xx).
            ProviderError: Любая другая ошибка провайдера.
        """
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        """
        Проверить доступность провайдера.

        Для Groq/YandexGPT — лёгкий запрос к API (GET /models или эквивалент).
        Для Ollama — запрос к /api/tags.

        Returns:
            True если провайдер доступен, иначе False.
        """
        ...
```

### 3.3. Health-check для каждого провайдера

| Провайдер | Метод проверки | URL | Ожидаемый код |
|---|---|---|---|
| **Ollama** | GET `/api/tags` | `http://localhost:11434/api/tags` | 200 + наличие модели в списке |
| **Groq** | GET `https://api.groq.com/openai/v1/models` | `https://api.groq.com/openai/v1/models` | 200 (с API-ключом в заголовке) |
| **YandexGPT** | POST `https://llm.api.cloud.yandex.net/llm/v1/models` | см. документацию Yandex Cloud | 200 (с IAM-токеном) |

**Кеширование health-check**: результаты health-check кешируются в памяти на 30 секунд, чтобы избежать лишних запросов при вызове `GET /api/providers`.

### 3.4. Механизм Fallback (ProviderSelector)

**Логика режима `"auto"`:**

```
ВХОД: topic (строка), preference (None)

1. Получить health-статусы всех провайдеров (с кешем 30 сек).

2. Проверить УМНЫЕ ПРАВИЛА:
   А) Если topic содержит юр. маркеры:
        список: ["ПДн", "152-ФЗ", "коммерческая тайна", "персональные данные",
                 "персональных данных", "GDPR", " confidentiality", "trade secret",
                 "персональным данным", "Защита персональных", "О персональных",
                 "ФЗ-152", "152-ФЗ", "ПДн", "персональных"]
        → если YandexGPT здоров → приоритет YandexGPT
        → иначе → следующий шаг

   Б) Если длина topic > 50 слов (сложный запрос):
        → если YandexGPT здоров → приоритет YandexGPT
        → иначе → следующий шаг

   В) ИНАЧЕ (обычный запрос):
        → цепочка: Ollama > Groq > YandexGPT
        → первый здоровый возвращается

3. Если в результате выбранный провайдер при generate() упал с ошибкой:
   → переключиться на следующего здорового из цепочки (до 1 раза)
   → если все перепробованы → вернуть ошибку 503

4. Если ни один провайдер не здоров в начале → 503.
```

**При ручном выборе (`"groq"`, `"yandexgpt"`, `"ollama"`):**
- Если указанный провайдер здоров → использовать его.
- Если не здоров → 503 с сообщением, какой провайдер недоступен.
- Fallback НЕ применяется при ручном выборе.

**ProviderSelector API:**

```python
class ProviderSelector:
    def __init__(self, providers: list[BaseLLMProvider]):
        self._providers = providers
        self._health_cache: dict[str, HealthResult] = {}
        self._cache_ttl = 30  # секунд

    async def select(
        self,
        topic: str,
        preference: str = "auto"
    ) -> BaseLLMProvider:
        """Выбрать провайдера согласно preference и topic."""

    async def refresh_health(self) -> None:
        """Принудительно обновить health-кеш."""

    def list_providers_with_status(self) -> list[ProviderStatus]:
        """Вернуть статусы всех провайдеров для GET /api/providers."""
```

### 3.5. Обработка ошибок провайдеров

| Ситуация | Исключение | HTTP код | Действие BE |
|---|---|---|---|
| Таймаут > 60 сек | `ProviderTimeoutError` | 503 | Попробовать fallback (auto), иначе 503 |
| Неверный API-ключ | `ProviderAuthError` | 503 | Записать в лог, пометить провайдера unhealthy |
| Rate limit (429) | `ProviderRateLimitError` | 503 | Пометить провайдера unhealthy на 60 сек |
| Сервис недоступен (5xx) | `ProviderUnavailableError` | 503 | Попробовать fallback (auto), иначе 503 |
| Пустой ответ от LLM | `ProviderError` | 500 | Логировать, вернуть 500 |

**Retry-политика:**
- При ошибках провайдера (таймаут, 5xx): **1 повтор** через 2 секунды (только в auto mode, при переключении на другой провайдер).
- При ошибках аутентификации (401): **без повтора**, провайдер помечается unhealthy до перезапуска сервиса.

### 3.6. Конфигурация провайдеров (config.py)

```python
# .env / config
GROQ_API_KEY=...
YANDEXGPT_API_KEY=...
YANDEXGPT_FOLDER_ID=...
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5:7b

# Настройки провайдеров по умолчанию
GROQ_MODEL=llama-3.3-70b-versatile   # или qwen3-32b
YANDEXGPT_MODEL=yandexgpt/5-pro
PROVIDER_TIMEOUT=60  # секунд
```

---

## 4. Схема БД

### 4.1. Таблица `documents`

```sql
CREATE TABLE IF NOT EXISTS documents (
    id              TEXT PRIMARY KEY,           -- UUID v4
    topic           TEXT NOT NULL,              -- Тема регламента (от пользователя)
    provider_used   TEXT NOT NULL,              -- 'groq', 'yandexgpt', 'ollama'
    prompt          TEXT NOT NULL,              -- Финальный промпт, отправленный в LLM
    raw_response    TEXT,                       -- Сырой ответ от LLM (JSON/markdown)
    docx_path       TEXT,                       -- Относительный путь к .docx файлу
    status          TEXT NOT NULL DEFAULT 'completed'  -- 'completed', 'failed'
                        CHECK(status IN ('completed', 'failed')),
    error_message   TEXT,                       -- Текст ошибки, если status = 'failed'
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))  -- ISO 8601
);

CREATE INDEX IF NOT EXISTS idx_documents_created_at
    ON documents(created_at DESC);
```

### 4.2. Описание колонок

| Колонка | Тип | Ограничения | Назначение |
|---|---|---|---|
| `id` | TEXT | PK, UUID v4 | Первичный ключ, генерируется на backend через `uuid.uuid4()` |
| `topic` | TEXT | NOT NULL | Исходный запрос пользователя (тема) |
| `provider_used` | TEXT | NOT NULL | Фактический провайдер, сгенерировавший документ |
| `prompt` | TEXT | NOT NULL | Полный промпт (system + user), отправленный провайдеру (для отладки) |
| `raw_response` | TEXT | nullable | Ответ LLM в сыром виде (markdown/json) — для отладки и регенерации |
| `docx_path` | TEXT | nullable | Путь к .docx относительно корня проекта: `generated/{uuid}.docx` |
| `status` | TEXT | DEFAULT 'completed', CHECK | Статус генерации |
| `error_message` | TEXT | nullable | При status='failed' — описание ошибки |
| `created_at` | TEXT | DEFAULT datetime('now') | Время создания записи |

### 4.3. SQLAlchemy model (для справки)

Таблица маппится в SQLAlchemy модель `Document`:
- ORM-модель в `app/models/document.py`
- Pydantic-схемы (request/response) в `app/schemas/document.py`

---

## 5. Структура промптов

### 5.1. Системный промпт (полный текст)

```
Ты — эксперт по корпоративным регламентам и нормативной документации.
Твоя задача — составить документ регламента на русском языке по указанной теме.

Документ должен быть структурирован, написан официально-деловым стилем,
содержать конкретные пункты и инструкции.

Формат ответа — строгая структура с маркерами разделов в markdown:

# Название документа

## 1. Общие положения
- Цель документа
- Область применения
- Нормативные ссылки (если применимо)

## 2. Термины и определения
(только если в теме есть специфические термины; иначе этот раздел опускается)
- Термин 1 — определение
- Термин 2 — определение

## 3. [Основная часть — разделы по теме]
Используй подразделы ### 3.1, ### 3.2 и т.д.
Где необходимо — нумерованные списки (1. 2. 3.) или маркированные списки (-).
Если уместны таблицы — используй markdown-таблицы.

## 4. Заключительные положения
- Порядок вступления в силу
- Ответственность за соблюдение
- Порядок внесения изменений
- Дата введения

## 5. Приложения
(если применимо; иначе этот раздел опускается)

ВАЖНЫЕ ТРЕБОВАНИЯ:
1. Весь документ на русском языке.
2. Не выдумывай конкретные номера приказов/ФЗ, если они не указаны в запросе.
3. Если нужны таблицы — используй синтаксис markdown-таблиц.
4. Для вложенных списков используй отступы в 2 пробела.
5. В конце документа добавь строку: ---\n\n*Документ сгенерирован автоматически, {текущая дата}*
```

### 5.2. Пользовательский промпт

```
Составь регламент на тему: "{topic}"

Учти следующие детали (если они применимы к теме):
- Процессы и процедуры
- Ответственные лица/должности
- Сроки выполнения
- Формы документов и отчётности
- Критерии контроля
```

### 5.3. Формат ответа от LLM (для парсинга)

Ожидаемый ответ — markdown со следующей структурой:

```
# Название документа

## 1. Общие положения
...

## 2. Термины и определения
...

## 3.1 Название подраздела
...

### 3.1.1 Подподраздел (опционально)
...

## 4. Заключительные положения
...

## 5. Приложения
...

---
*Документ сгенерирован автоматически, 30.06.2026*
```

**Парсинг в docx:**
- `# ` → Заголовок документа (docx: Heading 1, 18pt, bold)
- `## ` → Раздел (docx: Heading 2, 16pt, bold)
- `### ` → Подраздел (docx: Heading 3, 14pt, bold)
- `#### ` → Подподраздел (docx: Heading 4, 14pt, italic)
- `- ` или `* ` → Маркированный список
- `1. `, `2. ` → Нумерованный список
- `| ... | ... |` → Таблица (pipe-синтаксис)
- Обычный текст → параграф (Times New Roman, 14pt, interline 1.5)
- `---` → разделитель (игнорируется)
- `*Текст*` → курсив
- `**Текст**` → жирный

### 5.4. Prompt-шаблоны по типам (опционально, Stage 2+)

Можно расширить для разных типов регламентов:

| Тип | Модификация системного промпта |
|---|---|
| **Кадровый** | Добавить секции: порядок ознакомления, хранение документов |
| **Технический** | Добавить секции: требования безопасности, оборудование |
| **Финансовый** | Добавить секции: лимиты, отчётность, контроль |

> В MVP используется один универсальный системный промпт.

---

## 6. Модульная структура backend

```
backend/
├── app/
│   ├── __init__.py
│   │
│   ├── main.py                   # FastAPI app, lifespan, CORS, router include
│   ├── config.py                 # Pydantic Settings (.env loading)
│   ├── database.py               # SQLite engine, sessionmaker, get_db dependency
│   │
│   ├── api/
│   │   ├── __init__.py
│   │   └── routes.py             # Все эндпоинты: /api/generate, /api/documents, /api/providers
│   │
│   ├── models/
│   │   ├── __init__.py
│   │   └── document.py           # SQLAlchemy Document model
│   │
│   ├── schemas/
│   │   ├── __init__.py
│   │   └── document.py           # Pydantic: GenerateRequest, DocumentResponse, etc.
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   ├── generator.py          # Orchestrator: выбор провайдера → генерация → парсинг → docx → БД
│   │   └── docx_builder.py       # Парсинг markdown-ответа → python-docx Document
│   │
│   └── providers/
│       ├── __init__.py
│       ├── base.py               # BaseLLMProvider (abstract)
│       ├── groq.py               # GroqProvider
│       ├── yandexgpt.py          # YandexGPTProvider
│       ├── ollama.py             # OllamaProvider
│       └── selector.py           # ProviderSelector (auto mode)
│
├── generated/                    # Сгенерированные .docx (создаётся при первом запуске)
├── data/                         # SQLite БД (создаётся при первом запуске)
│
├── .env                          # Не в git
├── .env.example                  # Шаблон настроек
├── requirements.txt              # Зависимости
└── alembic/                      # (Опционально, для будущих миграций)
```

### 6.1. Описание ключевых модулей

| Модуль | Ответственность |
|---|---|
| `config.py` | Pydantic `BaseSettings`, загрузка из `.env`, валидация |
| `database.py` | `create_engine`, `sessionmaker`, `Base`, `get_db` |
| `api/routes.py` | Эндпоинты, Dependency Injection, вызов `generator` |
| `services/generator.py` | 1) Выбрать провайдера (ручной или auto); 2) Сформировать промпт; 3) Вызвать generate(); 4) Передать ответ в docx_builder; 5) Сохранить в БД; 6) Вернуть результат |
| `services/docx_builder.py` | Парсинг markdown → python-docx; форматирование; сохранение в `generated/{uuid}.docx` |
| `providers/selector.py` | ProviderSelector: кешированный health-check, auto-логика, fallback |

### 6.2. Зависимости (requirements.txt)

```
fastapi>=0.115.0
uvicorn[standard]>=0.32.0
sqlalchemy>=2.0.36
pydantic>=2.10.0
pydantic-settings>=2.6.0
python-docx>=1.1.2
httpx>=0.28.0
python-multipart>=0.0.12
```

---

## 7. Модульная структура frontend

```
frontend/
├── src/
│   ├── main.tsx                  # ReactDOM.createRoot, App
│   ├── App.tsx                   # Разметка страницы: форма + результат + история
│   ├── App.css                   # Минимальные стили
│   │
│   ├── api/
│   │   └── client.ts             # Функции: generateDocument(), getDocuments(), getDocument(), downloadDocument(), getProviders()
│   │
│   ├── components/
│   │   ├── GeneratorForm.tsx      # Textarea + RadioGroup (провайдер) + Submit button
│   │   ├── ResultPanel.tsx        # Уведомление + кнопка скачать + кнопка "Создать ещё"
│   │   └── HistoryList.tsx        # Таблица/список последних 20 генераций
│   │
│   └── types.ts                  # TypeScript: DocumentItem, ProviderStatus, GenerateRequest, GenerateResponse
│
├── index.html
├── package.json
├── tsconfig.json
├── vite.config.ts
└── public/
    └── favicon.svg
```

### 7.1. TypeScript types (types.ts)

```typescript
export type ProviderId = 'auto' | 'groq' | 'yandexgpt' | 'ollama';

export interface GenerateRequest {
  topic: string;
  provider?: ProviderId;
}

export interface DocumentItem {
  id: string;
  topic: string;
  provider_used: string;
  status: 'completed' | 'failed';
  created_at: string;
}

export interface DocumentDetail extends DocumentItem {
  prompt: string;
  error_message: string | null;
}

export interface DocumentListResponse {
  items: DocumentItem[];
  total: number;
}

export interface GenerateResponse {
  id: string;
  topic: string;
  filename: string;
  provider_used: string;
  status: 'completed' | 'failed';
  created_at: string;
}

export interface ProviderStatus {
  id: ProviderId;
  name: string;
  available: boolean;
  model: string | null;
  error: string | null;
}

export interface ProvidersResponse {
  providers: ProviderStatus[];
}
```

### 7.2. API client (client.ts)

| Функция | Метод | URL | Параметры |
|---|---|---|---|
| `generateDocument(req: GenerateRequest)` | POST | `/api/generate` | body |
| `getDocuments(limit?, offset?)` | GET | `/api/documents` | query |
| `getDocument(id: string)` | GET | `/api/documents/{id}` | path |
| `downloadDocument(id: string)` | GET | `/api/documents/{id}/download` | path (blob) |
| `getProviders()` | GET | `/api/providers` | — |

### 7.3. Компоненты (описание)

**GeneratorForm.tsx:**
- Textarea (placeholder: "Опишите тему регламента...", rows=5, maxLength=2000)
- Radio Group: Авто (по умолчанию), Groq, YandexGPT, Ollama
- Кнопка "Сгенерировать" (disabled при пустом поле / loading)
- Состояние: loading, error
- При успехе: вызывает callback `onGenerated(id: string)`
- Валидация: topic не пустой, не длиннее 2000 символов

**ResultPanel.tsx:**
- Показывается после успешной генерации
- Уведомление: "Регламент '{topic}' успешно создан!"
- Кнопка "Скачать .docx" → вызывает `downloadDocument(id)`
- Кнопка "Создать ещё" → очищает форму, возвращает к GeneratorForm
- Если status='failed': показать ошибку

**HistoryList.tsx:**
- Загружает список при монтировании через `getDocuments(20)`
- Таблица: Тема, Провайдер, Дата, Статус, Скачать (иконка/кнопка)
- Клик по строке → открыть детали (опционально)
- Автообновление после генерации нового документа

---

## 8. План реализации по Stage

### Stage 1: Backend Core

**Цель**: Функциональный backend с одним провайдером (Groq), генерацией .docx и API.

**Что входит:**
1. Инициализация проекта: структура папок, `.env.example`, `requirements.txt`
2. `config.py` — загрузка настроек
3. `database.py` — SQLite engine + создание таблицы
4. `models/document.py` — SQLAlchemy Document model
5. `schemas/document.py` — Pydantic схемы (request/response)
6. `providers/base.py` — BaseLLMProvider (абстрактный)
7. `providers/groq.py` — GroqProvider (через OpenAI-compatible API)
8. `services/docx_builder.py` — парсинг markdown в .docx
9. `services/generator.py` — оркестратор (пока без auto-select, просто вызывает переданный провайдер)
10. `api/routes.py` — все 5 эндпоинтов (POST /api/generate, GET /api/documents, GET /api/documents/{id}, GET /api/documents/{id}/download, GET /api/providers)
11. `main.py` — FastAPI app + CORS
12. Создание `generated/` и `data/` директорий

**Файлы для создания:**
- `backend/app/__init__.py`
- `backend/app/main.py`
- `backend/app/config.py`
- `backend/app/database.py`
- `backend/app/api/__init__.py`
- `backend/app/api/routes.py`
- `backend/app/models/__init__.py`
- `backend/app/models/document.py`
- `backend/app/schemas/__init__.py`
- `backend/app/schemas/document.py`
- `backend/app/services/__init__.py`
- `backend/app/services/generator.py`
- `backend/app/services/docx_builder.py`
- `backend/app/providers/__init__.py`
- `backend/app/providers/base.py`
- `backend/app/providers/groq.py`
- `backend/requirements.txt`
- `backend/.env.example`

**Acceptance Criteria:**
1. `POST /api/generate` с `provider: "groq"` генерирует документ и возвращает 201
2. Сгенерированный .docx можно скачать через `GET /api/documents/{id}/download`
3. Файл .docx открывается в Word: заголовок, разделы, списки, таблицы, Times New Roman
4. `GET /api/documents` возвращает список (пустой до первой генерации)
5. `GET /api/providers` возвращает статусы всех провайдеров (Groq — checked, остальные — unchecked с ошибкой)
6. Все записи сохраняются в БД SQLite
7. Валидация: пустой topic → 422, topic > 2000 → 422, неверный provider → 422

**Что НЕ входит (out of scope Stage 1):**
- YandexGPTProvider, OllamaProvider
- ProviderSelector (auto mode) — только ручной выбор `"groq"`
- Обработка ошибок с fallback (только базовая: таймаут → 503)
- Prompt-шаблоны по типам
- Alembic миграции

---

### Stage 2: All Providers + Auto-select

**Цель**: Добавить YandexGPT и Ollama, реализовать ProviderSelector, fallback, обработку ошибок.

**Что входит:**
1. `providers/yandexgpt.py` — YandexGPTProvider (YandexGPT API)
2. `providers/ollama.py` — OllamaProvider (локальный Ollama API)
3. `providers/selector.py` — ProviderSelector с:
   - Кешированным health-check (30 сек)
   - Логикой "auto" (юр. маркеры → YandexGPT, >50 слов → YandexGPT, иначе цепочка Ollama>Groq>YandexGPT)
   - Механизмом fallback при ошибке генерации (1 попытка переключения)
4. Обновление `config.py` — добавить настройки YandexGPT и Ollama
5. Обновление `schemas/document.py` — при необходимости расширить ошибки
6. Обновление `services/generator.py` — интеграция с ProviderSelector
7. Обновление `api/routes.py` — проверка, что POST /api/generate обрабатывает auto mode
8. Обработка ошибок провайдеров (timeout, rate limit, auth error) с разными HTTP-кодами

**Файлы для создания:**
- `backend/app/providers/yandexgpt.py`
- `backend/app/providers/ollama.py`
- `backend/app/providers/selector.py`

**Файлы для изменения:**
- `backend/app/config.py`
- `backend/app/services/generator.py`
- `backend/app/api/routes.py`
- `backend/app/main.py` (подключение провайдеров при старте)

**Acceptance Criteria:**
1. Все три провайдера работают при ручном выборе
2. `provider: "auto"` корректно выбирает провайдера по правилам:
   - Ollama запущен → выбирается Ollama
   - Ollama не запущен, Groq отвечает → Groq
   - Ollama и Groq не отвечают, YandexGPT отвечает → YandexGPT
3. При наличии юр. маркеров в теме → YandexGPT (если доступен)
4. При длинном запросе (>50 слов) → YandexGPT (если доступен)
5. При падении выбранного провайдера (auto) → fallback на другого
6. GET /api/providers показывает реальный статус каждого (available/unavailable)
7. При ручном выборе недоступного провайдера → 503 с понятным сообщением
8. Таймаут 60 сек: запрос дольше 60 сек возвращает 503

**Что НЕ входит (out of scope Stage 2):**
- Frontend
- Prompt-шаблоны по типам
- Асинхронная очередь (Celery/Background Tasks)
- Docker-контейнеризация

---

### Stage 3: Frontend

**Цель**: React-приложение с формой генерации, результатом и историей.

**Что входит:**
1. Инициализация Vite + React + TypeScript
2. `types.ts` — все TypeScript типы
3. `api/client.ts` — функции вызовов к backend
4. `components/GeneratorForm.tsx` — форма
5. `components/ResultPanel.tsx` — результат
6. `components/HistoryList.tsx` — история
7. `App.tsx` — сборка компонентов, состояние
8. `App.css` — минимальные стили
9. `vite.config.ts` — proxy для /api → backend
10. Кросс-проверка CORS/public

**Файлы для создания:**
- `frontend/package.json`
- `frontend/tsconfig.json`
- `frontend/tsconfig.node.json` (или app)
- `frontend/vite.config.ts`
- `frontend/index.html`
- `frontend/src/main.tsx`
- `frontend/src/App.tsx`
- `frontend/src/App.css`
- `frontend/src/types.ts`
- `frontend/src/api/client.ts`
- `frontend/src/components/GeneratorForm.tsx`
- `frontend/src/components/ResultPanel.tsx`
- `frontend/src/components/HistoryList.tsx`
- `frontend/public/favicon.svg`

**Acceptance Criteria:**
1. Пользователь может ввести тему, выбрать провайдера (по умолчанию "Авто"), нажать "Сгенерировать"
2. После генерации: уведомление об успехе + кнопка скачать + кнопка "Создать ещё"
3. История показывает последние 20 генераций (тема, провайдер, дата, кнопка скачать)
4. После новой генерации история обновляется
5. Скачанный .docx открывается и читается
6. Страница адаптивна (min-width 320px)
7. Валидация: кнопка неактивна при пустом поле
8. Обработка ошибок: уведомление при 422 / 503 / 500

**Что НЕ входит (out of scope Stage 3):**
- Авторизация/регистрация
- Темы оформления (только минимальный CSS)
- E2E-тесты
- Развёртывание (Docker, деплой)

---

## 9. Edge Cases, Risks, Open Questions

### 9.1. Edge Cases

| Ситуация | Ожидаемое поведение |
|---|---|
| **topic = пустая строка** | 422 Validation Error |
| **topic > 2000 символов** | 422 Validation Error |
| **topic = только пробелы** | 422 (trim перед валидацией не требуется — backend сам trim'ит) |
| **provider = неизвестное значение** | 422 |
| **Все провайдеры недоступны** | POST /api/generate → 503; GET /api/providers → все `available: false` |
| **.doc файл удалён с диска** | GET /api/documents/{id}/download → 404 |
| **Очень длинный ответ LLM (> 100 000 токенов)** | Обрезать по max_tokens, но по умолчанию 8192 |
| **LLM вернул невалидный markdown** | docx_builder должен обработать частичный парсинг без падения |
| **Два одновременных запроса** | Serialised через блокировку на уровне генерации (gIL для одного пользователя не критично); но лучше через asyncio lock |
| **SQLite Concurrent Writes** | Для одного пользователя неактуально; WAL mode для профилактики |
| **Спецсимволы в теме (XSS, SQL injection)** | SQLAlchemy parameterized queries; Pydantic валидация; .docx название — только латиница |

### 9.2. Риски и митигации

| Риск | Вероятность | Влияние | Митигация |
|---|---|---|---|
| **Ollama потребляет >4GB VRAM на RTX 3050** | Средняя | Высокая | Использовать Qwen2.5-7B Q4_K_M (~5GB RAM, ~4GB VRAM). Если не хватает — переключиться на 3B модель. |
| **YandexGPT free tier (1M токенов/мес) исчерпан** | Низкая (для личного использования) | Средняя | ProviderSelector должен проверять статус и не выбирать YandexGPT если он недоступен (по health-check). |
| **Groq API rate limit на бесплатном tier** | Средняя | Средняя | Fallback на другого провайдера; кеширование unhealthy на 60 сек. |
| **Большой объём .docx (>10MB)** | Низкая | Средняя | Ограничение max_tokens=8192; если превышен — обрезать. |
| **Долгая генерация > 60 сек** | Средняя | Средняя | Таймаут 60 сек; fallback на другого провайдера; пользователю — понятное сообщение. |

### 9.3. Открытые вопросы (для PM)

| Вопрос | Варианты | Предложение SA |
|---|---|---|
| Нужна ли поддержка английского языка? | 1) Только русский; 2) Детект языка; 3) Выбор языка в UI | Только русский в MVP |
| Нужна ли кастомная модель в Ollama (не Qwen2.5)? | 1) Конфигурируется через .env; 2) Жёстко зашита | Через .env (`OLLAMA_MODEL`) — уже в спецификации |
| Нужна ли асинхронная генерация (подождать, потом скачать)? | 1) Синхронно; 2) Async с polling | Синхронно в MVP. Async — Stage 4 |
| Нужен ли полноценный титульник в .docx? | 1) Нет (только заголовок); 2) Да, с полями | Нет в MVP |
| Нужна ли пагинация в истории (больше 20)? | 1) Да, offset пагинация; 2) Только последние 20 | Offset пагинация уже в API, но UI показывает 20 |

---

## Приложение A: Последовательность генерации (sequence diagram, текстовый)

```
User                  Frontend               Backend                  LLM Provider
 │                       │                       │                        │
 │ Ввод темы + выбор     │                       │                        │
 │ провайдера            │                       │                        │
 │──────────────────────>│                       │                        │
 │                       │                       │                        │
 │                       │ POST /api/generate    │                        │
 │                       │──────────────────────>│                        │
 │                       │                       │                        │
 │                       │                       │  ProviderSelector:     │
 │                       │                       │  select(topic, pref)   │
 │                       │                       │  health-check chain    │
 │                       │                       │       │                │
 │                       │                       │       │ (healthy)      │
 │                       │                       │       ▼                │
 │                       │                       │  Provider.generate()  │
 │                       │                       │───────────────────────>│
 │                       │                       │                        │
 │                       │                       │  ←── raw_response ─────│
 │                       │                       │                        │
 │                       │                       │  docx_builder.build()  │
 │                       │                       │  save to generated/    │
 │                       │                       │  save to DB            │
 │                       │                       │                        │
 │                       │  ←── 201 {id, ...} ───│                        │
 │                       │                       │                        │
 │  ←── response ────────│                       │                        │
 │                       │                       │                        │
 │  Нажимает "Скачать"   │                       │                        │
 │──────────────────────>│                       │                        │
 │                       │ GET /documents/{id}/download                    │
 │                       │──────────────────────>│                        │
 │                       │                       │  return file           │
 │                       │  ←── .docx blob ──────│                        │
 │  ←── download ────────│                       │                        │
```

---

## Приложение B: Глоссарий

| Термин | Определение |
|---|---|
| **SRP** | Service for Regulations and Policies |
| **Provider** | AI-сервис, который генерирует текст (Groq, YandexGPT, Ollama) |
| **Health-check** | Проверка доступности провайдера (лёгкий запрос к API) |
| **Fallback** | Переключение на другого провайдера при недоступности основного |
| **docx_builder** | Модуль, преобразующий markdown-ответ LLM в .docx файл |
| **ProviderSelector** | Модуль, реализующий автоматический выбор провайдера |
| **topic** | Тема регламента, введённая пользователем |
| **prompt** | Полный запрос (system + user), отправленный в LLM |

---

*Документ подготовлен: SA, 30.06.2026*
*Статус: готов к передаче BE и FE*
