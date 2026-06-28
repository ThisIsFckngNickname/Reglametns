# Phase 6 — Корректировка по замечаниям пользователя (Revision)

> **Статус:** Черновик  
> **Дата:** 2026-06-28  
> **Автор:** SA  
> **Зависимости:** Фаза 5 (генерация, RAG, amendments)

---

## 1. Objective

Пользователь (editor+) может дать замечание к сгенерированному документу. Система передаёт замечание в LLM, получает новую версию текста, заменяет содержимое файла и показывает diff между старой и новой версией. Ревизии логируются, история доступна для просмотра.

**Ключевые ограничения:**
- Версионность (Фаза 7) ещё не реализована → старый файл **перезаписывается**, старая версия не сохраняется как отдельный файл.
- Diff считается по тексту до/после, не по файлам версий.
- Если LLM вернула текст без изменений — ревизия **не создаётся**.

---

## 2. Models (Database)

### 2.1 DocumentRevision

Новая таблица для логирования каждой ревизии.

```python
class DocumentRevision(Base):
    __tablename__ = "document_revisions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    document_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("documents.id", ondelete="CASCADE"), index=True, nullable=False
    )
    comment: Mapped[str] = mapped_column(Text, nullable=False)
    target_section: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    old_text_hash: Mapped[str] = mapped_column(String(64), nullable=False)  # SHA-256
    new_text_hash: Mapped[str] = mapped_column(String(64), nullable=False)  # SHA-256
    stats_json: Mapped[str] = mapped_column(Text, nullable=False)  # JSON: {"added": N, "removed": M, "changed": K}
    created_by: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)

    # Relationships
    document: Mapped["Document"] = relationship("Document", back_populates="revisions", lazy="selectin")
    author: Mapped[Optional["User"]] = relationship("User", lazy="selectin")
```

**Индексы:**
- `ix_document_revisions_document_id` — индекс по `document_id` (уже добавлен через `index=True`)
- Композитный индекс не нужен, т.к. выборка всегда по `document_id` с сортировкой по `created_at DESC`

### 2.2 Document.revisions (backref)

Добавить relationship в `Document`:

```python
# в models/document.py
revisions: Mapped[list["DocumentRevision"]] = relationship(
    "DocumentRevision", back_populates="document",
    cascade="all, delete-orphan", lazy="selectin",
)
```

Обновить `__all__` и `TYPE_CHECKING` импорты.

### 2.3 Создание миграции

```bash
alembic revision --autogenerate -m "add_document_revisions"
```

---

## 3. API Endpoints

Все эндпоинты монтируются в `router.py` через `include_router(revision_router)`.

```python
# app/api/v1/revisions.py
router = APIRouter(prefix="/documents/{document_id}/revisions", tags=["revisions"])
```

### 3.1 POST /api/v1/documents/{document_id}/revise

Создать ревизию — вызвать LLM с замечанием, заменить текст, вернуть diff.

**Request:**
```json
{
  "comment": "Добавь раздел про ответственность сторон",
  "target_section": "Раздел 4"
}
```

**Response (200):**
```json
{
  "document_id": 42,
  "old_text": "Полный старый текст документа...",
  "new_text": "Полный новый текст документа...",
  "diff": {
    "unified_diff": "--- \n+++ \n@@ -1,5 +1,8 @@ ...",
    "html_diff": "<table class=\"diff\">...</table>",
    "stats": {
      "added": 15,
      "removed": 3,
      "changed": 5
    }
  },
  "revision_id": 1,
  "changed": true
}
```

**Response (200, no changes):**
```json
{
  "document_id": 42,
  "old_text": "полный текст...",
  "new_text": "полный текст...",
  "diff": {
    "unified_diff": "",
    "html_diff": "",
    "stats": {"added": 0, "removed": 0, "changed": 0}
  },
  "revision_id": null,
  "changed": false
}
```

**Validation:**
- `comment` — обязательное, min_length=10, max_length=5000
- `target_section` — опционально, max_length=200
- Доступ: editor+
- Проверка: документ существует в active_company
- Проверка: документ не в статусе `archived`

**Errors:**
| HTTP | Code | Когда |
|------|------|-------|
| 404 | DOCUMENT_NOT_FOUND | Документ не найден или не в компании |
| 400 | DOCUMENT_ARCHIVED | Документ в архиве |
| 422 | VALIDATION_ERROR | Невалидное тело |
| 500 | LLM_ERROR | Ошибка вызова LLM |
| 503 | LLM_UNAVAILABLE | Ollama недоступна |

### 3.2 GET /api/v1/documents/{document_id}/revisions

История ревизий.

**Response (200):**
```json
[
  {
    "id": 1,
    "comment": "Добавь раздел про ответственность сторон",
    "target_section": "Раздел 4",
    "stats": {"added": 15, "removed": 3, "changed": 5},
    "created_by_email": "user@example.com",
    "created_at": "2026-06-28T12:00:00"
  }
]
```

