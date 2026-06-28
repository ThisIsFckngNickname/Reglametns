# Phase 7 — Версионность документов (Versioning)

> **Статус:** Черновик  
> **Дата:** 2026-06-28  
> **Автор:** SA  
> **Зависимости:** Фаза 6 (Revision), Phase 4 (Analysis Pipeline)

---

## 1. Objective

Обеспечить полноценное управление версиями документов: каждая итерация документа (загрузка, генерация, ревизия) создаёт новую версию с возможностью просмотра, скачивания, отката и привязки анализа к конкретной версии.

### Ключевые изменения относительно текущего состояния

| Аспект | Сейчас | После Фазы 7 |
|--------|--------|--------------|
| Структура хранения файлов | `{company_id}/{doc_id}/{version_number}_{timestamp}.ext` | `{company_id}/{doc_id}/v{version_number}/filename.ext` |
| Привязка анализа | `DocumentAnalysis.document_version_id` опционально, не используется | Обязательная привязка к версии |
| Восстановление версии | Нет | Полноценный restore (создание новой версии из контента выбранной) |
| Diff между версиями | Только в контексте ревизий (old/new text) | Diff между файлами любых двух версий |
| Путь старых файлов | Единый каталог | Перенос в `v1/` при миграции |

---

## 2. Data Model

### 2.1 DocumentVersion (существующая модель — ДОПОЛНЕНИЯ)

**Текущая модель** уже имеет все необходимые поля. Требуется **добавить**:

```python
# backend/app/models/document_version.py

class DocumentVersion(Base):
    __tablename__ = "document_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    document_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("documents.id", ondelete="CASCADE"), index=True, nullable=False
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    file_type: Mapped[str] = mapped_column(String(10), nullable=False)       # docx / pdf
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    version_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True) # комментарий
    full_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)     # извлечённый текст
    uploaded_by: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)

    # ── Relationships ──
    document: Mapped["Document"] = relationship("Document", back_populates="versions")
    uploader: Mapped[Optional["User"]] = relationship("User", lazy="selectin")
    sections: Mapped[list["DocumentSection"]] = relationship(
        "DocumentSection", back_populates="version",
        cascade="all, delete-orphan", lazy="selectin",
    )
    tables: Mapped[list["DocumentTable"]] = relationship(
        "DocumentTable", back_populates="version",
        cascade="all, delete-orphan", lazy="selectin",
    )
```

**Добавить:**
- `file_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)` — SHA-256 содержимого файла
- `UniqueConstraint("document_id", "version_number")` — защита от дублирования номеров версий

```python
from sqlalchemy import UniqueConstraint

class DocumentVersion(Base):
    __table_args__ = (
        UniqueConstraint("document_id", "version_number", name="uq_doc_version"),
    )
    # ... остальные поля
```

### 2.2 Document — изменения

**Ничего не менять.** Текущая модель уже имеет:
- `versions` relationship (cascade delete)
- `analyses` relationship
- `revisions` relationship

Не добавляем `current_version_id` FK — текущая версия определяется как `max(version_number)`.

### 2.3 DocumentAnalysis — существующая привязка

`DocumentAnalysis` уже имеет поле `document_version_id`:

```python
class DocumentAnalysis(Base):
    # ...
    document_version_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("document_versions.id", ondelete="SET NULL"), nullable=True
    )
    # ...
    version: Mapped[Optional["DocumentVersion"]] = relationship("DocumentVersion", lazy="selectin")
```

**Требуется:** сделать `document_version_id` обязательным (NOT NULL) для новых анализов.  
**Миграция:** для существующих анализов — проставить `document_version_id` на основе latest version документа на момент анализа (по created_at).

### 2.4 Миграция Alembic

```bash
alembic revision --autogenerate -m "phase7_versioning_enhancements"
```

**Изменения:**
1. Добавить `file_hash` в `DocumentVersion`
2. Добавить `UniqueConstraint("document_id", "version_number")` в `DocumentVersion`
3. Сделать `DocumentAnalysis.document_version_id` NOT NULL (с миграцией данных)
4. Обновить индексы при необходимости

---

## 3. Storage Paths

### 3.1 Новый формат пути

```
storage/
  {company_id}/
    {document_id}/
      v{version_number}/
        filename.ext
```

### 3.2 Пример

```
storage/1/42/v1/Положение_о_ГСМ.docx
storage/1/42/v2/Положение_о_ГСМ_v2.docx
storage/1/42/v3/Положение_о_ГСМ_v3.docx
```

### 3.3 Изменения в StorageService

Метод `save()` должен формировать путь в новом формате:

```python
async def save(
    self, file: UploadFile, company_id: int, document_id: int, version_number: int
) -> str:
    ext = self._get_extension(file.filename or "document")
    filename = file.filename or f"document_v{version_number}{ext}"
    relative_dir = os.path.join(str(company_id), str(document_id), f"v{version_number}")
    relative_path = os.path.join(relative_dir, filename)
    relative_path = relative_path.replace("\\", "/")
    content = await file.read()
    await get_storage().save(relative_path, content)
    return relative_path
```

### 3.4 Обратная совместимость

Для чтения старых файлов (без `v1/` в пути) — fallback:

```python
async def get(self, file_path: str) -> bytes:
    storage = get_storage()
    if not await storage.exists(file_path):
        # Fallback: попробовать подставить v1/
        if "/v1/" not in file_path and "/" in file_path:
            parts = file_path.split("/")
            # старый формат: {company_id}/{doc_id}/{version_number}_{timestamp}.ext
            # новый формат: {company_id}/{doc_id}/v{version_number}/filename.ext
            # Пробуем оба варианта
            alt_path = self._try_old_path(file_path)
            if alt_path and await storage.exists(alt_path):
                return await storage.read(alt_path)
        raise FileNotFoundError(f"File not found: {file_path}")
    return await storage.read(file_path)
```

---

## 4. API Endpoints

Все эндпоинты монтируются в существующий `router.py`.

### 4.1 GET /api/v1/documents/{id}/versions

**Существующий** — обновить формат ответа.

