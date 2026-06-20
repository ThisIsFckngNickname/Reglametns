# Stage Definition: Stage 1 / Increment A

## Name
Scaffolding + Аутентификация + Управление холдингами

## Goal
Пользователь может зарегистрироваться по email, войти в систему, создать/выбрать холдинг и увидеть пустой дашборд.

## Business value
- Фиксируется мультитенантная архитектура: каждый пользователь привязан к холдингу
- Создан foundation для всех последующих инкрементов (БД, API, UI, авторизация)
- Модель безопасности закладывается с первого дня

## Scope
### Backend (Python / FastAPI)
1. Инициализация FastAPI-проекта (структура папок, uv/poetry, зависимости)
2. SQLAlchemy модели + Alembic миграции
3. Auth endpoints: register, verify, login, refresh
4. JWT-логика (generate, validate, middleware)
5. Holdings CRUD endpoints (admin-only create/update, list для всех)
6. User profile endpoints (get profile, set active holding)
7. Email-заглушка (логгер + in-memory storage для кодов)

### Frontend (React 18+ / Vite / TypeScript / Ant Design 5)
1. Инициализация проекта (Vite + React + TS + Ant Design 5)
2. OpenAPI-генератор клиента (openapi-typescript-codegen)
3. Auth pages: /login, /register, /verify
4. ProtectedRoute component (redirect to /login)
5. /profile — выбор холдинга из дропдауна с поиском
6. /admin/holdings — CRUD-таблица холдингов (только admin)
7. Auth context/store (Zustand или Redux Toolkit)

### Database (SQLite + Alembic)
1. users: id, email, is_verified, created_at
2. verification_codes: id, email, code, expires_at, used
3. holdings: id, name, inn, legal_form, created_at
4. user_holdings: user_id, holding_id, role (admin/member)

### Infra / DevEx
1. .env конфигурация
2. Makefile или tasks.json: dev, migrate, test
3. ESLint + Prettier + pre-commit hooks (опционально)
4. docker-compose (опционально, на будущее для Redis/SMTP)

## Out of scope
- Реальная SMTP-отправка (код пишется в лог)
- OAuth / SSO / интеграция с AD
- Document management (Increment B)
- MCP-сервер (Increment E)
- Версионирование документов (Increment D)
- Юридически значимые операции

## Backend work
- FastAPI app factory, CORS middleware, lifespan
- SQLAlchemy models + Alembic
- Auth router (register, verify, login, refresh)
- Holdings router (CRUD)
- User router (profile, set_holding)
- Auth dependency (get_current_user)
- Email service (interface + console implementation)

## Frontend work
- Vite + React + TS + Ant Design setup
- OpenAPI client generation (orval/openapi-typescript-codegen)
- Auth pages (register, verify, login)
- Auth context + token storage (localStorage with httpOnly fallback plan)
- Protected route wrapper
- Profile page (holding selector with search)
- Admin holdings page (Ant Design Table + Modal forms)
- Header component with current holding display

## Database work
- Initial Alembic revision
- Seed script: admin user + demo holding

## Infra / DevEx work
- README with dev setup instructions
- Run scripts (dev.sh/dev.ps1)
- VS Code launch configs

## Acceptance criteria
1. POST /auth/register — создаёт пользователя, возвращает success
2. POST /auth/verify — с верным кодом подтверждает email
3. POST /auth/login — отправляет код на email (лог)
4. POST /auth/verify-login — с верным кодом возвращает JWT (access + refresh)
5. Запросы без токена → 401
6. Admin может создать холдинг (name + inn + legal_form)
7. После входа пользователь видит страницу выбора холдинга
8. Выбор холдинга сохраняется в профиле и отображается в шапке
9. Пользователь без холдинга не может перейти к другим страницам
10. Все endpoint'ы покрыты тестами (pytest + httpx)

## Required tests
- unit: JWT utils, code generation & validation, email service
- integration: pytest + httpx против всех auth- и holding-endpoint'ов
- smoke: один e2e-тест (Cypress/Playwright): регистрация → верификация → логин → выбор холдинга

## Risks
- Email-заглушка: код не уходит на реальный email — нужно явно документировать
- JWT-секрет хранится в .env — риск утечки, требуется ротация
- Отсутствие rate-limiting на register/login — уязвимость к спаму
- refresh token хранится в localStorage — XSS-уязвимость (на MVP допустимо, в Stage 2 — httpOnly cookie)

## Dependencies
- Python 3.11+
- Node.js 20+
- SMTP-сервер — не требуется на MVP

## Deliverables
- Код backend (/backend)
- Код frontend (/frontend)
- Миграции БД (/backend/alembic)
- Тесты (pytest + playwright)
- Stage report
- QA-чеклист