**Доступ:** active_company (любой участник компании)

### 3.3 GET /api/v1/documents/{document_id}/revisions/{revision_id}

Детали конкретной ревизии.

**Response (200):**
```json
{
  "id": 1,
  "document_id": 42,
  "comment": "Добавь раздел про ответственность сторон",
  "target_section": "Раздел 4",
  "old_text_hash": "abc...",
  "new_text_hash": "def...",
  "stats": {"added": 15, "removed": 3, "changed": 5},
  "created_by_email": "user@example.com",
  "created_at": "2026-06-28T12:00:00"
}
```

**Примечание:** полный текст `old_text`/`new_text` **не** возвращается, т.к. старая версия не сохраняется (кроме хэша). Для получения diff нужно пересчитать — см. 3.4.

### 3.4 GET /api/v1/documents/{document_id}/revisions/{revision_id}/diff

Diff для исторической ревизии.

**Логика:** так как старый текст не сохраняется, diff для исторической ревизии считается как diff между текущим текстом и текстом на момент ревизии (если бы он сохранялся). **Упрощение:** возвращаем diff для текущего документа, показывая что изменилось с момента той ревизии до сейчас. 

**Альтернатива (рекомендуемая):** Хранить `old_text` и `new_text` в ревизии как текстовые поля (для небольших документов). Для больших документов (> 100 KB) хранить только diff. Учитывая, что мы не храним версии файлов, имеет смысл хранить `old_text` и `new_text` прямо в таблице `DocumentRevision`, чтобы можно было показать diff для любой исторической ревизии.

**Решение:** добавить поля `old_text` и `new_text` типа `Text` в `DocumentRevision`. Это увеличит размер БД, но позволит просматривать diff для любой ревизии без повторного вызова LLM.

**Обновлённая модель DocumentRevision:**
```python
class DocumentRevision(Base):
    ...
    old_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    new_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ...
```

**Response (200):** идентично `POST .../revise` — `{diff: ..., old_text, new_text}`

---

## 4. Pydantic Schemas

Добавить в `app/schemas/revision.py` (новый файл):

```python
# app/schemas/revision.py
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class DiffStats(BaseModel):
    added: int = 0
    removed: int = 0
    changed: int = 0


class DiffResult(BaseModel):
    unified_diff: str = ""
    html_diff: str = ""
    stats: DiffStats


class ReviseRequest(BaseModel):
    comment: str = Field(
        ..., min_length=10, max_length=5000,
        description="Описание замечания к документу"
    )
    target_section: Optional[str] = Field(
        None, max_length=200,
        description="Целевой раздел для правки (опционально)"
    )


class ReviseResponse(BaseModel):
    document_id: int
    old_text: str
    new_text: str
    diff: DiffResult
    revision_id: Optional[int] = None
    changed: bool = True


class RevisionHistoryItem(BaseModel):
    id: int
    comment: str
    target_section: Optional[str]
    stats: DiffStats
    created_by_email: str
    created_at: datetime


class RevisionDetail(BaseModel):
    id: int
    document_id: int
    comment: str
    target_section: Optional[str]
    stats: DiffStats
    created_by_email: str
    created_at: datetime
    old_text: Optional[str] = None
    new_text: Optional[str] = None


class RevisionDiffResponse(BaseModel):
    old_text: str
    new_text: str
    diff: DiffResult
```

**Проверить:** связь `created_by` → `user.email`, подтягивать через `selectinload`.

---

## 5. Services

### 5.1 RevisionService

Новый файл: `backend/app/services/revision_service.py`