**Response (200):**
```json
[
  {
    "id": 1,
    "version_number": 1,
    "file_type": "docx",
    "file_size": 24576,
    "version_notes": "Первоначальная версия",
    "uploaded_by": {"id": 1, "email": "user@example.com"},
    "created_at": "2026-06-28T12:00:00",
    "is_current": true
  },
  {
    "id": 2,
    "version_number": 2,
    "file_type": "docx",
    "file_size": 25123,
    "version_notes": "Добавлен раздел 5",
    "uploaded_by": {"id": 1, "email": "user@example.com"},
    "created_at": "2026-06-28T14:00:00",
    "is_current": false
  }
]
```

**Доступ:** active_company  
**Проверка:** документ принадлежит компании пользователя

### 4.2 GET /api/v1/documents/{id}/versions/{version_number}/download

**Существующий:** `/documents/versions/{version_id}/download` (по ID версии)  
**Добавить:** альтернативный эндпоинт по номеру версии.

```python
@router.get("/{document_id}/versions/{version_number}/download")
async def download_version_by_number(
    document_id: int,
    version_number: int,
    user: User = Depends(require_active_company),
    db: AsyncSession = Depends(get_db),
):
    """Download a specific version by version number."""
    # Verify document
    stmt = select(Document).where(
        Document.id == document_id,
        Document.company_id == user.active_company_id,
    )
    result = await db.execute(stmt)
    doc = result.scalar_one_or_none()
    if doc is None:
        raise NotFoundException(message="Document not found", field="document_id")

    # Get version
    ver_stmt = select(DocumentVersion).where(
        DocumentVersion.document_id == document_id,
        DocumentVersion.version_number == version_number,
    )
    ver_result = await db.execute(ver_stmt)
    version = ver_result.scalar_one_or_none()
    if version is None:
        raise NotFoundException(message="Version not found", field="version_number")

    # Read file
    try:
        file_bytes = await storage.get(version.file_path)
    except FileNotFoundError:
        raise NotFoundException(message="File not found on disk")

    filename = f"document_v{version.version_number}.{version.file_type}"
    return StreamingResponse(
        content=iter([file_bytes]),
        media_type=version.mime_type,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length": str(len(file_bytes)),
        },
    )
```

**Существующий** (`/documents/versions/{version_id}/download`) — сохранить для обратной совместимости.

### 4.3 POST /api/v1/documents/{id}/versions

**Существующий** — без изменений. Создаёт новую версию через `DocumentUploadService.create_version()`.

### 4.4 POST /api/v1/documents/{id}/versions/{version_number}/restore

**Новый эндпоинт.**

**Request:** пустое тело (или опциональный `comment`)

**Response (201):**
```json
{
  "id": 3,
  "document_id": 42,
  "version_number": 3,
  "file_type": "docx",
  "file_size": 24576,
  "version_notes": "Восстановлено из версии 1",
  "created_at": "2026-06-28T15:00:00"
}
```

**Логика:**
1. Найти версию с `document_id` + `version_number`
2. Прочитать её файл из storage
3. Создать **новую** версию (version_number = max + 1) с контентом выбранной
4. Установить `version_notes = "Восстановлено из версии {N}"`
5. Пересохранить файл в `v{new_version}/`
6. Обновить `full_text` и `sections` из старой версии (скопировать)
7. Вернуть новую версию

**Доступ:** editor+

### 4.5 GET /api/v1/documents/{id}/versions/{v1}/diff/{v2}

**Новый эндпоинт** — diff между двумя версиями.

**Response (200):**
```json
{
  "from_version": 1,
  "to_version": 2,
  "diff": {
    "unified_diff": "--- \n+++ \n@@ -1,5 +1,8 @@ ...",
    "html_diff": "<table class=\"diff\">...</table>",
    "stats": {
      "added": 15,
      "removed": 3,
      "changed": 5
    }
  }
}
```

**Логика:**
1. Получить `full_text` обеих версий (или извлечь из файлов через parser_service)
2. Использовать `DiffService.generate_diff()` (из Phase 6)
3. Вернуть результат

**Доступ:** active_company

### 4.6 GET /api/v1/documents/{id}/analyses?version={version}

**Существующий** эндпоинт — добавить опциональный query-параметр `version`.

**Логика:**
- Если `version` передан — фильтровать анализы по `document_version_id` (через `version_number` → `version_id`)
- Если `version` не передан — вернуть все анализы документа (как сейчас)

**Проверка:** active_company

### 4.7 Обновление существующих эндпоинтов

#### POST /api/v1/documents/upload
При создании документа теперь явно указываем `version_number = 1` и сохраняем в `v1/`.

#### POST /api/v1/documents/{id}/revise
При ревизии должна создаваться **новая версия** документа (а не перезаписываться `full_text` текущей):
1. Получить текущий текст из latest version
2. Вызвать LLM → получить новый текст
3. Создать **новую** версию (v+1)
4. Сохранить `full_text` новой версии
5. Создать `DocumentRevision` со ссылкой на новую версию

---

## 5. Services

### 5.1 VersionService (новый файл)

`backend/app/services/version_service.py`

