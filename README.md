# SRP — Service for Regulations and Policies

Сервис для создания, управления и генерации корпоративных регламентов и политик для холдингов.

## Возможности

- **Загрузка и парсинг документов** — Word (.docx) и PDF с извлечением структуры, таблиц, терминов
- **Граф влияний** — визуальная карта связей между документами и приказами
- **Версионность** — полная история изменений с сравнением версий (diff)
- **Генератор документов** — создание регламентов через GigaChat Pro с учётом профиля холдинга
- **Законодательство** — поиск по pravo.gov.ru, docs.cntd.ru, конструктор собственных источников
- **Мультитенантность** — поддержка множества холдингов с изолированными данными
- **Passwordless auth** — вход по email-коду, JWT + httpOnly cookies

## Технологический стек

| Компонент | Технология |
|-----------|-----------|
| Frontend | React 18+ / Vite / TypeScript / Ant Design 5 / Zustand / Cytoscape |
| Backend | Python 3.11+ / FastAPI / SQLAlchemy async / Alembic |
| Database | SQLite (dev) / PostgreSQL 16 (prod) |
| Storage | Local filesystem / S3 (MinIO) |
| Cache | In-memory / Redis |
| LLM | GigaChat Pro (с mock-режимом для разработки) |
| Email | Console (dev) / SMTP (MailHog) |
| Auth | Passwordless email-code + JWT (access + refresh httpOnly cookie) |

## Быстрый старт

### Локальная разработка

```bash
# Backend
cd backend
pip install -r requirements.txt
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
│   │   ├── parsers/   # Document parsers (Word, PDF, enhanced PDF)
│   │   ├── schemas/   # Pydantic schemas
│   │   ├── services/  # Business logic
│   │   ├── storage/   # Storage abstraction (Local / S3)
│   │   └── legislation/ # Legislation adapters
│   ├── alembic/       # Database migrations
│   └── tests/         # 190+ tests
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
pytest -x -q    # 190+ тестов, SQLite in-memory
```

Для тестов с PostgreSQL:
```bash
TEST_DATABASE_URL=postgresql+asyncpg://user:pass@localhost/db pytest -x -q
```