```python
"""
Revision service — handles document revision via LLM.
"""

import hashlib
import json
import logging
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestException, NotFoundException
from app.models.document import Document
from app.models.document_revision import DocumentRevision
from app.models.user import User
from app.schemas.revision import DiffResult, DiffStats, ReviseResponse
from app.services.diff_service import diff_service
from app.services.ollama_client import ollama_client
from app.services.storage_service import storage

logger = logging.getLogger(__name__)

REVISION_SYSTEM_PROMPT = """Ты — юрист холдинга. Внеси правки в документ в соответствии с замечаниями пользователя. Сохрани структуру, стиль, нумерацию разделов и общую логику документа. Ответь ПОЛНЫМ ТЕКСТОМ документа целиком, а не только изменениями.

Правила:
1. Сохраняй структуру документа (разделы, подразделы, нумерацию).
2. Вноси изменения только в соответствии с замечанием.
3. Если указан целевой раздел — меняй только его.
4. Если замечание противоречит содержанию документа — уточни в начале ответа в скобках.
5. Не добавляй markdown-разметку, ответ должен быть чистым текстом."""


class RevisionService:
    """Service for revising documents via LLM."""

    def __init__(self, llm_client=None, diff_svc=None):
        self._llm_client = llm_client or ollama_client
        self._diff_svc = diff_svc or diff_service

    async def revise_document(
        self,
        document_id: int,
        comment: str,
        target_section: Optional[str],
        current_user: User,
        db: AsyncSession,
    ) -> ReviseResponse:
        # 1. Verify document exists and is not archived
        doc = await self._get_document(document_id, current_user.active_company_id, db)
        if doc.status == "archived":
            raise BadRequestException(message="Cannot revise an archived document")

        # 2. Get current text
        old_text = await self._get_document_text(doc)

        if not old_text or not old_text.strip():
            raise BadRequestException(message="Document has no text content")

        # 3. Build prompt
        user_prompt = self._build_revision_prompt(old_text, comment, target_section)

        # 4. Call LLM
        try:
            new_text = await self._llm_client.chat_completion(
                messages=[
                    {"role": "system", "content": REVISION_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.2,  # Lower temperature for precise edits
                max_tokens=32000,
            )
        except Exception as e:
            logger.error(f"LLM call failed during revision: {e}")
            raise RuntimeError(f"LLM call failed: {e}")

        if not new_text or not new_text.strip():
            raise RuntimeError("LLM returned empty response")

        # 5. Clean LLM response (strip markdown code fences if present)
        new_text = self._clean_llm_response(new_text)

        # 6. Generate diff
        diff_result = await self._diff_svc.generate_diff(old_text, new_text)

        # 7. Check if anything changed
        if diff_result.stats.added == 0 and diff_result.stats.removed == 0 and diff_result.stats.changed == 0:
            return ReviseResponse(
                document_id=document_id,
                old_text=old_text,
                new_text=old_text,
                diff=diff_result,
                revision_id=None,
                changed=False,
            )

        # 8. Save new text to storage (overwrite)
        await self._save_document_text(doc, new_text)

        # 9. Log revision
        old_hash = hashlib.sha256(old_text.encode("utf-8")).hexdigest()
        new_hash = hashlib.sha256(new_text.encode("utf-8")).hexdigest()

        revision = DocumentRevision(
            document_id=document_id,
            comment=comment,
            target_section=target_section,
            old_text_hash=old_hash,
            new_text_hash=new_hash,
            old_text=old_text,
            new_text=new_text,
            stats_json=diff_result.stats.model_dump_json(),
            created_by=current_user.id,
        )
        db.add(revision)
        await db.flush()
        await db.refresh(revision)

        logger.info(
            f"Document {document_id} revised: revision_id={revision.id}, "
            f"added={diff_result.stats.added}, removed={diff_result.stats.removed}"
        )

        return ReviseResponse(
            document_id=document_id,
            old_text=old_text,
            new_text=new_text,
            diff=diff_result,
            revision_id=revision.id,
            changed=True,
        )

    async def get_revision_history(
        self, document_id: int, company_id: int, db: AsyncSession
    ) -> list[dict]:
        """Get revision history for a document."""
        doc = await self._get_document(document_id, company_id, db)

        stmt = (
            select(DocumentRevision)
            .where(DocumentRevision.document_id == document_id)
            .order_by(DocumentRevision.created_at.desc())
        )
        result = await db.execute(stmt)
        revisions = result.scalars().all()

        return [
            {
                "id": r.id,
                "comment": r.comment,
                "target_section": r.target_section,
                "stats": json.loads(r.stats_json) if r.stats_json else {},
                "created_by_email": r.author.email if r.author else "unknown",
                "created_at": r.created_at,
            }
            for r in revisions
        ]

    async def get_revision_detail(
        self, document_id: int, revision_id: int, company_id: int, db: AsyncSession
    ) -> dict:
        """Get a single revision details."""
        doc = await self._get_document(document_id, company_id, db)

        stmt = select(DocumentRevision).where(
            DocumentRevision.id == revision_id,
            DocumentRevision.document_id == document_id,
        )
        result = await db.execute(stmt)
        revision = result.scalar_one_or_none()

        if revision is None:
            raise NotFoundException(message="Revision not found", field="revision_id")

        return {
            "id": revision.id,
            "document_id": revision.document_id,
            "comment": revision.comment,
            "target_section": revision.target_section,
            "stats": json.loads(revision.stats_json) if revision.stats_json else {},
            "created_by_email": revision.author.email if revision.author else "unknown",
            "created_at": revision.created_at,
        }

    async def get_revision_diff(
        self, document_id: int, revision_id: int, company_id: int, db: AsyncSession
    ) -> dict:
        """Get diff for a specific revision (old vs new text stored in revision)."""
        doc = await self._get_document(document_id, company_id, db)

        stmt = select(DocumentRevision).where(
            DocumentRevision.id == revision_id,
            DocumentRevision.document_id == document_id,
        )
        result = await db.execute(stmt)
        revision = result.scalar_one_or_none()

        if revision is None:
            raise NotFoundException(message="Revision not found", field="revision_id")

        if not revision.old_text or not revision.new_text:
            raise BadRequestException(
                message="Revision text not available (old_text/new_text not stored)"
            )

        diff_result = await self._diff_svc.generate_diff(revision.old_text, revision.new_text)

        return {
            "old_text": revision.old_text,
            "new_text": revision.new_text,
            "diff": diff_result,
        }

    # ── Internal helpers ──────────────────────────────────────────────

    async def _get_document(self, document_id: int, company_id: int, db: AsyncSession) -> Document:
        stmt = select(Document).where(
            Document.id == document_id,
            Document.company_id == company_id,
        )
        result = await db.execute(stmt)
        doc = result.scalar_one_or_none()
        if doc is None:
            raise NotFoundException(message="Document not found", field="document_id")
        return doc

    async def _get_document_text(self, doc: Document) -> str:
        """Get the full text of a document from storage.

        Uses the latest version's file_path to retrieve text.
        Falls back to DocumentVersion.full_text if available.
        """
        # Get latest version
        if not doc.versions:
            return ""

        latest = max(doc.versions, key=lambda v: v.version_number)

        # Try full_text first
        if latest.full_text:
            return latest.full_text

        # Fall back to reading file + extracting text
        try:
            file_bytes = await storage.get(latest.file_path)
            # Use parser to extract text from docx/pdf
            from app.services.parser_service import parser_service
            text = await parser_service.extract_text(file_bytes, latest.file_type)
            return text or ""
        except Exception as e:
            logger.warning(f"Failed to extract text from file: {e}")
            return ""

    async def _save_document_text(self, doc: Document, new_text: str) -> None:
        """Update the document's full_text on the latest version.

        Actual file overwrite is deferred to Phase 7 (versioning).
        For now we update only the full_text field.
        """
        if doc.versions:
            latest = max(doc.versions, key=lambda v: v.version_number)
            latest.full_text = new_text
            # In Phase 7: also rebuild the .docx file and overwrite storage

    def _build_revision_prompt(
        self, old_text: str, comment: str, target_section: Optional[str]
    ) -> str:
        parts = ["Исходный текст документа:\n", old_text, "\n\n"]

        parts.append("Замечание пользователя:\n")
        parts.append(comment)

        if target_section:
            parts.append(f"\n\nЦелевой раздел: {target_section}")
            parts.append("\n\nВнеси правки только в указанный раздел. Остальные разделы оставь без изменений.")

        parts.append("\n\nВерни ПОЛНЫЙ текст документа целиком с внесёнными правками.")

        return "".join(parts)

    def _clean_llm_response(self, text: str) -> str:
        """Strip markdown code fences that LLM might add."""
        text = text.strip()
        if text.startswith("```"):
            # Find first newline after opening ```
            first_nl = text.find("\n")
            if first_nl != -1:
                text = text[first_nl + 1:]
            else:
                text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        return text.strip()