```python
"""
VersionService — управление версиями документов.

Отвечает за:
- Создание версий
- Получение списка/конкретной версии
- Восстановление версии (restore)
- Сравнение версий (diff)
- Скачивание файла версии
"""

import logging
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundException, BadRequestException
from app.models.document import Document
from app.models.document_version import DocumentVersion
from app.models.user import User
from app.schemas.revision import DiffResult
from app.services.diff_service import diff_service
from app.services.storage_service import storage

logger = logging.getLogger(__name__)


class VersionService:
    """Service for document version management."""

    async def get_versions(
        self,
        document_id: int,
        company_id: int,
        db: AsyncSession,
    ) -> list[dict]:
        """Get all versions of a document with metadata."""
        doc = await self._get_document(document_id, company_id, db)

        stmt = (
            select(DocumentVersion)
            .where(DocumentVersion.document_id == document_id)
            .order_by(DocumentVersion.version_number.desc())
        )
        result = await db.execute(stmt)
        versions = result.scalars().all()

        # Determine current version (max version_number)
        current_version_number = max(
            (v.version_number for v in versions), default=None
        )

        return [
            {
                "id": v.id,
                "version_number": v.version_number,
                "file_type": v.file_type,
                "file_size": v.file_size,
                "version_notes": v.version_notes,
                "uploaded_by": {
                    "id": v.uploader.id,
                    "email": v.uploader.email,
                } if v.uploader else None,
                "created_at": v.created_at.isoformat(),
                "is_current": v.version_number == current_version_number,
            }
            for v in versions
        ]

    async def get_version(
        self,
        document_id: int,
        version_number: int,
        company_id: int,
        db: AsyncSession,
    ) -> DocumentVersion:
        """Get a specific version by number."""
        await self._get_document(document_id, company_id, db)

        stmt = select(DocumentVersion).where(
            DocumentVersion.document_id == document_id,
            DocumentVersion.version_number == version_number,
        )
        result = await db.execute(stmt)
        version = result.scalar_one_or_none()

        if version is None:
            raise NotFoundException(
                message=f"Version {version_number} not found",
                field="version_number",
            )

        return version

    async def create_version(
        self,
        document_id: int,
        file_content: bytes,
        filename: str,
        file_type: str,
        mime_type: str,
        file_size: int,
        author_id: int,
        company_id: int,
        db: AsyncSession,
        comment: Optional[str] = None,
    ) -> DocumentVersion:
        """Create a new version for a document.

        Flow:
        1. Verify document exists
        2. Determine version number = max + 1
        3. Save file to storage/{company_id}/{doc_id}/v{version}/
        4. Create DocumentVersion record
        5. Parse file and extract sections/full_text
        6. Return the created version
        """
        doc = await self._get_document(document_id, company_id, db)

        # Get next version number
        version_stmt = select(func.max(DocumentVersion.version_number)).where(
            DocumentVersion.document_id == document_id
        )
        version_result = await db.execute(version_stmt)
        max_version = version_result.scalar() or 0
        version_number = max_version + 1

        # Save file to storage
        from fastapi import UploadFile as FastAPIUploadFile
        from io import BytesIO

        fake_file = FastAPIUploadFile(
            filename=filename,
            file=BytesIO(file_content),
        )
        rel_path = await storage.save(fake_file, company_id, document_id, version_number)

        # Compute file hash
        import hashlib
        file_hash = hashlib.sha256(file_content).hexdigest()

        # Create version record
        version = DocumentVersion(
            document_id=document_id,
            version_number=version_number,
            file_path=rel_path,
            file_type=file_type,
            file_size=file_size,
            mime_type=mime_type,
            file_hash=file_hash,
            version_notes=comment,
            uploaded_by=author_id,
        )
        db.add(version)
        await db.flush()
        await db.refresh(version)

        # Parse file and extract sections/full_text
        try:
            from app.services.parser_service import (
                document_parser,
                enhanced_document_parser,
            )
            from app.services.document_persistence_service import (
                document_persistence_service,
            )

            full_path = await storage.get_full_path(rel_path)
            parser = enhanced_document_parser if file_type == "pdf" else document_parser
            parse_result = parser.parse(full_path, file_type)

            await document_persistence_service.persist_parse_result(
                parse_result=parse_result,
                version=version,
                document_id=document_id,
                db=db,
            )
        except Exception as e:
            logger.warning(
                f"Parse failed for version {version.id}: {e}",
                exc_info=True,
            )
            # Не проваливаем операцию — файл сохранён, парсинг опционален

        logger.info(
            f"Version {version_number} created for document {document_id}: "
            f"file={rel_path}, size={file_size}"
        )

        return version

    async def restore_version(
        self,
        document_id: int,
        version_number: int,
        author_id: int,
        company_id: int,
        db: AsyncSession,
        comment: Optional[str] = None,
    ) -> DocumentVersion:
        """Restore a previous version by creating a new version with its content.

        Flow:
        1. Get the source version
        2. Read its file from storage
        3. Create a new version (max + 1) with that content
        4. Set version_notes to "Восстановлено из версии N"
        5. Copy full_text and sections from source version
        """
        source_version = await self.get_version(
            document_id, version_number, company_id, db
        )

        # Read file
        try:
            file_bytes = await storage.get(source_version.file_path)
        except FileNotFoundError:
            raise NotFoundException(
                message=f"File for version {version_number} not found on disk",
                field="version_number",
            )

        # Create new version with restored content
        restored_comment = comment or f"Восстановлено из версии {version_number}"
        new_version = await self.create_version(
            document_id=document_id,
            file_content=file_bytes,
            filename=f"document_v{source_version.version_number}.{source_version.file_type}",
            file_type=source_version.file_type,
            mime_type=source_version.mime_type,
            file_size=source_version.file_size,
            author_id=author_id,
            company_id=company_id,
            db=db,
            comment=restored_comment,
        )

        # Copy full_text from source version (if parsing didn't populate it)
        if not new_version.full_text and source_version.full_text:
            new_version.full_text = source_version.full_text

        logger.info(
            f"Version {version_number} restored as version "
            f"{new_version.version_number} for document {document_id}"
        )

        return new_version

    async def get_version_diff(
        self,
        document_id: int,
        version_a: int,
        version_b: int,
        company_id: int,
        db: AsyncSession,
    ) -> dict:
        """Generate diff between two versions."""
        v_a = await self.get_version(document_id, version_a, company_id, db)
        v_b = await self.get_version(document_id, version_b, company_id, db)

        # Get full_text for both versions
        text_a = await self._get_version_text(v_a)
        text_b = await self._get_version_text(v_b)

        if not text_a and not text_b:
            raise BadRequestException(
                message="Neither version has extractable text content"
            )

        diff_result = diff_service.generate_diff(text_a or "", text_b or "")

        return {
            "from_version": version_a,
            "to_version": version_b,
            "diff": diff_result,
        }

    async def download_version(
        self,
        document_id: int,
        version_number: int,
        company_id: int,
        db: AsyncSession,
    ) -> tuple[bytes, str, str]:
        """Get file content, filename, and mime type for download."""
        version = await self.get_version(document_id, version_number, company_id, db)

        try:
            file_bytes = await storage.get(version.file_path)
        except FileNotFoundError:
            raise NotFoundException(
                message=f"File for version {version_number} not found on disk",
                field="version_number",
            )

        filename = f"document_v{version.version_number}.{version.file_type}"
        return file_bytes, filename, version.mime_type

    # ── Internal helpers ──────────────────────────────────────────────

    async def _get_document(
        self, document_id: int, company_id: int, db: AsyncSession
    ) -> Document:
        """Verify document exists and belongs to company."""
        stmt = select(Document).where(
            Document.id == document_id,
            Document.company_id == company_id,
        )
        result = await db.execute(stmt)
        doc = result.scalar_one_or_none()
        if doc is None:
            raise NotFoundException(
                message="Document not found",
                field="document_id",
            )
        return doc

    async def _get_version_text(self, version: DocumentVersion) -> Optional[str]:
        """Get full text from a version, extracting from file if needed."""
        if version.full_text:
            return version.full_text

        try:
            file_bytes = await storage.get(version.file_path)
            from app.services.parser_service import parser_service
            text = await parser_service.extract_text(file_bytes, version.file_type)
            return text or None
        except Exception as e:
            logger.warning(f"Failed to extract text from version {version.id}: {e}")
            return None


# Singleton
version_service = VersionService()
```

