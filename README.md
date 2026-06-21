# SRP — Service for Regulations and Policies

Сервис для создания, управления и генерации корпоративных регламентов и политик для компаний.

## Возможности

- **Загрузка и парсинг документов** — Word (.docx) и PDF с извлечением структуры, таблиц, терминов
- **RAG-индексация** — утверждённые документы автоматически индексируются в векторное хранилище (ChromaDB)
- **Поиск в интернете** — генератор учитывает актуальные нормативные требования через DuckDuckGo (бесплатно)
- **Версионность** — полная история изменений с сравнением версий
- **Генератор документов** — создание регламентов через Ollama (локальная LLM) с учётом:
  - Профиля компании
  - Утверждённых документов (RAG)
  - Черновиков пользователя
  - Результатов интернет-поиска
- **Мультитенантность** — поддержка множества компаний с изолированными данными
- **Passwordless auth** — вход по email-коду, JWT + httpOnly cookies

## Технологический стек

| Компонент | Технология |
|-----------|-----------|
| Frontend | React 18+ / Vite / TypeScript / Ant Design 5 / Zustand |
| Backend | Python 3.11+ / FastAPI / SQLAlchemy async / Alembic |
| Database | SQLite (dev) / PostgreSQL 16 (prod) |
| Storage | Local filesystem / S3 (MinIO) |
| Cache | In-memory / Redis |
| Vector DB | ChromaDB (persistent, встраивается в Python-процесс) |
| LLM | Ollama (локально, `qwen2.5:7b` + `nomic-embed-text`) |
| Web Search | DuckDuckGo (free) / Tavily / SerpAPI (опционально) |
| Email | Console (dev) / SMTP (MailHog) |
| Auth | Passwordless email-code + JWT (access + refresh httpOnly cookie) |

## Быстрый старт

### Предварительные требования

1. Установите [Ollama](https://ollama.com/) и запустите:
   ```bash
   ollama pull qwen2.5:7b    # Модель для генерации
   ollama pull nomic-embed-text  # Модель для эмбеддингов RAG
   ```

2. Убедитесь, что Ollama работает: `http://localhost:11434`

### Локальная разработка

```bash
# Backend
cd backend
pip install -r requirements.txt
cp .env.example .env        # Настройте при необходимости
alembic upgrade head
python -m app.seed
uvicorn app.main:app --reload

# Frontend (в другом терминале)
cd frontend
npm install
npm run dev
```

### Production-стек (Docker)

```bash
docker compose -f docker-compose.dev.yml up -d
```

## Структура проекта

```
├── backend/           # Python FastAPI backend
│   ├── app/
│   │   ├── api/       # API endpoints (v1 router)
│   │   ├── core/      # Security, rate limiter
│   │   ├── models/    # SQLAlchemy models
│   │   ├── parsers/   # Document parsers (Word, PDF)
│   │   ├── schemas/   # Pydantic schemas
│   │   ├── services/  # Business logic + RAG + Web Search
│   │   ├── storage/   # Storage abstraction (Local / S3)
│   │   └── generators/# LLM integration & response handling
│   ├── alembic/       # Database migrations
│   └── tests/         # 200+ tests
├── frontend/          # React SPA
│   └── src/
│       ├── api/       # API client services
│       ├── components/# Shared components
│       ├── pages/     # Page components
│       ├── store/     # Zustand stores
│       └── mocks/     # MSW mock handlers
├── docs/              # Documentation
└── docker-compose.yml # Infrastructure services
```

## Тесты

```bash
cd backend
pytest -v --tb=short   # 200+ тестов, SQLite in-memory, без внешних сервисов
```

Для тестов с PostgreSQL:
```bash
TEST_DATABASE_URL=postgresql+asyncpg://user:pass@localhost/db pytest -v --tb=short
```

## CI/CD

Проект использует GitHub Actions (см. `.github/workflows/ci.yml`):
- **Backend**: Python 3.11, `pip install` → `pytest`
- **Frontend**: Node 20, `npm ci` → `npm run typecheck` → `npm run build`

## Архитектура RAG

1. Документ загружается → парсится → сохраняется
2. При статусе "Утверждён" → автоматическая индексация в ChromaDB
3. При генерации документа:
   - Извлекаются релевантные фрагменты из утверждённых документов (RAG)
   - Выполняется поиск в интернете по теме документа
   - Всё добавляется в контекст промпта LLM
4. LLM (Ollama) генерирует документ на основе: черновиков + RAG-контекста + результатов поиска