# Singleton
revision_service = RevisionService()
```

### 5.2 DiffService

Новый файл: `backend/app/services/diff_service.py`

```python
"""
Diff service — generates diffs between old and new document text.
"""

import difflib
import re
from typing import Optional

from app.schemas.revision import DiffResult, DiffStats


class DiffService:
    """Generates structured diffs between two text versions."""

    async def generate_diff(self, old_text: str, new_text: str) -> DiffResult:
        """Generate unified diff, HTML diff, and stats."""
        old_lines = old_text.splitlines(keepends=True)
        new_lines = new_text.splitlines(keepends=True)

        # Unified diff
        unified = "".join(difflib.unified_diff(
            old_lines,
            new_lines,
            fromfile="old",
            tofile="new",
            n=3,
        ))

        # HTML diff
        html_diff = difflib.HtmlDiff(tabsize=2).make_table(
            old_lines,
            new_lines,
            context=True,
            numlines=3,
        )

        # Stats
        stats = self._compute_stats(unified)

        return DiffResult(
            unified_diff=unified,
            html_diff=html_diff,
            stats=stats,
        )

    def _compute_stats(self, unified_diff: str) -> DiffStats:
        """Count added, removed, changed lines from unified diff."""
        added = 0
        removed = 0
        changed = 0

        for line in unified_diff.splitlines():
            if line.startswith("+++") or line.startswith("---") or line.startswith("@@"):
                continue
            if line.startswith("+") and not line.startswith("+++"):
                added += 1
            elif line.startswith("-") and not line.startswith("---"):
                removed += 1
            # Changed lines = min(added, removed) per hunk, approximate:
            # Actually we count changed as hunk lines where both +/- appear
            # Simpler: changed = min(added, removed) / 2

        changed = min(added, removed)
        # Remove from added/removed the part that's actually "changed"
        added_only = added - changed
        removed_only = removed - changed

        return DiffStats(
            added=added_only,
            removed=removed_only,
            changed=changed,
        )