### 5.2 Изменения в DocumentUploadService

При загрузке нового документа:
- Использовать новый формат пути (`v1/`)
- Убедиться, что `version_number = 1`
- Сохранить `file_hash`

При создании версии (`create_version`):
- Использовать `VersionService.create_version()` или дублировать логику

### 5.3 Изменения в DocumentUpdateService

- `_trigger_analysis_pipeline`: передавать `document_version_id` при запуске анализа
- `hard_delete_document`: удалять файлы из storage по новому формату пути (уже есть, проверить)

### 5.4 Изменения в RevisionService (Phase 6)

**Текущее поведение:** ревизия перезаписывает `full_text` в latest version.  
**Новое поведение:** ревизия создаёт **новую версию** документа.

```python
async def _save_document_text(self, doc: Document, new_text: str) -> None:
    """Create a new version with the revised text.

    Override: вместо обновления full_text последней версии,
    создаём новую версию документа.
    """
    # TODO: Phase 7 — create new version
    # 1. Get latest version's file_path
    # 2. Generate new .docx from new_text
    # 3. Call VersionService.create_version() with the new file
    # 4. Return the new version

    # Пока оставляем старую логику (заглушка)
    if doc.versions:
        latest = max(doc.versions, key=lambda v: v.version_number)
        latest.full_text = new_text
```

**В Phase 7** раскомментировать TODO и реализовать создание новой версии.

### 5.5 Изменения в AnalysisPipelineService

При создании `DocumentAnalysis` записи:
- Убедиться, что `document_version_id` проставляется (уже есть)
- В `trigger_analysis()` передавать `latest_version.id`

### 5.6 Изменения в DocumentSaverService (генерация)

При генерации документа:
- Сохранять в `v1/`
- Явно указывать `version_number = 1`
- Убедиться, что `file_hash` заполнен

### 5.7 Изменения в StorageService

Обновить метод `save()` для поддержки нового формата пути:

```python
async def save(
    self, file: UploadFile, company_id: int, document_id: int, version_number: int
) -> str:
    ext = self._get_extension(file.filename or "document")
    filename = file.filename or f"document_v{version_number}{ext}"

    relative_dir = os.path.join(str(company_id), str(document_id), f"v{version_number}")
    relative_path = os.path.join(relative_dir, filename)
    relative_path = relative_path.replace("\\", "/")

    content = await file.read()
    await get_storage().save(relative_path, content)

    return relative_path
```

---

## 6. Frontend

### 6.1 API слой

**Обновить** `frontend/src/api/documents.ts`:

```typescript
// ── Version types (Phase 7) ──────────────────────────────────────────

export interface VersionInfo {
  id: number
  version_number: number
  file_type: string
  file_size: number
  version_notes: string | null
  uploaded_by: { id: number; email: string } | null
  created_at: string
  is_current: boolean
}

export interface VersionDiffResponse {
  from_version: number
  to_version: number
  diff: DiffResult
}

// ── Version API functions ────────────────────────────────────────────

export async function getDocumentVersions(
  documentId: number
): Promise<VersionInfo[]> {
  const response = await apiClient.get(`/documents/${documentId}/versions`)
  return response.data
}

export async function downloadVersionByNumber(
  documentId: number,
  versionNumber: number
): Promise<void> {
  const response = await apiClient.get(
    `/documents/${documentId}/versions/${versionNumber}/download`,
    { responseType: 'blob' }
  )
  const filename = `document_v${versionNumber}.docx`
  const url = window.URL.createObjectURL(new Blob([response.data]))
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  window.URL.revokeObjectURL(url)
}

export async function restoreVersion(
  documentId: number,
  versionNumber: number,
  comment?: string
): Promise<VersionInfo> {
  const response = await apiClient.post(
    `/documents/${documentId}/versions/${versionNumber}/restore`,
    { comment }
  )
  return response.data
}

export async function getVersionDiff(
  documentId: number,
  versionA: number,
  versionB: number
): Promise<VersionDiffResponse> {
  const response = await apiClient.get(
    `/documents/${documentId}/versions/${versionA}/diff/${versionB}`
  )
  return response.data
}

export async function getAnalysesByVersion(
  documentId: number,
  versionNumber?: number
): Promise<AnalysisHistoryItem[]> {
  const params = versionNumber ? { version: versionNumber } : {}
  const response = await apiClient.get(
    `/documents/${documentId}/analyses`,
    { params }
  )
  return response.data
}
```

### 6.2 Обновление вкладки «Версии»

**Файл:** `frontend/src/pages/DocumentDetailPage.tsx`

**Изменения в таблице версий:**

