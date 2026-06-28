# Phase 5 B3: Amendments — Приказы, вносящие изменения

> **Проект:** SRP (Service for Regulations and Policies)
> **Фаза:** 5 / Инкремент B3 — Amendments (изменения документов приказами)
> **Дата:** 2026-06-28
> **Статус:** Черновик (готов к реализации)
> **Аудитория:** BE (Python/FastAPI), FE (React/TypeScript)
> **Зависимости:** Phase 5 B2 (document_type), существующий DocumentLink с link_type="amends"

---

## Содержание

1. [Контекст и цель](#1-контекст-и-цель)
2. [Архитектурное решение](#2-архитектурное-решение)
3. [Модели данных](#3-модели-данных)
4. [API Endpoints](#4-api-endpoints)
5. [Сервисный слой](#5-сервисный-слой)
6. [Frontend](#6-frontend)
7. [Acceptance Criteria](#7-acceptance-criteria)
8. [Edge Cases](#8-edge-cases)
9. [Risks и Mitigations](#9-risks-и-mitigations)
10. [Verification Strategy](#10-verification-strategy)
11. [Open Questions](#11-open-questions)
12. [Приложение: Примеры ответов](#12-приложение-примеры-ответов)

---

## 1. Контекст и цель

### 1.1 Бизнес-ценность

В реестре документов присутствуют приказы (`document_type=order`). Приказы могут вносить изменения в другие документы (регламенты, положения, политики и т.д.). Система должна позволять:

1. Пользователю явно указывать, что приказ вносит изменения в документ
2. На детальной странице приказа видеть список документов, которые он изменяет
3. На детальной странице документа видеть список приказов, которые его изменяют

### 1.2 Принципы

- **Не создавать новых таблиц** — используется существующая `DocumentLink` с `link_type="amends"`
- **Минимум нового кода** — переиспользуем существующий CRUD для DocumentLink
- **Только чтение для новых endpoints** — создание/удаление связей уже реализовано
- **Изоляция по компании** — все запросы проверяют `company_id`

### 1.3 Что уже есть

| Компонент | Статус | Описание |
|-----------|--------|----------|
| `DocumentLink` модель | ✅ | Поддерживает `link_type="amends"` |
| `POST /documents/{id}/links` | ✅ | Создание связи с любым `link_type` |
| `DELETE /documents/{id}/links/{link_id}` | ✅ | Удаление связи |
| `GET /documents/{id}/links` | ✅ | Исходящие связи (общий список) |
| `GET /documents/{id}/links/incoming` | ✅ | Входящие связи (общий список) |
| `document_type="order"` | ✅ | Добавлен в B2 |
| Frontend: модалка создания связи | ✅ | Вкладка «Связи» на детальной странице |

### 1.4 Что делаем в B3

| Компонент | Действие |
|-----------|----------|
 | `GET /documents/{id}/amendments` | **Новый** — приказы, изменяющие документ |
 | `GET /documents/{id}/amended-documents` | **Новый** — документы, изменяемые приказом |
 | `DocumentAmendmentService` | **Новый** сервис (или методы) |
 | Frontend: вкладка «Изменения» | **Новая** вкладка на `DocumentDetailPage` |
 | Pydantic схема `AmendmentItem` | **Новая** |

---

## 2. Архитектурное решение

### 2.1 Ключевые решения

| Решение | Обоснование |
|---------|-------------|
| Использовать `DocumentLink` без изменений | Модель уже поддерживает `link_type="amends"`. Новая таблица = избыточность. |
| Новые read-only endpoints | Отдельные endpoints для amendments удобнее на фронтенде, чем фильтрация общего списка связей. |
| Новый `DocumentAmendmentService` | Чистое разделение ответственности. Можно добавить как отдельный сервис или миксин. |
| Вкладка «Изменения» на фронтенде | Контекстно-зависимое отображение: для приказа — «что изменяет», для документа — «чем изменён». |

### 2.2 Схема взаимодействия

```
FE (DocumentDetailPage)
  │
  ├─ Вкладка «Изменения»
  │    ├─ Если doc.document_type === 'order':
  │    │   └─ GET /documents/{id}/amended-documents → таблица
  │    ├─ Если doc.document_type !== 'order':
  │    │   └─ GET /documents/{id}/amendments → таблица
  │    └─ Кнопка «Связать с приказом» (editor+)
  │         └─ Модалка → POST /documents/{id}/links { link_type: "amends" }
  │
  └─ (существующие вкладки)
```

---

## 3. Модели данных

### 3.1 DocumentLink (существующая)

Модель `DocumentLink` используется без изменений. Критичные поля:

```python
class DocumentLink(Base):
    __tablename__ = "document_links"

    id: int                          # PK
    source_document_id: int          # FK -> documents.id (приказ)
    target_document_id: int          # FK -> documents.id (изменяемый документ)
    link_type: str                   # "amends" для нашего случая
    is_manual: bool                  # True для ручных связей
    description: str | None          # Опциональное описание
    created_by: int | None           # FK -> users.id
    created_at: datetime             # Время создания
```

**Важно:** `link_type` уже валидируется на уровне Pydantic (`DocumentLinkCreate`) — допустимые значения: `references`, `amends`, `supersedes`, `related`.

### 3.2 Document (существующая)

Модель `Document` не требует изменений. Используем существующее поле `document_type` для идентификации приказов (`document_type="order"`).

### 3.3 ER-связь amendment

```
┌──────────────┐       ┌─────────────────┐       ┌──────────────────┐
│  Document    │       │  DocumentLink    │       │   Document       │
│  (приказ)    │──1:N──│  link_type=      │──N:1──│  (изменяемый     │
│  id=source   │       │  "amends"        │       │   документ)      │
└──────────────┘       └─────────────────┘       │  id=target       │
                                                  └──────────────────┘
```

---

## 4. API Endpoints

### 4.1 AmendmentItem (Pydantic схема)

```python
# backend/app/schemas/links.py (дополнение)

from datetime import datetime
from pydantic import BaseModel


class AmendmentItem(BaseModel):
    """A document that amends or is amended by another document."""
    document_id: int
    link_id: int
    title: str
    document_type: str
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}
```

### 4.2 GET /api/v1/documents/{id}/amendments

Возвращает приказы, вносящие изменения в этот документ (incoming amendments).

```
GET /api/v1/documents/{id}/amendments
Authorization: Bearer <access_token>
```

**Path parameters:**

| Параметр | Тип | Описание |
|----------|-----|----------|
| id | int | ID документа |

**Успешный ответ:** `200 OK`

```json
[
  {
    "document_id": 5,
    "link_id": 10,
    "title": "Приказ №45 от 20.06.2026",
    "document_type": "order",
    "status": "approved",
    "created_at": "2026-06-28T10:00:00Z"
  }
]
```

**Логика:**
1. Проверить, что документ с `id` принадлежит компании пользователя (иначе 404)
2. Найти все `DocumentLink`, где `target_document_id = id AND link_type = 'amends'`
3. Для каждой связи загрузить `source_document` (приказ)
4. Вернуть массив `AmendmentItem[]`

**Ошибки:**

| Код | Условие | detail.code |
|-----|---------|-------------|
| 401 | Не авторизован | UNAUTHORIZED |
| 404 | Документ не найден или не в компании пользователя | NOT_FOUND |

**Пример cURL:**
```bash
curl -X GET http://localhost:8000/api/v1/documents/1/amendments \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..."
```

### 4.3 GET /api/v1/documents/{id}/amended-documents

Возвращает документы, изменяемые этим приказом (outgoing amendments).

```
GET /api/v1/documents/{id}/amended-documents
Authorization: Bearer <access_token>
```

**Path parameters:**

| Параметр | Тип | Описание |
|----------|-----|----------|
| id | int | ID документа (приказа) |

**Успешный ответ:** `200 OK`

```json
[
  {
    "document_id": 3,
    "link_id": 10,
    "title": "Регламент документооборота",
    "document_type": "regulation",
    "status": "draft",
    "created_at": "2026-06-28T10:00:00Z"
  }
]
```

**Логика:**
1. Проверить, что документ с `id` принадлежит компании пользователя (иначе 404)
2. Найти все `DocumentLink`, где `source_document_id = id AND link_type = 'amends'`
3. Для каждой связи загрузить `target_document`
4. Вернуть массив `AmendmentItem[]`

**Ошибки:**

| Код | Условие | detail.code |
|-----|---------|-------------|
| 401 | Не авторизован | UNAUTHORIZED |
| 404 | Документ не найден или не в компании пользователя | NOT_FOUND |

**Пример cURL:**
```bash
curl -X GET http://localhost:8000/api/v1/documents/5/amended-documents \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..."
```

### 4.4 Существующие endpoints (без изменений)

| Endpoint | Использование |
|----------|---------------|
| `POST /api/v1/documents/{id}/links` | Создание связи `amends` |
| `DELETE /api/v1/documents/{id}/links/{link_id}` | Удаление связи |
| `GET /api/v1/documents/{id}/links` | Исходящие связи (общие) |
| `GET /api/v1/documents/{id}/links/incoming` | Входящие связи (общие) |

---

## 5. Сервисный слой

### 5.1 DocumentAmendmentService

Новый сервис (или миксин, добавляемый к `DocumentService` через множественное наследование):

```python
# backend/app/services/document_amendment_service.py

import logging
from datetime import datetime
from typing import List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundException
from app.models.document import Document
from app.models.document_link import DocumentLink

logger = logging.getLogger(__name__)


class DocumentAmendmentService:
    """Service for amendment-specific queries.
    
    Handles the "amends" link type between orders and documents.
    """

    async def get_amendments(
        self, document_id: int, company_id: int, db: AsyncSession
    ) -> List[dict]:
        """Get orders that amend this document.
        
        Returns a list of source documents (orders) that have
        an 'amends' link pointing to this document.
        """
        # Verify document ownership
        doc = await self._verify_ownership(document_id, company_id, db)
        if doc is None:
            raise NotFoundException(
                message="Document not found", field="document_id"
            )

        # Find all 'amends' links where this document is the target
        stmt = (
            select(DocumentLink)
            .where(
                DocumentLink.target_document_id == document_id,
                DocumentLink.link_type == "amends",
            )
            .join(
                Document,
                DocumentLink.source_document_id == Document.id,
            )
            .add_columns(
                Document.id.label("source_id"),
                Document.title.label("source_title"),
                Document.document_type.label("source_type"),
                Document.status.label("source_status"),
            )
        )
        result = await db.execute(stmt)
        rows = result.all()

        return [
            {
                "document_id": row.source_id,
                "link_id": row[0].id,
                "title": row.source_title,
                "document_type": row.source_type,
                "status": row.source_status,
                "created_at": (
                    row[0].created_at.isoformat()
                    if row[0].created_at
                    else None
                ),
            }
            for row in rows
        ]

    async def get_amended_documents(
        self, document_id: int, company_id: int, db: AsyncSession
    ) -> List[dict]:
        """Get documents amended by this order.
        
        Returns a list of target documents that this document
        (an order) amends.
        """
        # Verify document ownership
        doc = await self._verify_ownership(document_id, company_id, db)
        if doc is None:
            raise NotFoundException(
                message="Document not found", field="document_id"
            )

        # Find all 'amends' links where this document is the source
        stmt = (
            select(DocumentLink)
            .where(
                DocumentLink.source_document_id == document_id,
                DocumentLink.link_type == "amends",
            )
            .join(
                Document,
                DocumentLink.target_document_id == Document.id,
            )
            .add_columns(
                Document.id.label("target_id"),
                Document.title.label("target_title"),
                Document.document_type.label("target_type"),
                Document.status.label("target_status"),
            )
        )
        result = await db.execute(stmt)
        rows = result.all()

        return [
            {
                "document_id": row.target_id,
                "link_id": row[0].id,
                "title": row.target_title,
                "document_type": row.target_type,
                "status": row.target_status,
                "created_at": (
                    row[0].created_at.isoformat()
                    if row[0].created_at
                    else None
                ),
            }
            for row in rows
        ]

    async def _verify_ownership(
        self, document_id: int, company_id: int, db: AsyncSession
    ) -> Document | None:
        """Verify that a document belongs to the given company."""
        stmt = select(Document).where(
            Document.id == document_id,
            Document.company_id == company_id,
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()
```

### 5.2 Интеграция в DocumentService

Добавить `DocumentAmendmentService` в цепочку наследования `DocumentService`:

```python
# backend/app/services/document_service.py

from app.services.document_read_service import DocumentReadService
from app.services.document_upload_service import DocumentUploadService
from app.services.document_update_service import DocumentUpdateService
from app.services.document_amendment_service import DocumentAmendmentService


class DocumentService(
    DocumentReadService,
    DocumentUploadService,
    DocumentUpdateService,
    DocumentAmendmentService,
):
    """Facade combining all document operations."""
    pass


document_service = DocumentService()
```

### 5.3 Регистрация endpoint'ов

Добавить два новых обработчика в `backend/app/api/v1/documents.py`:

```python
@router.get("/{document_id}/amendments", response_model=List[AmendmentItem])
async def get_amendments(
    document_id: int,
    user: User = Depends(require_active_company),
    db: AsyncSession = Depends(get_db),
):
    """Get orders that amend this document."""
    return await document_service.get_amendments(
        document_id=document_id,
        company_id=user.active_company_id,
        db=db,
    )


@router.get("/{document_id}/amended-documents", response_model=List[AmendmentItem])
async def get_amended_documents(
    document_id: int,
    user: User = Depends(require_active_company),
    db: AsyncSession = Depends(get_db),
):
    """Get documents amended by this order."""
    return await document_service.get_amended_documents(
        document_id=document_id,
        company_id=user.active_company_id,
        db=db,
    )
```

---

## 6. Frontend

### 6.1 Новая вкладка «Изменения»

Вкладка добавляется на `DocumentDetailPage.tsx` после вкладки «Анализ» (последняя на данный момент).

**Позиция в табах:** после `analysis`:

```
info | structure | terms | abbreviations | tables | versions | links | analysis | amendments ← NEW
```

**Логика отображения:**

| Условие | Показываем |
|---------|------------|
| `document_type === 'order'` | Секция «Вносит изменения в» + опциональная кнопка «Связать» |
| `document_type !== 'order'` | Секция «Изменяется приказами» |
| Всегда (для editor+) | Кнопка «Связать с приказом» |

### 6.2 API-клиент (дополнение)

```typescript
// frontend/src/api/documents.ts (дополнение)

export interface AmendmentItem {
  document_id: number
  link_id: number
  title: string
  document_type: string
  status: string
  created_at: string
}

export async function getAmendments(id: number): Promise<AmendmentItem[]> {
  const response = await apiClient.get(`/documents/${id}/amendments`)
  return response.data
}

export async function getAmendedDocuments(id: number): Promise<AmendmentItem[]> {
  const response = await apiClient.get(`/documents/${id}/amended-documents`)
  return response.data
}
```

### 6.3 Типы (дополнение)

```typescript
// frontend/src/types/index.ts (дополнение)

export interface AmendmentItem {
  document_id: number
  link_id: number
  title: string
  document_type: string
  status: string
  created_at: string
}
```

### 6.4 Компонент вкладки

```tsx
// Внутри DocumentDetailPage.tsx

// State
const [amendments, setAmendments] = useState<AmendmentItem[]>([])
const [amendedDocs, setAmendedDocs] = useState<AmendmentItem[]>([])
const [amendmentsLoading, setAmendmentsLoading] = useState(false)

// Loaders
const loadAmendments = useCallback(async () => {
  if (!documentId) return
  setAmendmentsLoading(true)
  try {
    const doc = currentDocument
    if (!doc) return
    
    if (doc.document_type === 'order') {
      const data = await getAmendedDocuments(documentId)
      setAmendedDocs(data)
    } else {
      const data = await getAmendments(documentId)
      setAmendments(data)
    }
  } catch {
    // Silent fail
  } finally {
    setAmendmentsLoading(false)
  }
}, [documentId, currentDocument])

// В handleTabChange добавить:
case 'amendments':
  if (amendedDocs.length === 0 && amendments.length === 0) loadAmendments()
  break
```

**Структура вкладки:**

```tsx
{
  key: 'amendments',
  label: 'Изменения',
  children: (
    <div>
      {/* Если приказ: показывает, какие документы изменяет */}
      {currentDocument.document_type === 'order' && (
        <>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
            <Title level={5} style={{ margin: 0 }}>Вносит изменения в</Title>
            {canEdit && (
              <Button
                type="primary"
                size="small"
                icon={<PlusOutlined />}
                onClick={() => {
                  setNewLinkType('amends')
                  setLinkModalOpen(true)
                }}
              >
                Связать с документом
              </Button>
            )}
          </div>
          {amendmentsLoading ? (
            <Spin style={{ display: 'block', margin: '40px auto' }} />
          ) : amendedDocs.length === 0 ? (
            <Empty description="Этот приказ не вносит изменения ни в один документ" image={EMPTY_IMAGE} />
          ) : (
            <Table
              dataSource={amendedDocs}
              rowKey="link_id"
              pagination={false}
              size="small"
              columns={amendmentColumns}
            />
          )}
        </>
      )}

      {/* Если не приказ: показывает приказы, которые его изменяют */}
      {currentDocument.document_type !== 'order' && (
        <>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
            <Title level={5} style={{ margin: 0 }}>Изменяется приказами</Title>
            {canEdit && (
              <Button
                type="primary"
                size="small"
                icon={<PlusOutlined />}
                onClick={() => {
                  setNewLinkType('amends')
                  setLinkModalOpen(true)
                }}
              >
                Связать с приказом
              </Button>
            )}
          </div>
          {amendmentsLoading ? (
            <Spin style={{ display: 'block', margin: '40px auto' }} />
          ) : amendments.length === 0 ? (
            <Empty description="Нет приказов, изменяющих этот документ" image={EMPTY_IMAGE} />
          ) : (
            <Table
              dataSource={amendments}
              rowKey="link_id"
              pagination={false}
              size="small"
              columns={amendmentColumns}
            />
          )}
        </>
      )}

      {/* Кнопка удаления связи — в колонке действий таблицы */}
    </div>
  ),
}
```

**Колонки таблицы:**

```typescript
// Для amendedDocs (приказ → документы)
const amendmentColumns: ColumnsType<AmendmentItem> = [
  {
    title: 'Название',
    dataIndex: 'title',
    key: 'title',
    ellipsis: true,
    render: (text: string) => <a onClick={() => navigate(`/documents/${record.document_id}`)}>{text}</a>,
  },
  {
    title: 'Тип',
    dataIndex: 'document_type',
    key: 'document_type',
    width: 140,
    render: (type: string) => (
      <Tag color={DOCUMENT_TYPE_COLORS[type] || 'default'}>
        {DOCUMENT_TYPE_LABELS[type as DocumentType] || type}
      </Tag>
    ),
  },
  {
    title: 'Статус',
    dataIndex: 'status',
    key: 'status',
    width: 120,
    render: (status: string) => (
      <Tag color={STATUS_COLORS[status as DocumentStatus]}>
        {STATUS_LABELS[status as DocumentStatus] || status}
      </Tag>
    ),
  },
  {
    title: 'Дата связи',
    dataIndex: 'created_at',
    key: 'created_at',
    width: 160,
    render: (date: string) => dayjs(date).format('DD.MM.YYYY HH:mm'),
  },
  {
    title: '',
    key: 'actions',
    width: 60,
    render: (_: any, record: AmendmentItem) => canEdit && (
      <Popconfirm
        title="Удалить связь?"
        onConfirm={() => handleDeleteLink(record.link_id)}
        okText="Да"
        cancelText="Нет"
      >
        <Button type="link" danger size="small" icon={<DeleteOutlined />} />
      </Popconfirm>
    ),
  },
]
```

### 6.5 Адаптация существующей модалки создания связи

Существующая модалка создания связи (вкладка «Связи») уже поддерживает все `link_type`, включая `amends`. При открытии модалки из вкладки «Изменения» нужно предустановить `link_type = 'amends'`.

**Переиспользование:** модалка одна, открывается с разным `default link_type`:
- Из вкладки «Связи»: `link_type` выбирается пользователем (по умолчанию `references`)
- Из вкладки «Изменения»: `link_type` предустановлен в `amends`

---

## 7. Acceptance Criteria

1. **Создание связи amends**
   - Приказ (`document_type=order`) можно связать с любым документом через `POST /documents/{id}/links` с `link_type="amends"`
   - Ответ содержит `id`, `source_document_id`, `target_document_id`, `link_type`, `created_at`

2. **Просмотр изменяемых документов (на приказе)**
   - На детальной странице приказа вкладка «Изменения» показывает список документов, которые он изменяет
   - Каждая строка: Название, Тип, Статус, Дата связи
   - Если изменяемых документов нет: сообщение «Этот приказ не вносит изменения ни в один документ»

3. **Просмотр изменяющих приказов (на документе)**
   - На детальной странице документа (не приказа) вкладка «Изменения» показывает список приказов, которые его изменяют
   - Каждая строка: Приказ, Статус, Дата связи
   - Если изменяющих приказов нет: сообщение «Нет приказов, изменяющих этот документ»

4. **Удаление связи**
   - Связь можно удалить через существующий `DELETE /documents/{id}/links/{link_id}`
   - После удаления вкладка «Изменения» обновляется

5. **Проверка company_id**
   - `GET /documents/{id}/amendments` возвращает 404, если документ не в компании пользователя
   - `GET /documents/{id}/amended-documents` возвращает 404, если документ не в компании пользователя

6. **Валидация link_type**
   - `POST /documents/{id}/links` с `link_type="amends"` проходит валидацию
   - `POST /documents/{id}/links` с недопустимым `link_type` возвращает 422

---

## 8. Edge Cases

| Случай | Ожидаемое поведение |
|--------|---------------------|
| Приказ изменяет сам себя | 400 Bad Request (защита на уровне `create_link`) |
| Документ удалён (hard delete) | CASCADE удаляет связанные `DocumentLink` |
| Приказ изменяет несколько документов | Вкладка показывает все (`N:N` через `DocumentLink`) |
| Несколько приказов изменяют один документ | Вкладка показывает все |
| Пользователь не editor | Кнопка «Связать» не показывается; API возвращает 403 |
| Документ archived | Связи продолжают отображаться (архив — только статус) |
| `link_type="amends"` с документа, который не приказ | Технически возможно, но бизнес-логика не запрещает |
| Очень длинное название документа | Таблица использует `ellipsis: true` |

---

## 9. Risks и Mitigations

| Риск | Влияние | Mitigation |
|------|---------|------------|
| CASCADE при удалении документа теряет связи | Потеря данных о связях | Документировано как expected behavior. Hard delete — редкая admin-операция. |
| Один приказ изменяет сотни документов | Производительность | Без пагинации на MVP. При необходимости — добавить пагинацию. |
| link_type="amends" не валидируется на уровне БД | Целостность данных | Валидация на уровне Pydantic + ограничение в коде. |
| Дублирование связей (дважды amends между одними документами) | Дубли в UI | `create_link` создаёт новую запись каждый раз. На MVP — без уникального constraint. Риск низкий. |
| Frontend загружает обе секции для приказа | Лишний запрос | Загружаем только релевантную секцию в зависимости от `document_type`. |

---

## 10. Verification Strategy

### 10.1 Backend-тесты (pytest)

```python
# backend/tests/test_amendments.py

class TestGetAmendments:
    """GET /api/v1/documents/{id}/amendments"""

    async def test_returns_orders_that_amend_document(self, client, db):
        """Документ, на который ссылаются приказы с link_type=amends."""
        ...

    async def test_returns_empty_list_when_no_amendments(self, client, db):
        """Нет приказов, изменяющих документ."""
        ...

    async def test_returns_404_for_foreign_document(self, client, db):
        """Документ другой компании — 404."""
        ...

    async def test_filters_by_link_type(self, client, db):
        """Связи других типов не попадают в результат."""
        ...


class TestGetAmendedDocuments:
    """GET /api/v1/documents/{id}/amended-documents"""

    async def test_returns_documents_amended_by_order(self, client, db):
        ...

    async def test_returns_empty_list_when_order_amends_nothing(self, client, db):
        ...

    async def test_returns_404_for_foreign_document(self, client, db):
        ...


class TestAmendmentItemSchema:
    """Проверка полей AmendmentItem."""

    async def test_serializes_correctly(self):
        ...
```

### 10.2 E2E-тесты

Проверить на реальном API:
1. Загрузить приказ и документ
2. Создать связь `amends`
3. Проверить, что `GET /documents/{id}/amendments` возвращает приказ
4. Проверить, что `GET /documents/{id}/amended-documents` возвращает документ
5. Удалить связь
6. Проверить, что списки пусты

### 10.3 Frontend-проверки

1. Вкладка «Изменения» появляется только когда есть данные
2. Для приказа показывается секция «Вносит изменения в»
3. Для документа показывается секция «Изменяется приказами»
4. Кнопка «Связать с приказом» показывается только для editor+
5. После создания связи вкладка обновляется
6. После удаления связи вкладка обновляется

### 10.4 TypeScript typecheck

```bash
cd frontend && npx tsc --noEmit
```

---

## 11. Open Questions

1. **Нужна ли пагинация для amendments?**
   - На MVP: нет. Если у документа >100 приказов — добавить query params `page` и `page_size`.
   
2. **Нужно ли отображать description связи?**
   - На MVP: нет. В таблице достаточно базовых полей. При необходимости — добавить колонку.

3. **Показывать ли вкладку «Изменения» для документов с type=order, у которых нет изменяемых документов?**
   - Да, с пустым состоянием и кнопкой создания связи.

4. **Должна ли кнопка «Связать с приказом» фильтровать поиск только по приказам?**
   - На MVP: нет, поиск по всем документам (чтобы не усложнять API). Рекомендую добавить фильтр в будущем.

---

## 12. Приложение: Примеры ответов

### A.1 Успешный запрос amendments

```
GET /api/v1/documents/3/amendments
Authorization: Bearer eyJhbGciOiJIUzI1NiIs...

Response: 200
[
  {
    "document_id": 5,
    "link_id": 10,
    "title": "Приказ №45 от 20.06.2026",
    "document_type": "order",
    "status": "approved",
    "created_at": "2026-06-28T10:00:00Z"
  },
  {
    "document_id": 7,
    "link_id": 12,
    "title": "Приказ №48 от 22.06.2026",
    "document_type": "order",
    "status": "draft",
    "created_at": "2026-06-28T12:00:00Z"
  }
]
```

### A.2 Успешный запрос amended-documents

```
GET /api/v1/documents/5/amended-documents
Authorization: Bearer eyJhbGciOiJIUzI1NiIs...

Response: 200
[
  {
    "document_id": 3,
    "link_id": 10,
    "title": "Регламент документооборота",
    "document_type": "regulation",
    "status": "draft",
    "created_at": "2026-06-28T10:00:00Z"
  }
]
```

### A.3 Пустой результат

```
GET /api/v1/documents/10/amendments

Response: 200
[]
```

### A.4 Ошибка 404

```
GET /api/v1/documents/999/amendments

Response: 404
{
  "detail": {
    "code": "NOT_FOUND",
    "message": "Document not found",
    "field": "document_id"
  }
}
```