# Singleton
diff_service = DiffService()
```

### 5.3 Обработка errors

- `LLM_ERROR` (500) — если LLM вернула пустой ответ или ошибка вызова.
- `DOCUMENT_ARCHIVED` (400) — если документ в архиве.
- `NO_CONTENT` (400) — если у документа нет текста.

Добавить новые exception classes при необходимости.

### 5.4 Обновление `__init__` модели

Добавить `DocumentRevision` в `backend/app/models/__init__.py`:

```python
from app.models.document_revision import DocumentRevision
```

Добавить `DocumentRevision` в `__all__`.

---

## 6. API Router

Новый файл: `backend/app/api/v1/revisions.py`

```python
"""
API routes for document revision operations.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_active_company, require_editor
from app.database import get_db
from app.models.user import User
from app.schemas.revision import (
    ReviseRequest,
    ReviseResponse,
    RevisionHistoryItem,
    RevisionDetail,
    RevisionDiffResponse,
)
from app.services.revision_service import revision_service

router = APIRouter(prefix="/documents/{document_id}/revisions", tags=["revisions"])


@router.post("/revise", response_model=ReviseResponse)
async def revise_document(
    document_id: int,
    body: ReviseRequest,
    current_user: User = Depends(require_editor),
    db: AsyncSession = Depends(get_db),
):
    """Revise a document based on user feedback via LLM."""
    return await revision_service.revise_document(
        document_id=document_id,
        comment=body.comment,
        target_section=body.target_section,
        current_user=current_user,
        db=db,
    )


@router.get("", response_model=list[RevisionHistoryItem])
async def get_revision_history(
    document_id: int,
    current_user: User = Depends(require_active_company),
    db: AsyncSession = Depends(get_db),
):
    """Get revision history for a document."""
    return await revision_service.get_revision_history(
        document_id=document_id,
        company_id=current_user.active_company_id,
        db=db,
    )


@router.get("/{revision_id}", response_model=RevisionDetail)
async def get_revision_detail(
    document_id: int,
    revision_id: int,
    current_user: User = Depends(require_active_company),
    db: AsyncSession = Depends(get_db),
):
    """Get details of a specific revision."""
    return await revision_service.get_revision_detail(
        document_id=document_id,
        revision_id=revision_id,
        company_id=current_user.active_company_id,
        db=db,
    )


@router.get("/{revision_id}/diff", response_model=RevisionDiffResponse)
async def get_revision_diff(
    document_id: int,
    revision_id: int,
    current_user: User = Depends(require_active_company),
    db: AsyncSession = Depends(get_db),
):
    """Get diff for a specific revision."""
    return await revision_service.get_revision_diff(
        document_id=document_id,
        revision_id=revision_id,
        company_id=current_user.active_company_id,
        db=db,
    )
```

Подключить в `backend/app/api/v1/router.py`:

```python
from app.api.v1.revisions import router as revisions_router
router.include_router(revisions_router)
```

---

## 7. Frontend

### 7.1 API слой

Добавить в `frontend/src/api/documents.ts`:

```typescript
// ── Revision types ─────────────────────────────────────────────────

export interface DiffStats {
  added: number
  removed: number
  changed: number
}

export interface DiffResult {
  unified_diff: string
  html_diff: string
  stats: DiffStats
}

export interface ReviseRequest {
  comment: string
  target_section?: string
}

export interface ReviseResponse {
  document_id: number
  old_text: string
  new_text: string
  diff: DiffResult
  revision_id: number | null
  changed: boolean
}

export interface RevisionHistoryItem {
  id: number
  comment: string
  target_section: string | null
  stats: DiffStats
  created_by_email: string
  created_at: string
}

export interface RevisionDetail extends RevisionHistoryItem {
  document_id: number
  old_text?: string
  new_text?: string
}

export interface RevisionDiffResponse {
  old_text: string
  new_text: string
  diff: DiffResult
}

// ── API functions ──────────────────────────────────────────────────

export async function reviseDocument(
  documentId: number,
  data: ReviseRequest
): Promise<ReviseResponse> {
  const response = await apiClient.post(`/documents/${documentId}/revisions/revise`, data)
  return response.data
}

export async function getRevisionHistory(
  documentId: number
): Promise<RevisionHistoryItem[]> {
  const response = await apiClient.get(`/documents/${documentId}/revisions`)
  return response.data
}

export async function getRevisionDetail(
  documentId: number,
  revisionId: number
): Promise<RevisionDetail> {
  const response = await apiClient.get(`/documents/${documentId}/revisions/${revisionId}`)
  return response.data
}

export async function getRevisionDiff(
  documentId: number,
  revisionId: number
): Promise<RevisionDiffResponse> {
  const response = await apiClient.get(`/documents/${documentId}/revisions/${revisionId}/diff`)
  return response.data
}
```

### 7.2 ReviseModal компонент

Новый файл: `frontend/src/components/ReviseModal.tsx`

**Props:**
```typescript
interface ReviseModalProps {
  documentId: number
  open: boolean
  onClose: () => void
  onSuccess: (response: ReviseResponse) => void
}
```

**Структура:**
- Ant Design `Modal` (title: «Внести правки»)
- Поле: `TextArea` для замечания (обязательное, min 10 символов)
- Поле: `Input` для «Целевой раздел» (опционально, placeholder: «Например: Раздел 3 или 4.2»)
- Кнопка «Отправить» (type=primary, loading state)
- Валидация на клиенте: comment не пустой и >= 10 символов
- После успеха: `onSuccess(response)` + закрыть модалку

```typescript
// ── Примерная реализация ──

const ReviseModal: React.FC<ReviseModalProps> = ({ documentId, open, onClose, onSuccess }) => {
  const [comment, setComment] = useState('')
  const [targetSection, setTargetSection] = useState('')
  const [submitting, setSubmitting] = useState(false)

  const handleSubmit = async () => {
    if (!comment || comment.trim().length < 10) {
      message.warning('Замечание должно содержать минимум 10 символов')
      return
    }
    setSubmitting(true)
    try {
      const response = await reviseDocument(documentId, {
        comment: comment.trim(),
        target_section: targetSection.trim() || undefined,
      })
      message.success('Правки внесены')
      onSuccess(response)
      onClose()
    } catch (err: any) {
      const msg = err?.response?.data?.detail?.message || err?.message || 'Ошибка при внесении правок'
      message.error(msg)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Modal
      title="Внести правки"
      open={open}
      onCancel={onClose}
      onOk={handleSubmit}
      confirmLoading={submitting}
      okText="Отправить"
      cancelText="Отмена"
      destroyOnClose
    >
      <Space direction="vertical" style={{ width: '100%' }} size="middle">
        <div>
          <Text strong>Замечание <span style={{ color: 'red' }}>*</span></Text>
          <TextArea
            rows={5}
            value={comment}
            onChange={e => setComment(e.target.value)}
            placeholder="Опишите, что нужно изменить в документе..."
            showCount
            maxLength={5000}
            style={{ marginTop: 4 }}
          />
        </div>
        <div>
          <Text strong>Целевой раздел (опционально)</Text>
          <Input
            value={targetSection}
            onChange={e => setTargetSection(e.target.value)}
            placeholder="Например: Раздел 3 или 4.2"
            style={{ marginTop: 4 }}
          />
        </div>
      </Space>
    </Modal>
  )
}
```

### 7.3 DiffView компонент

Новый файл: `frontend/src/components/DiffView.tsx`

**Вариант A (использовать `react-diff-viewer-continued`):**
```typescript
import ReactDiffViewer from 'react-diff-viewer-continued'
```

**Props:**
```typescript
interface DiffViewProps {
  oldValue: string
  newValue: string
  showDiffOnly?: boolean
  extraLinesSurroundingDiff?: number
  leftTitle?: string
  rightTitle?: string
  onClose?: () => void
  stats?: DiffStats
}
```

**Структура:**
- Контейнер с заголовком «Изменения в документе»
- Сводка: «+N строк, -M строк, изменено K»
- ReactDiffViewer в splitView mode (или unified, обсуждаемо)
- Кнопка «Закрыть» или «Продолжить редактирование»
- Интеграция: можно показывать как full-page overlay или внутри Modal

**Вариант B (использовать Ant Design):**  
Если `react-diff-viewer-continued` вызывает проблемы, можно использовать `Typography.Paragraph` с dangerouslySetInnerHTML для `html_diff`, полученного с backend. Но предпочтительнее вариант A, т.к. библиотека уже есть в зависимостях.

```typescript
// ── Примерная реализация ──

import ReactDiffViewer from 'react-diff-viewer-continued'

const DiffView: React.FC<DiffViewProps> = ({
  oldValue,
  newValue,
  showDiffOnly = false,
  extraLinesSurroundingDiff = 3,
  leftTitle = 'Старая версия',
  rightTitle = 'Новая версия',
  onClose,
  stats,
}) => {
  return (
    <div style={{ padding: 16 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <Title level={4}>Изменения в документе</Title>
        {onClose && (
          <Button onClick={onClose}>Закрыть</Button>
        )}
      </div>

      {stats && (
        <Space style={{ marginBottom: 16 }}>
          <Tag color="green">+{stats.added} строк</Tag>
          <Tag color="red">-{stats.removed} строк</Tag>
          {stats.changed > 0 && (
            <Tag color="orange">изменено {stats.changed}</Tag>
          )}
        </Space>
      )}

      <div style={{ border: '1px solid #d9d9d9', borderRadius: 4, overflow: 'hidden' }}>
        <ReactDiffViewer
          oldValue={oldValue}
          newValue={newValue}
          splitView={true}
          leftTitle={leftTitle}
          rightTitle={rightTitle}
          showDiffOnly={showDiffOnly}
          extraLinesSurroundingDiff={extraLinesSurroundingDiff}
          styles={{
            diffContainer: { maxHeight: '70vh', overflow: 'auto' },
          }}
        />
      </div>
    </div>
  )
}
```

### 7.4 Интеграция в DocumentDetailPage

1. **Добавить кнопку «Внести правки»** в хедер страницы (рядом с кнопками статуса), видна для editor+ и не-archived:

```tsx
{canEdit && doc.status !== 'archived' && (
  <Button
    type="primary"
    icon={<EditOutlined />}
    onClick={() => setReviseModalOpen(true)}
  >
    Внести правки
  </Button>
)}
```

2. **Добавить стейт:**
```typescript
const [reviseModalOpen, setReviseModalOpen] = useState(false)
const [diffViewData, setDiffViewData] = useState<ReviseResponse | null>(null)
```

3. **Добавить вкладку «Ревизии»** после «Изменений»:

```tsx
{
  key: 'revisions',
  label: `Ревизии (${revisionsCount})`,
  children: <RevisionsTab documentId={documentId} />,
}
```

4. **Создать подкомпонент `RevisionsTab`** (или встроить в страницу):

```tsx
// В revisions tab:
// - Таблица с колонками: Дата, Комментарий, Раздел, Изменено (+N/-M), Кто
// - При клике на строку -> открыть DiffView с diff этой ревизии
```

5. **После успешной ревизии** (из ReviseModal):
- Закрыть модалку
- Установить `setDiffViewData(response)`
- Показать `DiffView` как overlay (или в модальном окне, или как дополнительный блок на странице)

**Рекомендуемый UX flow:**
1. Пользователь нажимает «Внести правки» → открывается `ReviseModal`
2. Пользователь вводит замечание и (опционально) раздел → нажимает «Отправить»
3. Backend вызывает LLM, сохраняет новую версию, возвращает diff
4. Модалка закрывается, на странице открывается `DiffView` (как overlay или в Modal)
5. Пользователь видит diff, может закрыть его
6. Страница автоматически обновляется (refresh документа)

### 7.5 TypeScript типы

Добавить в `frontend/src/types/index.ts`:

```typescript
// ── Revision types ──

export interface DiffStats {
  added: number
  removed: number
  changed: number
}

export interface DiffResult {
  unified_diff: string
  html_diff: string
  stats: DiffStats
}
```

---

## 8. Модель DocumentRevision (полный код)

Новый файл: `backend/app/models/document_revision.py`

```python
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.document import Document
    from app.models.user import User


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class DocumentRevision(Base):
    __tablename__ = "document_revisions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    document_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("documents.id", ondelete="CASCADE"), index=True, nullable=False
    )
    comment: Mapped[str] = mapped_column(Text, nullable=False)
    target_section: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    old_text_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    new_text_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    old_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    new_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    stats_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)

    document: Mapped["Document"] = relationship("Document", back_populates="revisions", lazy="selectin")
    author: Mapped[Optional["User"]] = relationship("User", lazy="selectin")

    def __repr__(self) -> str:
        return f"<DocumentRevision(id={self.id}, doc_id={self.document_id})>"
```

---

## 9. Acceptance Criteria

1. **Пользователь пишет «добавь раздел про ответственность»**
   - → LLM добавляет раздел
   - → Diff показывает +N строк
   - → Новая ревизия создаётся
   - → Файл документа обновляется

2. **Пользователь пишет «в разделе 4.2 исправь срок с 5 на 10 дней»**
   - → Меняется только указанный раздел
   - → Diff показывает изменённые строки
   - → Остальные разделы не затрагиваются

3. **Diff отображается с подсветкой изменений (красный/зелёный)**
   - → `react-diff-viewer-continued` корректно показывает split view
   - → Сводка (+N/-M) отображается над diff

4. **Можно посмотреть историю ревизий**
   - → Вкладка «Ревизии» показывает таблицу
   - → Клик по строке открывает diff для этой ревизии

5. **Старый текст не сохраняется как отдельная версия**
   - → Файл перезаписан
   - → Старый файл отсутствует в storage
   - → Старый текст есть только в `old_text` поля `DocumentRevision`

6. **Если LLM не изменяет документ — diff пустой, ревизия не создаётся**
   - → `changed: false` в ответе
   - → `revision_id: null`
   - → Новая запись в `document_revisions` НЕ создаётся

7. **Безопасность:**
   - → Endpoint доступен только editor+
   - → Проверка принадлежности документа к компании пользователя
   - → Архивные документы нельзя рецензировать

---

## 10. Risks & Assumptions

### 10.1 Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| LLM меняет не то, что просили | Medium | Промпт с точным цитированием + низкая температура (0.2). Пользователь видит diff сразу после ревизии и может проверить |
| LLM возвращает неполный документ (обрывается) | High | Увеличить max_tokens до 32000; проверять целостность в `_clean_llm_response`; добавить fallback |
| LLM возвращает тот же текст (пустая ревизия) | Low | Проверка `changed: false` — ревизия не создаётся |
| Большой diff (>10K строк) тяжело визуализировать | Medium | `react-diff-viewer` использует виртуализацию; ограничить высоту контейнера (70vh) |
| Хранение `old_text`/`new_text` в БД увеличивает размер | Medium | Тексты могут быть большими (до 100KB+). Ожидаемый размер: 100 ревизий × 200KB = 20MB — приемлемо для SQLite |
| LLM возвращает JSON вместо plain text | Medium | `_clean_llm_response` не обработает JSON. Нужно проверять и пытаться extract content |
| Устаревший `storage_service.get_text` не найден | Low | В коде нет прямого `get_text`, но есть `storage.get()`. Используем fallback через parser_service |

### 10.2 Assumptions

- **Старый файл перезаписывается** — версионность будет в Фазе 7.
- **Diff генерируется на backend** через `difflib` и отображается на frontend через `react-diff-viewer-continued`.
- **LLM должна вернуть полный текст документа**, не только изменения.
- **Размер текста документа** не превышает ~100K символов (иначе проблемы с хранением в `Text` поле SQLite, но SQLite Text может хранить до 1 ГБ).
- **`storage_service`** предоставляет метод получения текста (через `DocumentVersion.full_text` или через `parser_service.extract_text`).
- **Ollama** доступна на момент вызова; если нет — ошибка 503.

---

## 11. Порядок реализации (Steps)

### Step 1: Backend — Model
- [ ] Создать `backend/app/models/document_revision.py`
- [ ] Добавить `revisions` relationship в `Document`
- [ ] Обновить `models/__init__.py`
- [ ] Создать alembic миграцию

### Step 2: Backend — Schemas
- [ ] Создать `backend/app/schemas/revision.py`
- [ ] Определить все Pydantic модели (ReviseRequest, ReviseResponse, DiffResult, etc.)

### Step 3: Backend — Services
- [ ] Создать `backend/app/services/diff_service.py` (DiffService)
- [ ] Создать `backend/app/services/revision_service.py` (RevisionService)
- [ ] Добавить обработку ошибок (LLM_ERROR, DOCUMENT_ARCHIVED, NO_CONTENT)

### Step 4: Backend — API Router
- [ ] Создать `backend/app/api/v1/revisions.py`
- [ ] Подключить в `router.py`
- [ ] Добавить проверки доступа (require_editor / require_active_company)

### Step 5: Frontend — API и типы
- [ ] Обновить `frontend/src/types/index.ts` (DiffStats, DiffResult)
- [ ] Добавить API функции в `frontend/src/api/documents.ts`

### Step 6: Frontend — ReviseModal
- [ ] Создать `frontend/src/components/ReviseModal.tsx`
- [ ] Интегрировать в `DocumentDetailPage.tsx`

### Step 7: Frontend — DiffView
- [ ] Создать `frontend/src/components/DiffView.tsx`
- [ ] Использовать `react-diff-viewer-continued`

### Step 8: Frontend — RevisionsTab
- [ ] Создать вкладку «Ревизии» на странице документа
- [ ] Таблица с историей ревизий
- [ ] Клик по строке → DiffView для исторической ревизии

### Step 9: Integration & Tests
- [ ] Написать backend тесты (pytest) для RevisionService
- [ ] Написать e2e тест (ревизия → проверка diff → проверка истории)
- [ ] Проверить миграцию (alembic upgrade head)
- [ ] Проверить frontend сборку (npm run build)

### Step 10: Документация
- [ ] Обновить DESIGN.md (если необходимо)
- [ ] Обновить openapi.json

---

## 12. Открытые вопросы

1. **Хранить ли `old_text` и `new_text` в `DocumentRevision`?**
   - ✅ Решение: да, хранить. Это позволяет показывать diff для любой исторической ревизии без повторного вызова LLM. Риск роста БД низкий.

2. **Как получать текст документа, если нет `DocumentVersion.full_text`?**
   - Использовать `parser_service.extract_text()` для чтения из файла .docx/.pdf.

3. **Показывать diff сразу после ревизии или только на отдельной вкладке?**
   - ✅ Решение: сразу после ревизии показывать `DiffView` (overlay или modal) + дублировать в историю ревизий.

4. **Нужна ли перегенерация .docx файла?**
   - В Фазе 6 — нет, только обновление `full_text`. В Фазе 7 (версионность) — полная перегенерация.

5. **Как обрабатывать случай, когда замечание относится к документу в статусе `approved`?**
   - Разрешено (editor+ может рецензировать approved документы). Статус не меняется.

6. **Можно ли рецензировать документы других компаний?**
   - Нет, только документы своей active_company.

---

## 13. Приложение: Изменения в зависимостях

### Backend
- Нет новых зависимостей (difflib — стандартная библиотека Python)

### Frontend
- `react-diff-viewer-continued` — **уже есть** в package.json (^4.2.2)
- `diff` (^9.0.0) — **уже есть** в package.json (для потенциального использования)
- Новых npm-пакетов не требуется