```typescript
const versionColumns: ColumnsType<VersionInfo> = [
  {
    title: 'Версия',
    dataIndex: 'version_number',
    key: 'version_number',
    width: 80,
    render: (v: number, record: VersionInfo) => (
      record.is_current
        ? <Tag color="blue">v{v} (текущая)</Tag>
        : <Tag>v{v}</Tag>
    ),
  },
  {
    title: 'Тип',
    dataIndex: 'file_type',
    key: 'file_type',
    width: 70,
    render: (t: string) => <Tag>{t.toUpperCase()}</Tag>,
  },
  {
    title: 'Размер',
    dataIndex: 'file_size',
    key: 'file_size',
    width: 100,
    render: (s: number) => formatFileSize(s),
  },
  {
    title: 'Комментарий',
    dataIndex: 'version_notes',
    key: 'version_notes',
    ellipsis: true,
    render: (val: string | null) => val || <Text type="secondary">—</Text>,
  },
  {
    title: 'Кем создана',
    dataIndex: ['uploaded_by', 'email'],
    key: 'uploaded_by',
    width: 200,
  },
  {
    title: 'Дата',
    dataIndex: 'created_at',
    key: 'created_at',
    width: 160,
    render: (date: string) => dayjs(date).format('DD.MM.YYYY HH:mm'),
  },
  {
    title: 'Действия',
    key: 'actions',
    width: 240,
    render: (_: any, record: VersionInfo) => (
      <Space>
        <Button
          type="primary"
          size="small"
          icon={<DownloadOutlined />}
          onClick={() => handleDownloadVersion(record.version_number)}
        >
          Скачать
        </Button>
        {canEdit && !record.is_current && (
          <Popconfirm
            title="Восстановить версию?"
            description={`Будет создана новая версия с содержимым v${record.version_number}`}
            onConfirm={() => handleRestoreVersion(record.version_number)}
            okText="Восстановить"
            cancelText="Отмена"
          >
            <Button
              size="small"
              icon={<ReloadOutlined />}
            >
              Восстановить
            </Button>
          </Popconfirm>
        )}
        {/* Чекбокс для выбора версии для сравнения */}
        <Checkbox
          checked={selectedVersions.includes(record.version_number)}
          onChange={(e) => handleVersionSelect(record.version_number, e.target.checked)}
          disabled={selectedVersions.length >= 2 && !selectedVersions.includes(record.version_number)}
        />
      </Space>
    ),
  },
]
```

**Новые стейты:**
```typescript
const [selectedVersions, setSelectedVersions] = useState<number[]>([])
const [diffModalOpen, setDiffModalOpen] = useState(false)
const [versionDiff, setVersionDiff] = useState<VersionDiffResponse | null>(null)
const [diffLoading, setDiffLoading] = useState(false)
```

**Новые обработчики:**
```typescript
const handleDownloadVersion = async (versionNumber: number) => {
  try {
    await downloadVersionByNumber(documentId, versionNumber)
  } catch {
    message.error('Не удалось скачать версию')
  }
}

const handleRestoreVersion = async (versionNumber: number) => {
  try {
    await restoreVersion(documentId, versionNumber)
    message.success(`Версия v${versionNumber} восстановлена`)
    loadVersions()
    fetchDocument(documentId)
  } catch {
    message.error('Ошибка при восстановлении версии')
  }
}

const handleVersionSelect = (versionNumber: number, checked: boolean) => {
  if (checked) {
    setSelectedVersions(prev => [...prev, versionNumber].slice(-2))
  } else {
    setSelectedVersions(prev => prev.filter(v => v !== versionNumber))
  }
}

const handleCompareVersions = async () => {
  if (selectedVersions.length !== 2) {
    message.warning('Выберите две версии для сравнения')
    return
  }
  const [v1, v2] = selectedVersions.sort((a, b) => a - b)
  setDiffLoading(true)
  try {
    const result = await getVersionDiff(documentId, v1, v2)
    setVersionDiff(result)
    setDiffModalOpen(true)
  } catch {
    message.error('Ошибка при сравнении версий')
  } finally {
    setDiffLoading(false)
  }
}
```

**Кнопка «Сравнить»** (над таблицей, активна когда выбрано 2 версии):
```typescript
{selectedVersions.length === 2 && (
  <Button
    type="default"
    icon={<FileTextOutlined />}
    onClick={handleCompareVersions}
    loading={diffLoading}
    style={{ marginRight: 8 }}
  >
    Сравнить v{Math.min(...selectedVersions)} и v{Math.max(...selectedVersions)}
  </Button>
)}
```

### 6.3 Diff-вьювер между версиями

**Модальное окно** с `DiffView` (переиспользуем из Phase 6):

```typescript
<Modal
  title={`Сравнение версий v${versionDiff?.from_version} и v${versionDiff?.to_version}`}
  open={diffModalOpen}
  onCancel={() => setDiffModalOpen(false)}
  width="90%"
  style={{ top: 20 }}
  footer={[
    <Button key="close" onClick={() => setDiffModalOpen(false)}>
      Закрыть
    </Button>,
  ]}
>
  {versionDiff && (
    <DiffView
      oldValue={/* full_text from version A */}
      newValue={/* full_text from version B */}
      htmlDiff={versionDiff.diff.html_diff}
      stats={versionDiff.diff.stats}
      leftTitle={`Версия v${versionDiff.from_version}`}
      rightTitle={`Версия v${versionDiff.to_version}`}
      onClose={() => setDiffModalOpen(false)}
    />
  )}
</Modal>
```

### 6.4 Загрузка новой версии

**Уже есть** — кнопка «Создать версию» открывает Modal с Dragger.  
**Дополнительно:**
- После загрузки — переключаться на вкладку «Версии»
- Показывать прогресс загрузки (через `onProgress`)

### 6.5 Привязка анализа к версии

**На вкладке «Анализ»** добавить индикатор:
- «Анализ версии v{number}» в карточке анализа
- В историю анализов добавить колонку «Версия»

```typescript
// В таблице истории анализов
{
  title: 'Версия',
  dataIndex: 'document_version_id',
  key: 'version',
  width: 80,
  render: (versionId: number | null, record: any) => {
    if (record.version_number) {
      return <Tag>v{record.version_number}</Tag>
    }
    return <Text type="secondary">—</Text>
  },
}
```

### 6.6 TypeScript типы

**Добавить в** `frontend/src/types/index.ts`:

```typescript
// ── Version types (Phase 7) ──

export interface VersionInfo {
  id: number
  version_number: number
  file_type: string
  file_size: number
  version_notes: string | null
  uploaded_by: { id: number; email: string } | null
  created_at: string
  is_current: boolean
}

export interface VersionDiffResponse {
  from_version: number
  to_version: number
  diff: DiffResult
}
```

