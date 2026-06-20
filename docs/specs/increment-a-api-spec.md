# Increment A: API и контракты данных

> **Проект:** SRP (Service for Regulations and Policies)
> **Инкремент:** A — Scaffolding + Аутентификация + Управление холдингами
> **Дата:** 2026-06-20
> **Статус:** Черновик (готов к реализации)
> **Аудитория:** BE (Python/FastAPI), FE (React/TypeScript)

---

## Оглавление

1. [Контекст и цель](#1-контекст-и-цель)
2. [Базовый URL и формат](#2-базовый-url-и-формат)
3. [REST API контракты](#3-rest-api-контракты)
   - 3.1 Auth — регистрация и вход
   - 3.2 Auth — токены
   - 3.3 Auth — профиль
   - 3.4 Holdings — CRUD (admin)
   - 3.5 User — выбор холдинга
4. [Data Models (SQLAlchemy)](#4-data-models-sqlalchemy)
5. [Бизнес-логика и флоу](#5-бизнес-логика-и-флоу)
6. [Единый формат ошибок](#6-единый-формат-ошибок)
7. [Middleware и зависимости](#7-middleware-и-зависимости)
8. [Безопасность](#8-безопасность)
9. [Приложение A: Примеры ответов](#9-приложение-a-примеры-ответов)
10. [Приложение B: Статус-коды](#10-приложение-b-статус-коды)

---

## 1. Контекст и цель

Данный документ описывает API-контракты, модели данных и бизнес-логику для первого инкремента SRP.
Цель инкремента A: пользователь может зарегистрироваться по email, войти в систему, создать/выбрать холдинг и увидеть пустой дашборд.

### Принятые решения (ADR-0001)

- **Auth:** passwordless email-код + JWT (access 15 мин + refresh 7 дней)
- **Мультитенантность:** user_holdings (user_id, holding_id, role), на MVP — один холдинг на пользователя
- **Email:** заглушка — код выводится в лог (console), реальная SMTP-отправка не требуется
- **Профиль холдинга:** Наименование (уникальное), ИНН (опционально), Юр.форма (ООО/АО/ПАО/иное)

---

## 2. Базовый URL и формат

### Base URL

```
/api/v1
```

Пример: `POST /api/v1/auth/register`

### Формат дат

Даты передаются в ISO 8601: `2026-06-20T14:30:00Z`

### Content-Type

- Запросы: `application/json`
- Ответы: `application/json`

### Аутентификация

Защищённые endpoint'ы требуют заголовок:

```
Authorization: Bearer <access_token>
```

---

## 3. REST API контракты

---

### 3.1 Auth — регистрация и вход

---

#### `POST /api/v1/auth/register`

Регистрация нового пользователя по email. Создаёт запись в `users` с `is_verified=false`.
Генерирует 6-значный код подтверждения (purpose=registration) и выводит его в лог.

**Request Body:**

```json
{
  "email": "user@example.com"
}
```

| Поле  | Тип    | Обязательно | Описание            |
|-------|--------|-------------|---------------------|
| email | string | да          | Email пользователя  |

**Валидация на этапе запроса:**
- `email` — не пустая строка, соответствует регулярному выражению `^[^\s@]+@[^\s@]+\.[^\s@]+$`
- `email` — максимум 255 символов

**Успешный ответ:** `201 Created`

```json
{
  "message": "Verification code sent to email",
  "code_length": 6
}
```

| Поле        | Тип    | Описание                               |
|-------------|--------|----------------------------------------|
| message     | string | Сообщение пользователю                 |
| code_length | int    | Длина кода (всегда 6, для FE валидации)|

**Ошибки:**

| Код  | Условие                          | detail.code      |
|------|----------------------------------|------------------|
| 409  | Email уже зарегистрирован        | CONFLICT         |
| 422  | Некорректный email (не прошёл валидацию) | VALIDATION_ERROR |

**Пример cURL:**

```bash
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com"}'
```

---

#### `POST /api/v1/auth/verify-registration`

Подтверждение регистрации по коду из email. Устанавливает `is_verified=true`, помечает код использованным.

**Request Body:**

```json
{
  "email": "user@example.com",
  "code": "482913"
}
```

| Поле  | Тип    | Обязательно | Описание             |
|-------|--------|-------------|----------------------|
| email | string | да          | Email пользователя   |
| code  | string | да          | 6-значный код        |

**Валидация:**
- `code` — строка ровно из 6 символов

**Успешный ответ:** `200 OK`

```json
{
  "message": "Email verified successfully",
  "verified": true
}
```

| Поле     | Тип     | Описание                              |
|----------|---------|---------------------------------------|
| message  | string  | Сообщение пользователю                |
| verified | boolean | Всегда `true` при успехе             |

**Ошибки:**

| Код  | Условие                          | detail.code      |
|------|----------------------------------|------------------|
| 400  | Неверный код                     | UNAUTHORIZED     |
| 400  | Код истёк (15 мин)              | CODE_EXPIRED     |
| 400  | Код уже использован             | UNAUTHORIZED     |
| 404  | Пользователь не найден          | NOT_FOUND        |
| 422  | Некорректный email или код      | VALIDATION_ERROR |

**Пример cURL:**

```bash
curl -X POST http://localhost:8000/api/v1/auth/verify-registration \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "code": "482913"}'
```

---

#### `POST /api/v1/auth/login`

Инициирует вход по email. Генерирует 6-значный код (purpose=login) и выводит в лог.
Пользователь должен быть зарегистрирован и верифицирован.

**Request Body:**

```json
{
  "email": "user@example.com"
}
```

| Поле  | Тип    | Обязательно | Описание            |
|-------|--------|-------------|---------------------|
| email | string | да          | Email пользователя  |

**Успешный ответ:** `200 OK`

```json
{
  "message": "Verification code sent to email"
}
```

**Ошибки:**

| Код  | Условие                         | detail.code      |
|------|---------------------------------|------------------|
| 404  | Пользователь не найден          | NOT_FOUND        |
| 403  | Email не подтверждён            | FORBIDDEN        |
| 422  | Некорректный email              | VALIDATION_ERROR |

**Пример cURL:**

```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com"}'
```

---

#### `POST /api/v1/auth/verify-login`

Подтверждение входа по коду. При успехе возвращает JWT-токены.

**Request Body:**

```json
{
  "email": "user@example.com",
  "code": "731804"
}
```

| Поле  | Тип    | Обязательно | Описание             |
|-------|--------|-------------|----------------------|
| email | string | да          | Email пользователя   |
| code  | string | да          | 6-значный код        |

**Успешный ответ:** `200 OK`

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "dGhpcyBpcyBhIHJlZnJl...",
  "token_type": "bearer",
  "expires_in": 900
}
```

| Поле          | Тип    | Описание                              |
|---------------|--------|---------------------------------------|
| access_token  | string | JWT access token (15 мин)             |
| refresh_token | string | JWT refresh token (7 дней)            |
| token_type    | string | Всегда `"bearer"`                     |
| expires_in    | int    | Время жизни access_token в секундах (900) |

**Ошибки:**

| Код  | Условие                          | detail.code      |
|------|----------------------------------|------------------|
| 400  | Неверный код                     | UNAUTHORIZED     |
| 400  | Код истёк (15 мин)              | CODE_EXPIRED     |
| 400  | Код уже использован             | UNAUTHORIZED     |
| 404  | Пользователь не найден          | NOT_FOUND        |
| 422  | Некорректный email или код      | VALIDATION_ERROR |

**Пример cURL:**

```bash
curl -X POST http://localhost:8000/api/v1/auth/verify-login \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "code": "731804"}'
```

---

### 3.2 Auth — токены

---

#### `POST /api/v1/auth/refresh`

Обновление access_token по refresh_token.

**Request Body:**

```json
{
  "refresh_token": "dGhpcyBpcyBhIHJlZnJl..."
}
```

| Поле          | Тип    | Обязательно | Описание              |
|---------------|--------|-------------|-----------------------|
| refresh_token | string | да          | Действующий refresh   |

**Успешный ответ:** `200 OK`

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "expires_in": 900
}
```

**Ошибки:**

| Код  | Условие                    | detail.code      |
|------|----------------------------|------------------|
| 401  | Refresh token невалидный   | UNAUTHORIZED     |
| 401  | Refresh token истёк       | UNAUTHORIZED     |
| 422  | Некорректный формат       | VALIDATION_ERROR |

**Пример cURL:**

```bash
curl -X POST http://localhost:8000/api/v1/auth/refresh \
  -H "Content-Type: application/json" \
  -d '{"refresh_token": "dGhpcyBpcyBhIHJlZnJl..."}'
```

---

### 3.3 Auth — профиль

---

#### `GET /api/v1/auth/me`

Возвращает профиль текущего аутентифицированного пользователя.

**Заголовки:**

```
Authorization: Bearer <access_token>
```

**Успешный ответ:** `200 OK`

```json
{
  "id": 1,
  "email": "user@example.com",
  "is_verified": true,
  "active_holding": {
    "id": 1,
    "name": "ООО Ромашка",
    "inn": "7701123456",
    "legal_form": "ООО"
  }
}
```

| Поле           | Тип      | Описание                                |
|----------------|----------|-----------------------------------------|
| id             | int      | ID пользователя                         |
| email          | string   | Email пользователя                      |
| is_verified    | boolean  | Статус верификации email                |
| active_holding | object|null | Текущий выбранный холдинг или `null`    |

**Поля `active_holding`:**

| Поле       | Тип      | Описание             |
|------------|----------|----------------------|
| id         | int      | ID холдинга          |
| name       | string   | Наименование         |
| inn        | string|null | ИНН (10 или 12 цифр) |
| legal_form | string   | Юр. форма            |

**Ошибки:**

| Код  | Условие                    | detail.code      |
|------|----------------------------|------------------|
| 401  | Отсутствует / невалидный токен | UNAUTHORIZED  |

**Пример cURL:**

```bash
curl -X GET http://localhost:8000/api/v1/auth/me \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..."
```

---

### 3.4 Holdings — CRUD (admin)

Все endpoint'ы в этой секции требуют:
- `Authorization: Bearer <access_token>`
- Роль пользователя в контексте: `admin` в `user_holdings`

---

#### `GET /api/v1/holdings`

Получить список всех холдингов (доступно всем аутентифицированным пользователям).

**Успешный ответ:** `200 OK`

```json
[
  {
    "id": 1,
    "name": "ООО Ромашка",
    "inn": "7701123456",
    "legal_form": "ООО",
    "created_at": "2026-06-20T10:00:00Z"
  },
  {
    "id": 2,
    "name": "АО Технопарк",
    "inn": "7702987654",
    "legal_form": "АО",
    "created_at": "2026-06-20T10:05:00Z"
  }
]
```

**Ошибки:**

| Код  | Условие                    | detail.code      |
|------|----------------------------|------------------|
| 401  | Не авторизован             | UNAUTHORIZED     |

**Пример cURL:**

```bash
curl -X GET http://localhost:8000/api/v1/holdings \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..."
```

---

#### `POST /api/v1/holdings`

Создать новый холдинг. Требуется роль `admin`.

**Request Body:**

```json
{
  "name": "ООО Ромашка",
  "inn": "7701123456",
  "legal_form": "ООО"
}
```

| Поле       | Тип    | Обязательно | Описание                                      |
|------------|--------|-------------|-----------------------------------------------|
| name       | string | да          | Наименование холдинга (уникальное, до 255)    |
| inn        | string | нет         | ИНН (10 или 12 цифр, опционально)             |
| legal_form | string | да          | Юр. форма: `ООО`, `АО`, `ПАО` или `иное`     |

**Валидация:**
- `name` — 1-255 символов, не пустая строка
- `inn` — если указан, то строка из 10 или 12 цифр
- `legal_form` — одно из: `ООО`, `АО`, `ПАО`, `иное`

**Успешный ответ:** `201 Created`

```json
{
  "id": 1,
  "name": "ООО Ромашка",
  "inn": "7701123456",
  "legal_form": "ООО"
}
```

**Ошибки:**

| Код  | Условие                          | detail.code      |
|------|----------------------------------|------------------|
| 401  | Не авторизован                   | UNAUTHORIZED     |
| 403  | Недостаточно прав (не admin)     | FORBIDDEN        |
| 409  | Холдинг с таким name уже существует | CONFLICT      |
| 422  | Некорректные данные              | VALIDATION_ERROR |

**Пример cURL:**

```bash
curl -X POST http://localhost:8000/api/v1/holdings \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..." \
  -d '{"name": "ООО Ромашка", "inn": "7701123456", "legal_form": "ООО"}'
```

---

#### `PUT /api/v1/holdings/{id}`

Обновить существующий холдинг. Требуется роль `admin`. Все поля опциональны — частичное обновление (PATCH-семантика).

**Path parameters:**

| Параметр | Тип  | Описание      |
|----------|------|---------------|
| id       | int  | ID холдинга   |

**Request Body:**

```json
{
  "name": "ООО Ромашка-Новая",
  "inn": "7701123457",
  "legal_form": "ООО"
}
```

| Поле       | Тип    | Обязательно | Описание                          |
|------------|--------|-------------|-----------------------------------|
| name       | string | нет         | Наименование холдинга             |
| inn        | string | нет         | ИНН (10 или 12 цифр)              |
| legal_form | string | нет         | Юр. форма: `ООО`, `АО`, `ПАО`, `иное` |

**Успешный ответ:** `200 OK`

```json
{
  "id": 1,
  "name": "ООО Ромашка-Новая",
  "inn": "7701123457",
  "legal_form": "ООО"
}
```

**Ошибки:**

| Код  | Условие                               | detail.code      |
|------|---------------------------------------|------------------|
| 401  | Не авторизован                        | UNAUTHORIZED     |
| 403  | Недостаточно прав (не admin)          | FORBIDDEN        |
| 404  | Холдинг с id не найден                | NOT_FOUND        |
| 409  | name уже занят другим холдингом       | CONFLICT         |
| 422  | Некорректные данные                   | VALIDATION_ERROR |

**Пример cURL:**

```bash
curl -X PUT http://localhost:8000/api/v1/holdings/1 \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..." \
  -d '{"name": "ООО Ромашка-Новая", "inn": "7701123457"}'
```

---

#### `DELETE /api/v1/holdings/{id}`

Удалить холдинг. Требуется роль `admin`.

**Path parameters:**

| Параметр | Тип  | Описание      |
|----------|------|---------------|
| id       | int  | ID холдинга   |

**Успешный ответ:** `204 No Content` (без тела)

**Ошибки:**

| Код  | Условие                          | detail.code      |
|------|----------------------------------|------------------|
| 401  | Не авторизован                   | UNAUTHORIZED     |
| 403  | Недостаточно прав (не admin)     | FORBIDDEN        |
| 404  | Холдинг с id не найден           | NOT_FOUND        |
| 409  | Холдинг содержит связи (user_holdings) | CONFLICT   |

**Пример cURL:**

```bash
curl -X DELETE http://localhost:8000/api/v1/holdings/1 \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..."
```

---

### 3.5 User — выбор холдинга

---

#### `PUT /api/v1/user/holding`

Установить активный холдинг для текущего пользователя. Проверяет членство пользователя в холдинге.

**Заголовки:**

```
Authorization: Bearer <access_token>
```

**Request Body:**

```json
{
  "holding_id": 1
}
```

| Поле       | Тип | Обязательно | Описание              |
|------------|-----|-------------|-----------------------|
| holding_id | int | да          | ID холдинга           |

**Успешный ответ:** `200 OK`

```json
{
  "message": "Active holding set successfully",
  "active_holding": {
    "id": 1,
    "name": "ООО Ромашка"
  }
}
```

**Ошибки:**

| Код  | Условие                          | detail.code      |
|------|----------------------------------|------------------|
| 401  | Не авторизован                   | UNAUTHORIZED     |
| 403  | Пользователь не состоит в холдинге | FORBIDDEN      |
| 404  | Холдинг не найден                | NOT_FOUND        |
| 422  | Некорректный holding_id          | VALIDATION_ERROR |

**Пример cURL:**

```bash
curl -X PUT http://localhost:8000/api/v1/user/holding \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..." \
  -d '{"holding_id": 1}'
```

---

## 4. Data Models (SQLAlchemy)

### 4.1 `users`

Таблица пользователей системы.

| Колонка      | Тип                | Constraints                              | Описание                    |
|-------------|--------------------|------------------------------------------|-----------------------------|
| id          | Integer            | PK, autoincrement                        | Уникальный ID               |
| email       | String(255)        | UNIQUE, NOT NULL, INDEX                  | Email пользователя          |
| is_verified | Boolean            | NOT NULL, default=False                  | Подтверждён ли email        |
| created_at  | DateTime           | NOT NULL, default=datetime.utcnow        | Дата создания               |
| updated_at  | DateTime           | NOT NULL, default=datetime.utcnow, onupdate | Дата обновления          |

**Индексы:** `ix_users_email` — уникальный индекс по `email`

### 4.2 `verification_codes`

Таблица кодов подтверждения для регистрации и входа.

| Колонка    | Тип                | Constraints                              | Описание                       |
|-----------|--------------------|------------------------------------------|--------------------------------|
| id         | Integer            | PK, autoincrement                        | Уникальный ID                  |
| email      | String(255)        | NOT NULL, INDEX                          | Email, на который отправлен код|
| code       | String(6)          | NOT NULL                                 | 6-значный код                  |
| purpose    | String(20)         | NOT NULL                                 | `"registration"` или `"login"` |
| expires_at | DateTime           | NOT NULL                                 | Время истечения кода           |
| used       | Boolean            | NOT NULL, default=False                  | Флаг использования             |
| created_at | DateTime           | NOT NULL, default=datetime.utcnow        | Дата создания                  |

**Индексы:** `ix_verification_codes_email` — по `email` для быстрого поиска

**Примечание:** На MVP очистка просроченных кодов не требуется. Можно добавить периодическую очистку начиная со Stage 2.

### 4.3 `holdings`

Таблица холдингов (организаций-арендаторов в мультитенантной модели).

| Колонка     | Тип                | Constraints                              | Описание                                   |
|------------|--------------------|------------------------------------------|--------------------------------------------|
| id          | Integer            | PK, autoincrement                        | Уникальный ID                              |
| name        | String(255)        | UNIQUE, NOT NULL                         | Наименование холдинга                      |
| inn         | String(12)         | NULLABLE                                 | ИНН (10 или 12 цифр, опционально)          |
| legal_form  | String(20)         | NOT NULL                                 | Юр. форма: `ООО`, `АО`, `ПАО`, `иное`     |
| created_at  | DateTime           | NOT NULL, default=datetime.utcnow        | Дата создания                              |
| updated_at  | DateTime           | NOT NULL, default=datetime.utcnow, onupdate | Дата обновления                         |

**Индексы:** `ix_holdings_name` — уникальный индекс по `name`

### 4.4 `user_holdings`

Связка пользователь-холдинг с ролью. Обеспечивает мультитенантность.

| Колонка    | Тип                | Constraints                                    | Описание                  |
|-----------|--------------------|------------------------------------------------|---------------------------|
| id         | Integer            | PK, autoincrement                              | Уникальный ID             |
| user_id    | Integer            | FK -> users.id, NOT NULL, INDEX               | ID пользователя           |
| holding_id | Integer            | FK -> holdings.id, NOT NULL, INDEX             | ID холдинга               |
| role       | String(20)         | NOT NULL, default=`"member"`                   | Роль: `admin` или `member`|

**Constraints:**
- `UNIQUE (user_id, holding_id)` — уникальная связка
- `FK -> users.id` ON DELETE CASCADE
- `FK -> holdings.id` ON DELETE CASCADE

**Индексы:** `ix_user_holdings_user_id`, `ix_user_holdings_holding_id`, `uq_user_holdings` (unique composite)

### 4.5 ER-диаграмма (текстовая)

```
┌─────────────────┐       ┌───────────────────┐       ┌──────────────────┐
│      users       │       │   user_holdings    │       │    holdings       │
├─────────────────┤       ├───────────────────┤       ├──────────────────┤
│ id (PK)         │──1:N──│ user_id (FK)       │N:1───│ id (PK)           │
│ email (UQ)      │       │ holding_id (FK)    │       │ name (UQ)         │
│ is_verified     │       │ role (admin/member)│       │ inn (nullable)    │
│ created_at      │       │ UNIQUE(u,h)        │       │ legal_form        │
│ updated_at      │       └───────────────────┘       │ created_at        │
└─────────────────┘                                    │ updated_at        │
                                                       └──────────────────┘
       │ 1:N
       ▼
┌───────────────────┐
│ verification_codes│
├───────────────────┤
│ id (PK)           │
│ email (INDEX)     │
│ code (6)          │
│ purpose           │
│ expires_at        │
│ used              │
│ created_at        │
└───────────────────┘
```

---

## 5. Бизнес-логика и флоу

### 5.1 Регистрация

```
POST /auth/register(email)
│
├─ 1. Валидация формата email (regex)
├─ 2. Проверка уникальности email в таблице users
│    └─ Если exists → 409 CONFLICT
├─ 3. Создание пользователя: users.insert(email, is_verified=false)
├─ 4. Генерация 6-значного кода:
│    └─ code = random.randint(100000, 999999) → str
├─ 5. Сохранение кода:
│    └─ verification_codes.insert(email, code, purpose="registration",
│         expires_at=now+15min, used=false)
├─ 6. Вывод кода в лог:
│    └─ logger.info(f"Verification code for {email}: {code}")
└─ 7. Response 201 { message, code_length: 6 }
```

**Детали:**
- `code` — строковое представление 6-значного числа с ведущими нулями (f"{num:06d}")
- `expires_at` — `datetime.utcnow() + timedelta(minutes=15)`
- Если пользователь существует с `is_verified=true`, возвращаем 409 — конфликт
- Если пользователь существует с `is_verified=false`, считаем регистрацию незавершённой: **перезаписываем код** (старый код помечаем used=true, создаём новый). Это позволяет пользователю запросить новый код.

### 5.2 Верификация регистрации

```
POST /auth/verify-registration(email, code)
│
├─ 1. Поиск пользователя по email
│    └─ Если не найден → 404 NOT_FOUND
├─ 2. Поиск verification_codes WHERE email AND purpose="registration"
│    ORDER BY created_at DESC LIMIT 1
├─ 3. Проверки:
│    ├─ Если код не найден → 400 UNAUTHORIZED
│    ├─ Если code.used = true → 400 UNAUTHORIZED
│    └─ Если code.expires_at < now → 400 CODE_EXPIRED
├─ 4. Если code != предоставленному → 400 UNAUTHORIZED
├─ 5. Пометить код использованным: code.used = true
├─ 6. Обновить пользователя: user.is_verified = true
└─ 7. Response 200 { message, verified: true }
```

### 5.3 Логин

```
POST /auth/login(email)
│
├─ 1. Поиск пользователя по email
│    └─ Если не найден → 404 NOT_FOUND
├─ 2. Проверка is_verified
│    └─ Если false → 403 FORBIDDEN
├─ 3. Генерация 6-значного кода
├─ 4. Сохранение: verification_codes(email, code, purpose="login",
│    expires_at=now+15min, used=false)
├─ 5. Вывод в лог
└─ 6. Response 200 { message }
```

### 5.4 Верификация логина (выдача токенов)

```
POST /auth/verify-login(email, code)
│
├─ 1. Поиск пользователя по email
│    └─ Если не найден → 404 NOT_FOUND
├─ 2. Поиск verification_codes WHERE email AND purpose="login"
│    ORDER BY created_at DESC LIMIT 1
├─ 3. Проверки (аналогично верификации регистрации)
├─ 4. Пометить код использованным
├─ 5. Генерация JWT:
│    ├─ access_token: { sub: user.id, type: "access", exp: now+15min }
│    └─ refresh_token: { sub: user.id, type: "refresh", exp: now+7d }
├─ 6. Response 200 { access_token, refresh_token, token_type, expires_in }
└─ 7. Примечание: refresh_token хранится в БД? На MVP — нет, stateless JWT.
       В Stage 2 — добавить таблицу refresh_tokens для revoke-логики.
```

### 5.5 Refresh токена

```
POST /auth/refresh(refresh_token)
│
├─ 1. Декодировать refresh_token (проверить подпись и exp)
│    └─ Если невалидный → 401 UNAUTHORIZED
├─ 2. Проверить type == "refresh"
│    └─ Если нет → 401 UNAUTHORIZED
├─ 3. Извлечь user.id из payload
├─ 4. Поиск пользователя по id
│    └─ Если не найден или is_verified=false → 401 UNAUTHORIZED
├─ 5. Генерация нового access_token
└─ 6. Response 200 { access_token, expires_in }
```

### 5.6 Выбор холдинга

```
PUT /user/holding(holding_id)  [Auth required]
│
├─ 1. Извлечение текущего пользователя из токена
├─ 2. Поиск холдинга по holding_id
│    └─ Если не найден → 404 NOT_FOUND
├─ 3. Проверка членства: user_holdings WHERE user_id AND holding_id
│    └─ Если записи нет → 403 FORBIDDEN
├─ 4. Сохранение активного холдинга:
│    └─ На MVP: сохраняем в user_holdings поле active (или отдельная колонка
│       в users: active_holding_id FK -> holdings.id)
│    └─ Рекомендация: добавить колонку active_holding_id (FK, nullable) в users
├─ 5. Response 200 { message, active_holding: { id, name } }
```

**Варианты хранения active_holding:**

| Вариант | Плюсы | Минусы | Решение |
|---------|-------|--------|---------|
| Колонка `active_holding_id` в `users` | Простота, 1 запрос | Денормализация | **MVP** |
| Отдельная таблица `user_active_holdings` | Нормализация | Сложнее | Stage 2+ |

**Решение на MVP:** добавить колонку `active_holding_id` (Integer, FK -> holdings.id, nullable) в таблицу `users`.

### 5.7 Получение профиля (`GET /auth/me`)

```
GET /auth/me  [Auth required]
│
├─ 1. Извлечение пользователя из токена
├─ 2. Загрузка пользователя с active_holding (join)
├─ 3. Response 200 { id, email, is_verified, active_holding }
```

---

## 6. Единый формат ошибок

### 6.1 Структура

Все ошибки возвращаются в едином формате:

```json
{
  "detail": {
    "code": "ERROR_CODE",
    "message": "Human-readable message on Russian or English",
    "field": "field_name"
  }
}
```

| Поле    | Тип      | Обязательно | Описание                                 |
|---------|----------|-------------|------------------------------------------|
| code    | string   | да          | Машинный код ошибки (см. таблицу ниже)   |
| message | string   | да          | Человекочитаемое сообщение               |
| field   | string   | нет         | Поле, вызвавшее ошибку (для валидации)   |

### 6.2 Коды ошибок

| Код               | HTTP статус | Описание                                      | Когда возникает                              |
|-------------------|-------------|-----------------------------------------------|----------------------------------------------|
| `VALIDATION_ERROR`| 422         | Невалидные данные в запросе                   | Некорректный email, пустой name, и т.д.      |
| `NOT_FOUND`       | 404         | Ресурс не найден                              | Пользователь не найден, холдинг не найден    |
| `CONFLICT`        | 409         | Конфликт дубликата                            | Email уже зарегистрирован, name уже занят    |
| `UNAUTHORIZED`    | 401 / 400   | Неверный токен или код                        | Неверный код, истёкший токен, невалидный refresh |
| `CODE_EXPIRED`    | 400         | Код подтверждения истёк                       | Коду больше 15 минут                         |
| `FORBIDDEN`       | 403         | Недостаточно прав                             | Пользователь не admin, email не подтверждён  |
| `RATE_LIMITED`    | 429         | Превышен лимит запросов                       | >5 попыток отправки кода за 15 минут         |

### 6.3 Примеры ошибок

**VALIDATION_ERROR (422):**
```json
{
  "detail": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid email format",
    "field": "email"
  }
}
```

**CONFLICT (409):**
```json
{
  "detail": {
    "code": "CONFLICT",
    "message": "A user with this email already exists",
    "field": "email"
  }
}
```

**CODE_EXPIRED (400):**
```json
{
  "detail": {
    "code": "CODE_EXPIRED",
    "message": "Verification code has expired. Request a new one.",
    "field": "code"
  }
}
```

**UNAUTHORIZED (401) — невалидный токен:**
```json
{
  "detail": {
    "code": "UNAUTHORIZED",
    "message": "Invalid or expired token",
    "field": null
  }
}
```

**RATE_LIMITED (429):**
```json
{
  "detail": {
    "code": "RATE_LIMITED",
    "message": "Too many requests. Please try again in 15 minutes.",
    "field": null
  }
}
```

### 6.4 Обработка ValidationError (Pydantic)

FastAPI автоматически возвращает ошибки валидации Pydantic в формате:

```json
{
  "detail": [
    {
      "loc": ["body", "email"],
      "msg": "value is not a valid email address",
      "type": "value_error"
    }
  ]
}
```

**На MVP допустимо** возвращать стандартный формат Pydantic.
**Рекомендуется** добавить exception handler, который преобразует их в единый формат:

```json
{
  "detail": {
    "code": "VALIDATION_ERROR",
    "message": "value is not a valid email address",
    "field": "email"
  }
}
```

---

## 7. Middleware и зависимости

### 7.1 `get_current_user` — Dependency для защищённых endpoint'ов

```python
async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> User:
    """Извлекает и валидирует JWT, возвращает объект User."""
    # 1. Декодировать JWT (проверить подпись, exp, type="access")
    # 2. Извлечь user.id из sub
    # 3. Загрузить пользователя из БД (включая active_holding)
    # 4. Если пользователь не найден или is_verified=false → 401
    # 5. Вернуть User
```

**Использование:**

```python
@app.get("/api/v1/auth/me")
async def get_me(user: User = Depends(get_current_user)):
    return UserProfileSchema.from_orm(user)
```

### 7.2 `require_admin` — Dependency для admin-endpoint'ов

```python
async def require_admin(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> User:
    """Проверяет, что пользователь имеет роль admin хотя бы в одном холдинге."""
    # 1. Проверить user_holdings WHERE user_id AND role="admin"
    # 2. Если записи нет → 403 FORBIDDEN
    # 3. Вернуть User
```

**Примечание:** На MVP админ-доступ глобальный — пользователь admin, если есть хотя бы одна запись с ролью admin в любой связке user_holdings. В Stage 2+ это заменится на контекстную проверку (admin конкретного холдинга).

### 7.3 `require_membership` — Dependency для проверки членства в холдинге

```python
async def require_membership(
    holding_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> UserHolding:
    """Проверяет, что пользователь состоит в указанном холдинге."""
    # 1. Проверить user_holdings WHERE user_id AND holding_id
    # 2. Если записи нет → 403 FORBIDDEN
    # 3. Вернуть UserHolding
```

### 7.4 Rate Limiting Middleware

**Назначение:** предотвращение спама на endpoint'ах отправки кода.

**Эндпоинты под rate limiting:**
- `POST /auth/register`
- `POST /auth/login`

**Реализация на MVP (in-memory):**

```python
from collections import defaultdict
from datetime import datetime, timedelta

class InMemoryRateLimiter:
    def __init__(self, max_attempts: int = 5, window_minutes: int = 15):
        self.max_attempts = max_attempts
        self.window = timedelta(minutes=window_minutes)
        self.attempts: dict[str, list[datetime]] = defaultdict(list)

    async def check(self, key: str) -> bool:
        now = datetime.utcnow()
        # Очистить старые записи
        self.attempts[key] = [
            t for t in self.attempts[key] if now - t < self.window
        ]
        if len(self.attempts[key]) >= self.max_attempts:
            return False  # rate limited
        self.attempts[key].append(now)
        return True
```

**Ключ rate limiting:** `f"auth:{email}"`

**HTTP-заголовки ответа при rate limit:**

```
X-RateLimit-Limit: 5
X-RateLimit-Remaining: 0
X-RateLimit-Reset: <timestamp>
```

**При достижении лимита:** `429 Too Many Requests` + тело ошибки `RATE_LIMITED`.

### 7.5 CORS Middleware

Настройки CORS для разработки:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Vite dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

Для production: `allow_origins` — конкретный домен frontend'а.

### 7.6 Email Service (Interface + Console Implementation)

```python
from abc import ABC, abstractmethod

class EmailService(ABC):
    @abstractmethod
    async def send_code(self, email: str, code: str, purpose: str) -> None:
        """Отправить код подтверждения на email."""
        ...

class ConsoleEmailService(EmailService):
    async def send_code(self, email: str, code: str, purpose: str) -> None:
        logger.info(f"[EMAIL] To: {email} | Code: {code} | Purpose: {purpose}")
        print(f"[EMAIL] To: {email} | Code: {code} | Purpose: {purpose}")
```

**DI через FastAPI lifespan:**

```python
async def lifespan(app: FastAPI):
    app.state.email_service = ConsoleEmailService()
    yield
```

---

## 8. Безопасность

### 8.1 JWT-конфигурация

| Параметр              | Значение                | Примечание                          |
|-----------------------|-------------------------|-------------------------------------|
| Алгоритм              | HS256                   | Быстрый, HMAC с секретом            |
| Секрет                | Из `JWT_SECRET` в .env  | Минимум 32 символа, сложный         |
| Access token TTL      | 15 минут (900 сек)      | Короткое время жизни                |
| Refresh token TTL     | 7 дней (604800 сек)     | Длинное время жизни                 |
| Поля payload (access) | `sub`: user.id, `type`: "access", `exp`: timestamp | |
| Поля payload (refresh)| `sub`: user.id, `type`: "refresh", `exp`: timestamp | |

### 8.2 Хранение токенов на frontend

| Токен          | Хранение на MVP | Риск | Рекомендация на Stage 2+ |
|----------------|-----------------|------|--------------------------|
| access_token   | localStorage    | XSS  | httpOnly cookie          |
| refresh_token  | localStorage    | XSS  | httpOnly cookie + /api/v1/auth/refresh |

**Митигация XSS на MVP:** Content Security Policy (CSP) заголовки + минимальный DOM-доступ.

### 8.3 Защита endpoint'ов

| Уровень защиты | Что проверяет | Механизм |
|----------------|---------------|----------|
| Аутентификация | Наличие и валидность access_token | Depends(get_current_user) |
| Авторизация   | Роль admin в user_holdings | Depends(require_admin) |
| Членство      | Наличие в user_holdings | Depends(require_membership) |

### 8.4 Security assumptions (MVP)

- JWT-секрет хранится в `.env`, не попадает в репозиторий
- Refresh token не может быть отозван на MVP (stateless JWT)
- Код подтверждения — 6 цифр (1 из 1 000 000 комбинаций)
- Rate limiting: 5 попыток за 15 минут снижает риск брутфорса до пренебрежимого

---

## 9. Приложение A: Примеры ответов

### A.1 Полный сценарий: регистрация → верификация → логин → профиль

**1. Регистрация**
```bash
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email": "analyst@holding.ru"}'
```

**Response 201:**
```json
{
  "message": "Verification code sent to email",
  "code_length": 6
}
```

**Лог:**
```
[EMAIL] To: analyst@holding.ru | Code: 482913 | Purpose: registration
```

**2. Верификация регистрации**
```bash
curl -X POST http://localhost:8000/api/v1/auth/verify-registration \
  -H "Content-Type: application/json" \
  -d '{"email": "analyst@holding.ru", "code": "482913"}'
```

**Response 200:**
```json
{
  "message": "Email verified successfully",
  "verified": true
}
```

**3. Логин**
```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "analyst@holding.ru"}'
```

**Response 200:**
```json
{
  "message": "Verification code sent to email"
}
```

**4. Верификация логина**
```bash
curl -X POST http://localhost:8000/api/v1/auth/verify-login \
  -H "Content-Type: application/json" \
  -d '{"email": "analyst@holding.ru", "code": "731804"}'
```

**Response 200:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOjEsInR5cGUiOiJhY2Nlc3MiLCJleHAiOjE3MTg4ODUyMDB9.signature",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOjEsInR5cGUiOiJyZWZyZXNoIiwiZXhwIjoxNzE5NDkwMDAwfQ.signature",
  "token_type": "bearer",
  "expires_in": 900
}
```

**5. Получение профиля (без холдинга)**
```bash
curl -X GET http://localhost:8000/api/v1/auth/me \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..."
```

**Response 200:**
```json
{
  "id": 1,
  "email": "analyst@holding.ru",
  "is_verified": true,
  "active_holding": null
}
```

**6. Admin создаёт холдинг**
```bash
curl -X POST http://localhost:8000/api/v1/holdings \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..." \
  -d '{"name": "ООО Холдинг-Центр", "inn": "7701987654", "legal_form": "ООО"}'
```

**Response 201:**
```json
{
  "id": 1,
  "name": "ООО Холдинг-Центр",
  "inn": "7701987654",
  "legal_form": "ООО"
}
```

**7. Пользователь выбирает холдинг**
```bash
curl -X PUT http://localhost:8000/api/v1/user/holding \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..." \
  -d '{"holding_id": 1}'
```

**Response 200:**
```json
{
  "message": "Active holding set successfully",
  "active_holding": {
    "id": 1,
    "name": "ООО Холдинг-Центр"
  }
}
```

**8. Профиль с холдингом**
```bash
curl -X GET http://localhost:8000/api/v1/auth/me \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..."
```

**Response 200:**
```json
{
  "id": 1,
  "email": "analyst@holding.ru",
  "is_verified": true,
  "active_holding": {
    "id": 1,
    "name": "ООО Холдинг-Центр",
    "inn": "7701987654",
    "legal_form": "ООО"
  }
}
```

### A.2 Получение списка холдингов

```bash
curl -X GET http://localhost:8000/api/v1/holdings \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..."
```

**Response 200:**
```json
[
  {
    "id": 1,
    "name": "ООО Холдинг-Центр",
    "inn": "7701987654",
    "legal_form": "ООО",
    "created_at": "2026-06-20T10:00:00Z"
  },
  {
    "id": 2,
    "name": "АО Технологии Будущего",
    "inn": "7701654321",
    "legal_form": "АО",
    "created_at": "2026-06-20T10:05:00Z"
  }
]
```

### A.3 Ошибка повторной регистрации

```bash
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email": "analyst@holding.ru"}'
```

**Response 409:**
```json
{
  "detail": {
    "code": "CONFLICT",
    "message": "A user with this email already exists",
    "field": "email"
  }
}
```

### A.4 Ошибка неверного кода

```bash
curl -X POST http://localhost:8000/api/v1/auth/verify-registration \
  -H "Content-Type: application/json" \
  -d '{"email": "analyst@holding.ru", "code": "000000"}'
```

**Response 400:**
```json
{
  "detail": {
    "code": "UNAUTHORIZED",
    "message": "Invalid verification code",
    "field": "code"
  }
}
```

### A.5 Ошибка доступа без токена

```bash
curl -X GET http://localhost:8000/api/v1/holdings
```

**Response 401:**
```json
{
  "detail": {
    "code": "UNAUTHORIZED",
    "message": "Not authenticated",
    "field": null
  }
}
```

### A.6 Обновление холдинга

```bash
curl -X PUT http://localhost:8000/api/v1/holdings/1 \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..." \
  -d '{"inn": "7701987655"}'
```

**Response 200:**
```json
{
  "id": 1,
  "name": "ООО Холдинг-Центр",
  "inn": "7701987655",
  "legal_form": "ООО"
}
```

### A.7 Удаление холдинга

```bash
curl -X DELETE http://localhost:8000/api/v1/holdings/2 \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..."
```

**Response 204:** (no body)

### A.8 Refresh токена

```bash
curl -X POST http://localhost:8000/api/v1/auth/refresh \
  -H "Content-Type: application/json" \
  -d '{"refresh_token": "eyJhbGciOiJIUzI1NiIs..."}'
```

**Response 200:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.new_access_token",
  "expires_in": 900
}
```

---

## 10. Приложение B: Статус-коды

Сводная таблица endpoint'ов и возвращаемых статус-кодов.

| # | Endpoint                          | Метод | 200 | 201 | 204 | 400 | 401 | 403 | 404 | 409 | 422 | 429 |
|---|-----------------------------------|-------|-----|-----|-----|-----|-----|-----|-----|-----|-----|-----|
| 1 | `/auth/register`                  | POST  |     |  ✓  |     |     |     |     |     |  ✓  |  ✓  |  ✓  |
| 2 | `/auth/verify-registration`       | POST  |  ✓  |     |     |  ✓  |     |     |  ✓  |     |  ✓  |     |
| 3 | `/auth/login`                     | POST  |  ✓  |     |     |     |     |  ✓  |  ✓  |     |  ✓  |  ✓  |
| 4 | `/auth/verify-login`              | POST  |  ✓  |     |     |  ✓  |     |     |  ✓  |     |  ✓  |     |
| 5 | `/auth/refresh`                   | POST  |  ✓  |     |     |     |  ✓  |     |     |     |  ✓  |     |
| 6 | `/auth/me`                        | GET   |  ✓  |     |     |     |  ✓  |     |     |     |     |     |
| 7 | `/holdings`                       | GET   |  ✓  |     |     |     |  ✓  |     |     |     |     |     |
| 8 | `/holdings`                       | POST  |     |  ✓  |     |     |  ✓  |  ✓  |     |  ✓  |  ✓  |     |
| 9 | `/holdings/{id}`                  | PUT   |  ✓  |     |     |     |  ✓  |  ✓  |  ✓  |  ✓  |  ✓  |     |
|10 | `/holdings/{id}`                  | DELETE|     |     |  ✓  |     |  ✓  |  ✓  |  ✓  |  ✓  |     |     |
|11 | `/user/holding`                   | PUT   |  ✓  |     |     |     |  ✓  |  ✓  |  ✓  |     |  ✓  |     |

**Итого:** 11 endpoint'ов, 8 уникальных статус-кодов.

---

## Приложение C: Рекомендации по реализации для BE

### C.1 Структура проекта (backend)

```
backend/
├── alembic/
│   └── versions/
├── app/
│   ├── api/
│   │   └── v1/
│   │       ├── __init__.py
│   │       ├── auth.py        # auth router
│   │       ├── holdings.py    # holdings CRUD router
│   │       └── user.py        # user profile router
│   ├── core/
│   │   ├── config.py          # Settings from .env
│   │   ├── security.py        # JWT generation/validation
│   │   └── dependencies.py    # get_current_user, require_admin
│   ├── models/
│   │   ├── __init__.py
│   │   ├── user.py
│   │   ├── verification_code.py
│   │   ├── holding.py
│   │   └── user_holding.py
│   ├── schemas/
│   │   ├── auth.py            # Pydantic request/response schemas
│   │   ├── holding.py
│   │   └── user.py
│   ├── services/
│   │   ├── auth_service.py
│   │   ├── code_service.py    # Generation + validation
│   │   └── email_service.py   # Interface + Console
│   ├── middleware/
│   │   └── rate_limiter.py
│   └── main.py                # FastAPI app factory
├── tests/
│   ├── conftest.py
│   ├── test_auth.py
│   └── test_holdings.py
├── .env.example
├── alembic.ini
├── pyproject.toml
└── requirements.txt
```

### C.2 Зависимости (Python)

```
fastapi>=0.111,<1.0
uvicorn[standard]>=0.29,<1.0
sqlalchemy>=2.0,<3.0
alembic>=1.13,<2.0
pydantic>=2.0,<3.0
pydantic-settings>=2.0,<3.0
python-jose[cryptography]>=3.3,<4.0
pytest>=8.0,<9.0
httpx>=0.27,<1.0
aiosqlite>=0.20,<1.0
```

### C.3 Рекомендации по тестированию

| Тип теста            | Инструмент | Что тестировать |
|----------------------|-----------|-----------------|
| Unit (сервисы)       | pytest    | JWT utils, code generation, email service, rate limiter |
| Integration (API)    | pytest + httpx | Все 11 endpoint'ов: success + error scenarios |
| Smoke (e2e)          | Playwright / Cypress | Регистрация → верификация → логин → выбор холдинга |

**Покрытие API-тестов:**
- Каждый endpoint: минимум 1 success + 2 error сценария
- Auth: неверный код, истёкший код, повторная регистрация, доступ без токена
- Holdings: создание, дубликат имени, удаление с существующими связями, доступ не-admin

---

*Конец документа.*
