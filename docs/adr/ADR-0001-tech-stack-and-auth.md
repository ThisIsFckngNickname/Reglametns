# ADR-0001: Технологический стек и аутентификация на MVP

## Status
Accepted

## Context
Проект SRP (Service for Regulations and Policies) стартует с нуля. Необходимо зафиксировать ключевые технологические решения, влияющие на всю архитектуру: frontend-фреймворк, способ аутентификации, структуру профиля холдинга и глубину парсинга PDF.

## Decision

### 1. Frontend-стек
**React 18+ + Vite + TypeScript + Ant Design 5**
- Vite — быстрая сборка, first-class TypeScript support
- Ant Design 5 — корпоративная UI-библиотека с готовыми компонентами (таблицы, формы, дропдауны)
- OpenAPI-генератор клиента (openapi-typescript-codegen) для типизированного API-слоя

### 2. Аутентификация
**Passwordless email-код + JWT (access + refresh token)**
- Регистрация: email → код подтверждения → верификация
- Вход: email → код → JWT (access 15min + refresh 7d)
- На MVP код выводится в лог (заглушка SMTP)
- Rate-limiting на отправку кода — обязателен

### 3. Профиль холдинга
Обязательные поля на MVP:
- Наименование (строка, уникальное)
- ИНН (опционально, строка 10/12 цифр)
- Юридическая принадлежность (ООО/АО/ПАО/иное)

### 4. Мультитенантность
- Таблица user_holdings (user_id, holding_id, role: admin/member)
- Пользователь может быть привязан к одному холдингу (на MVP)
- После входа обязателен выбор холдинга из дропдауна с поиском
- Все данные изолированы по holding_id

### 5. Парсинг PDF
- Таблицы — извлекаем
- Сноски, колонтитулы — не извлекаем
- Приоритет: Word (.docx) — первый, PDF — второй

### 6. Декомпозиция Stage 1
Stage 1 разбит на 5 инкрементов (A→E):
- A: Scaffolding + Auth + Holdings
- B: Document Registry + Upload + Parsing
- C: Generator + GigaChat Pro
- D: Versioning + Orders
- E: MCP + Legislation Search + Impact Map

## Consequences

### Positive
- Мультитенантность заложена с первого дня, миграция данных между холдингами невозможна по умолчанию
- Passwordless auth снижает барьер входа для пользователей
- Ant Design ускоряет разработку корпоративного UI
- Vite + TypeScript дают быструю обратную связь при разработке
- Декомпозиция на инкременты позволяет поставлять ценность итеративно

### Negative
- Email-заглушка на MVP означает, что код нужно копировать из логов — UX страдает до внедрения SMTP
- React + Ant Design — тяжелый bundle для первой загрузки (решается lazy loading)
- ИНН как опциональное поле может привести к дубликатам холдингов

### Neutral
- При переходе на PostgreSQL/S3 схема БД изменится: user_holdings может стать частью более сложной RBAC-модели
- OpenAPI-генератор привязывает frontend к контрактам backend — breaking changes требуют координации