---

## 7. Migration Strategy

### 7.1 Миграция существующих документов

**Цель:** все существующие документы получают версию 1 без потери данных.

**Шаги миграции (скрипт `backend/scripts/migrate_versions.py`):**

```python
"""
Миграция существующих документов для Phase 7.
Создаёт DocumentVersion v1 для документов без версий,
переносит файлы в новый формат пути.
"""

import asyncio
import hashlib
import logging
import os
import shutil

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session
from app.models.document import Document
from app.models.document_version import DocumentVersion
from app.services.storage_service import storage

logger = logging.getLogger(__name__)

MIGRATE_BATCH_SIZE = 50


async def migrate_document_versions():
    """Scan all documents and ensure each has at least one version."""
    async with async_session() as db:
        # Get all documents
        stmt = select(Document)
        result = await db.execute(stmt)
        documents = result.scalars().all()

        total = len(documents)
        migrated = 0
        skipped = 0
        errors = 0

        for doc in documents:
            try:
                # Check if document already has versions
                ver_stmt = select(DocumentVersion).where(
                    DocumentVersion.document_id == doc.id
                )
                ver_result = await db.execute(ver_stmt)
                existing_versions = ver_result.scalars().all()

                if existing_versions:
                    # Already has versions — just ensure file paths are correct
                    for version in existing_versions:
                        await _migrate_version_path(doc, version)
                    skipped += 1
                    continue

                # Create version 1 from existing data
                # Find the file(s) in storage
                storage_dir = os.path.join(
                    storage.BASE_PATH,
                    str(doc.company_id),
                    str(doc.id),
                )

                if not os.path.exists(storage_dir):
                    logger.warning(
                        f"No storage directory for document {doc.id}, "
                        "skipping file migration"
                    )
                    # Create stub version anyway
                    version = DocumentVersion(
                        document_id=doc.id,
                        version_number=1,
                        file_path="",
                        file_type="docx",
                        file_size=0,
                        mime_type="application/octet-stream",
                    )
                    db.add(version)
                    await db.flush()
                    migrated += 1
                    continue

                # Find files in old format
                files = [
                    f for f in os.listdir(storage_dir)
                    if os.path.isfile(os.path.join(storage_dir, f))
                ]

                if not files:
                    logger.warning(
                        f"No files found for document {doc.id}"
                    )
                    version = DocumentVersion(
                        document_id=doc.id,
                        version_number=1,
                        file_path="",
                        file_type="docx",
                        file_size=0,
                        mime_type="application/octet-stream",
                    )
                    db.add(version)
                    await db.flush()
                    migrated += 1
                    continue

                # Use the most recent file
                files.sort(key=lambda f: os.path.getmtime(
                    os.path.join(storage_dir, f)
                ), reverse=True)
                old_filename = files[0]

                old_path = os.path.join(storage_dir, old_filename)
                new_dir = os.path.join(storage_dir, "v1")
                os.makedirs(new_dir, exist_ok=True)
                new_path = os.path.join(new_dir, old_filename)

                # Copy file to new path
                shutil.copy2(old_path, new_path)

                # Read file for hash and size
                with open(new_path, "rb") as f:
                    content = f.read()

                file_hash = hashlib.sha256(content).hexdigest()
                file_size = len(content)

                ext = os.path.splitext(old_filename)[1].lower().replace(".", "")
                file_type = "docx" if ext == "docx" else "pdf"
                mime_type = (
                    "application/vnd.openxmlformats-officedocument."
                    "wordprocessingml.document"
                    if file_type == "docx"
                    else "application/pdf"
                )

                rel_path = os.path.join(
                    str(doc.company_id),
                    str(doc.id),
                    "v1",
                    old_filename,
                ).replace("\\", "/")

                # Create version record
                version = DocumentVersion(
                    document_id=doc.id,
                    version_number=1,
                    file_path=rel_path,
                    file_type=file_type,
                    file_size=file_size,
                    mime_type=mime_type,
                    file_hash=file_hash,
                )
                db.add(version)
                await db.flush()

                # Parse file to extract full_text and sections
                try:
                    from app.services.parser_service import (
                        document_parser,
                        enhanced_document_parser,
                    )
                    from app.services.document_persistence_service import (
                        document_persistence_service,
                    )

                    parser = (
                        enhanced_document_parser
                        if file_type == "pdf"
                        else document_parser
                    )
                    parse_result = parser.parse(new_path, file_type)

                    await document_persistence_service.persist_parse_result(
                        parse_result=parse_result,
                        version=version,
                        document_id=doc.id,
                        db=db,
                    )
                except Exception as e:
                    logger.warning(
                        f"Parse failed during migration for doc {doc.id}: {e}"
                    )

                migrated += 1
                logger.info(
                    f"Migrated document {doc.id}: "
                    f"v1 created from {old_filename}"
                )

            except Exception as e:
                logger.error(
                    f"Failed to migrate document {doc.id}: {e}",
                    exc_info=True,
                )
                errors += 1

            # Batch commit
            if (migrated + skipped + errors) % MIGRATE_BATCH_SIZE == 0:
                await db.commit()

        await db.commit()

        logger.info(
            f"Migration complete: {total} docs, "
            f"{migrated} migrated, {skipped} already had versions, "
            f"{errors} errors"
        )


async def _migrate_version_path(doc: Document, version: DocumentVersion):
    """Ensure version file is in the new path format."""
    if not version.file_path:
        return

    # Check if already in new format (contains /v1/, /v2/, etc.)
    if "/v" in version.file_path:
        return  # Already in new format

    # Old format: {company_id}/{doc_id}/{filename}
    # New format: {company_id}/{doc_id}/v{version}/{filename}
    old_path = version.file_path
    filename = os.path.basename(old_path)
    storage_dir = os.path.join(
        storage.BASE_PATH,
        str(doc.company_id),
        str(doc.id),
    )
    new_rel_path = os.path.join(
        str(doc.company_id),
        str(doc.id),
        f"v{version.version_number}",
        filename,
    ).replace("\\", "/")

    # Move file if old path exists and new doesn't
    old_full = os.path.join(storage.BASE_PATH, old_path)
    new_full = os.path.join(storage.BASE_PATH, new_rel_path)

    if os.path.exists(old_full) and not os.path.exists(new_full):
        os.makedirs(os.path.dirname(new_full), exist_ok=True)
        shutil.move(old_full, new_full)
        version.file_path = new_rel_path
        logger.info(
            f"Moved file for doc {doc.id} v{version.version_number}: "
            f"{old_path} → {new_rel_path}"
        )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(migrate_document_versions())
```

### 7.2 Миграция DocumentAnalysis

Проставить `document_version_id` для существующих анализов:

```python
# В составе миграционного скрипта
async def migrate_analysis_version_ids():
    """Set document_version_id for analyses that don't have it."""
    async with async_session() as db:
        stmt = select(DocumentAnalysis).where(
            DocumentAnalysis.document_version_id.is_(None)
        )
        result = await db.execute(stmt)
        analyses = result.scalars().all()

        for analysis in analyses:
            # Find the latest version at the time of analysis
            ver_stmt = (
                select(DocumentVersion)
                .where(DocumentVersion.document_id == analysis.document_id)
                .where(DocumentVersion.created_at <= analysis.created_at)
                .order_by(DocumentVersion.version_number.desc())
                .limit(1)
            )
            ver_result = await db.execute(ver_stmt)
            version = ver_result.scalar_one_or_none()

            if version:
                analysis.document_version_id = version.id

        await db.commit()
        logger.info(f"Updated {len(analyses)} analyses with version IDs")
```

### 7.3 Порядок миграции

1. **Остановить сервисы** (если возможно)
2. **Backup**: создать копию `srp.db` и `storage/`
3. **Установить новый код** (без запуска)
4. **Запустить миграцию БД**: `alembic upgrade head`
5. **Запустить скрипт миграции файлов**: `python -m backend.scripts.migrate_versions`
6. **Запустить сервисы**
7. **Тестирование**: проверить несколько документов разных типов

---

## 8. Acceptance Criteria

1. **Загрузка нового файла создаёт версию v1**
   - Выбрать "Загрузить документ" → файл сохраняется в `storage/{company}/{doc}/v1/`
   - Создаётся `DocumentVersion` с `version_number=1`

2. **Повторная загрузка создаёт v2, v3...**
   - На вкладке «Версии» → «Создать версию» → загрузить новый файл
   - Новая версия создаётся с `version_number = max + 1`
   - Файл сохраняется в `v{new_version}/`

3. **При генерации документа создаётся v1**
   - GeneratorService → DocumentSaverService → версия 1

4. **При ревизии создаётся новая версия**
   - Нажать «Внести правки» → LLM генерирует новый текст
   - Создаётся новая `DocumentVersion` (v+1) с новым файлом
   - Старая версия не перезаписывается

5. **Можно скачать любую версию**
   - В таблице версий → кнопка «Скачать» у каждой версии
   - Скачивается файл именно этой версии

6. **Можно восстановить версию**
   - Кнопка «Восстановить» → подтверждение → создаётся новая версия
   - `version_notes = "Восстановлено из версии N"`
   - Файл новой версии = файл выбранной

7. **Можно сравнить две версии**
   - Выбрать две версии чекбоксами → «Сравнить» → DiffView
   - DiffService.generate_diff() на основе full_text

8. **Анализ привязан к версии**
   - `DocumentAnalysis.document_version_id` заполнен
   - Фильтр `GET .../analyses?version=N` возвращает анализы для версии

9. **Миграция существующих документов**
   - Все существующие документы имеют v1
   - Файлы перемещены в `v1/` (или есть fallback для старых путей)
   - Существующие анализы привязаны к версиям

10. **Обратная совместимость**
    - Старые ссылки на скачивание (`/documents/versions/{version_id}/download`) работают
    - Старые пути файлов доступны через fallback

---

## 9. Risks & Assumptions

### 9.1 Risks

| Риск | Impact | Mitigation |
|------|--------|------------|
| Миграция большого объёма данных — долго и рискованно | High | Тестировать на копии; батчевая миграция по 50 документов; backup перед миграцией |
| Потеря файлов при переносе в `v1/` | Critical | Сначала копировать, потом удалять старые; fallback для старых путей |
| Конфликт версий при одновременной загрузке | Medium | UniqueConstraint + номер версии вычисляется в транзакции (SELECT MAX FOR UPDATE) |
| Diff между версиями не работает, если нет `full_text` | Medium | Fallback на извлечение текста из файла через parser_service |
| Восстановление случайно выбрано | Low | Подтверждение с описанием: «Будет создана новая версия с содержимым v{N}» |
| Старые ссылки на файлы перестают работать | Medium | Fallback в StorageService.get() для старых путей; не удалять старые файлы сразу |
| Много версий → дублирование storage | Low | Ожидается < 10 версий на документ; архивация старых — в будущих фазах |
| Конфликт имён файлов в новом формате | Low | Имя файла сохраняется как есть; UUID в имени не нужен, т.к. путь уникален |

### 9.2 Assumptions

- **Текущая версия** = версия с максимальным `version_number` (не хранится отдельно)
- **Файлы не удаляются** при создании новой версии (все версии сохраняются)
- **Восстановление** создаёт новую версию, не перезаписывает существующие
- **Размер файлов** не превышает лимиты хранилища (ожидается < 10 MB на файл)
- **Количество версий** на документ — не более 20-30 (нет авто-архивации старых)
- **DiffService** из Phase 6 переиспользуется для сравнения full_text версий
- **ParserService** доступен для извлечения текста из файлов версий, у которых нет full_text

---

## 10. Порядок реализации (Steps)

### Step 1: Backend — Storage paths
- [ ] Обновить `StorageService.save()` — новый формат пути `v{version}/`
- [ ] Добавить fallback для старых путей в `StorageService.get()`
- [ ] Обновить `StorageService.delete()` — удаление по новому формату

### Step 2: Backend — Model changes
- [ ] Добавить `file_hash` в `DocumentVersion`
- [ ] Добавить `UniqueConstraint("document_id", "version_number")`
- [ ] Создать Alembic миграцию

### Step 3: Backend — VersionService
- [ ] Создать `backend/app/services/version_service.py`
- [ ] Реализовать: `get_versions`, `get_version`, `create_version`, `restore_version`, `get_version_diff`, `download_version`

### Step 4: Backend — API endpoints
- [ ] `GET /documents/{id}/versions` — обновить формат ответа (добавить `is_current`)
- [ ] `GET /documents/{id}/versions/{version_number}/download` — новый
- [ ] `POST /documents/{id}/versions/{version_number}/restore` — новый
- [ ] `GET /documents/{id}/versions/{v1}/diff/{v2}` — новый
- [ ] `GET /documents/{id}/analyses?version={version}` — обновить фильтр
- [ ] Подключить в `router.py`

### Step 5: Backend — Интеграция с существующими сервисами
- [ ] **DocumentUploadService**: использовать новый `StorageService.save()` с `v{version}/`
- [ ] **DocumentSaverService**: использовать новый формат пути
- [ ] **RevisionService**: при ревизии создавать новую версию (а не перезаписывать)
- [ ] **AnalysisPipelineService**: убедиться, что `document_version_id` проставляется
- [ ] **DocumentUpdateService**: обновить `_trigger_analysis_pipeline` для передачи `document_version_id`

### Step 6: Backend — Migration script
- [ ] Создать `backend/scripts/migrate_versions.py`
- [ ] Перенос файлов в `v1/`
- [ ] Создание `DocumentVersion` для документов без версий
- [ ] Миграция `DocumentAnalysis.document_version_id`

### Step 7: Frontend — API и типы
- [ ] Обновить `frontend/src/api/documents.ts` — новые функции (getDocumentVersions, downloadVersionByNumber, restoreVersion, getVersionDiff, getAnalysesByVersion)
- [ ] Добавить типы в `frontend/src/types/index.ts` (VersionInfo, VersionDiffResponse)

### Step 8: Frontend — Версии tab
- [ ] Обновить таблицу версий: отображение текущей версии (Tag "Текущая")
- [ ] Добавить кнопку «Скачать» для каждой версии
- [ ] Добавить кнопку «Восстановить» (с подтверждением)
- [ ] Добавить чекбоксы для выбора двух версий → кнопка «Сравнить»

### Step 9: Frontend — Diff между версиями
- [ ] Модальное окно с `DiffView` для двух версий
- [ ] Использовать существующий `DiffView` компонент

### Step 10: Frontend — Анализ по версии
- [ ] Добавить колонку «Версия» в историю анализов
- [ ] Показывать номер версии в карточке анализа

### Step 11: Integration & Tests
- [ ] Backend тесты (pytest) для VersionService
- [ ] E2E тест: создать версию → скачать → восстановить → diff
- [ ] Проверить миграцию (alembic upgrade head + скрипт migration)
- [ ] Проверить frontend сборку (npm run build)
- [ ] Проверить обратную совместимость (старые файлы, старые endpoints)

### Step 12: Документация
- [ ] Обновить `openapi.json` (новые endpoints)
- [ ] Обновить `DESIGN.md` если необходимо

---

## 11. Открытые вопросы

1. **Нужен ли `current_version_id` в Document?**
   - ✅ Решение: нет, текущая версия определяется как `max(version_number)`. Это проще и не требует миграции данных. Единственный недостаток — запрос `MAX` на каждое чтение, но это решается через подзапрос или кэширование в `DocumentResponse`.

2. **Как быть с файлами, у которых нет `full_text`?**
   - ✅ Решение: использовать `parser_service.extract_text()` для извлечения текста на лету при diff/restore. Результат не кэшировать.

3. **Удалять ли старые файлы после переноса в `v1/`?**
   - ✅ Решение: нет, оставить для обратной совместимости. Fallback в `StorageService.get()` сначала пытается новый путь, потом старый. Старые файлы можно будет удалить после подтверждения, что миграция прошла успешно.

4. **Ограничить количество версий?**
   - Нет, в этой фазе не ограничиваем. При необходимости — архивация старых версий в отдельном скрипте.

5. **Как обновлять `file_path` в существующих `DocumentVersion`?**
   - ✅ Решение: в миграционном скрипте обновлять `file_path` для существующих версий на новый формат.

6. **Поддерживать ли скачивание по ID версии (старый endpoint)?**
   - ✅ Да, сохранить для обратной совместимости. Новый endpoint (`by version_number`) — рекомендуемый.

7. **Обрабатывать ли случай, когда `full_text` версии пуст, а файл существует?**
   - ✅ Да, в `_get_version_text()` есть fallback на парсинг файла.

---

## 12. Файловая структура (изменения)

```
backend/
  app/
    models/
      document_version.py        # +file_hash, +UniqueConstraint
    services/
      version_service.py         # NEW
      storage_service.py         # update save() path format
      document_upload_service.py # use new path format
      document_saver_service.py  # use new path format
      revision_service.py        # create new version instead of overwrite
      analysis_pipeline_service.py # ensure document_version_id
    api/
      v1/
        documents.py             # new endpoints for versioning
        analysis.py              # add ?version filter
  scripts/
    migrate_versions.py          # NEW: data migration

frontend/
  src/
    api/
      documents.ts               # +version API functions
      versions.ts                # update if needed
    types/
      index.ts                   # +VersionInfo, VersionDiffResponse
    pages/
      DocumentDetailPage.tsx     # enhanced versions tab
```

---

## 13. Приложение: diff между ревизией Phase 6 и версией Phase 7

| Операция | Phase 6 (Revision) | Phase 7 (Version) |
|----------|-------------------|-------------------|
| Создание | `DocumentRevision` (old/new text) | `DocumentVersion` (файл + full_text) |
| Хранение текста | В таблице `document_revisions` | В `DocumentVersion.full_text` |
| Файл | Перезаписывается | Новая версия сохраняется отдельно |
| Откат | Нет | Restore версии |
| Сравнение | old_text vs new_text | full_text любой пары версий |
| Привязка анализа | К документу (опционально к версии) | К версии (обязательно) |
| История | Только ревизии | Ревизии + версии |
