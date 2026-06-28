"""
Version service — manages document versions.

Phase 7: Provides create, list, restore, download, and compare
operations for document versions.
"""

import hashlib
import logging
import os
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundException, BadRequestException
from app.models.document import Document
from app.models.document_version import DocumentVersion
from app.schemas.revision import DiffResult
from app.services.diff_service import diff_service
from app.services.storage_service import storage

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    """Return naive UTC datetime."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class VersionService:
    """Service for document version management."""

    async def get_versions(
        self,
        document_id: int,
        company_id: int,
        db: AsyncSession,
    ) -> list[DocumentVersion]:
        """Get all versions for a document, newest first."""
        # Verify document belongs to company
        stmt = select(Document).where(
            Document.id == document_id,
            Document.company_id == company_id,
        )
        result = await db.execute(stmt)
        if result.scalar_one_or_none() is None:
            raise NotFoundException(message="Document not found", field="document_id")

        stmt = (
            select(DocumentVersion)
            .where(DocumentVersion.document_id == document_id)
            .order_by(DocumentVersion.version_number.desc())
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get_version(
        self,
        document_id: int,
        version_number: int,
        company_id: int,
        db: AsyncSession,
    ) -> DocumentVersion:
        """Get a specific version by document_id and version_number."""
        # Verify document belongs to company
        stmt = select(Document).where(
            Document.id == document_id,
            Document.company_id == company_id,
        )
        result = await db.execute(stmt)
        if result.scalar_one_or_none() is None:
            raise NotFoundException(message="Document not found", field="document_id")

        version_stmt = select(DocumentVersion).where(
            DocumentVersion.document_id == document_id,
            DocumentVersion.version_number == version_number,
        )
        version_result = await db.execute(version_stmt)
        version = version_result.scalar_one_or_none()
        if version is None:
            raise NotFoundException(
                message=f"Version {version_number} not found",
                field="version_number",
            )
        return version

    async def create_version(
        self,
        document_id: int,
        company_id: int,
        file_content: bytes,
        filename: str,
        author_id: int,
        comment: Optional[str] = None,
        db: Optional[AsyncSession] = None,
    ) -> DocumentVersion:
        """Create a new version for a document.

        1. Verify document exists and belongs to company
        2. Determine version number (max + 1)
        3. Compute file hash
        4. Save file to storage/{company_id}/{doc_id}/v{version}/{filename}
        5. Create DocumentVersion record
        """
        from fastapi import HTTPException

        # Get document
        stmt = select(Document).where(
            Document.id == document_id,
            Document.company_id == company_id,
        )
        result = await db.execute(stmt)
        doc = result.scalar_one_or_none()
        if doc is None:
            raise HTTPException(status_code=404, detail="Document not found")

        # Get max version number
        max_v_stmt = select(func.coalesce(func.max(DocumentVersion.version_number), 0)).where(
            DocumentVersion.document_id == document_id,
        )
        max_v_result = await db.execute(max_v_stmt)
        max_version = max_v_result.scalar() or 0
        new_version_number = max_version + 1

        # Compute hash
        file_hash = hashlib.sha256(file_content).hexdigest()
        file_size = len(file_content)

        # Determine file type and mime type
        ext = os.path.splitext(filename)[1].lower().replace(".", "")
        file_type = "docx" if ext == "docx" else "pdf" if ext == "pdf" else ext
        mime_types = {
            "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "pdf": "application/pdf",
        }
        mime_type = mime_types.get(file_type, "application/octet-stream")

        # Save file using storage_service
        saved_path = await storage.save_version_file(
            document=doc,
            version_number=new_version_number,
            file_content=file_content,
            filename=filename,
        )

        # Create version record
        version = DocumentVersion(
            document_id=document_id,
            version_number=new_version_number,
            file_path=saved_path,
            file_type=file_type,
            file_size=file_size,
            mime_type=mime_type,
            file_hash=file_hash,
            version_notes=comment,
            uploaded_by=author_id,
            created_at=_utcnow(),
        )
        db.add(version)
        await db.flush()
        await db.refresh(version)

        logger.info(
            f"Created version {new_version_number} for document {document_id}: "
            f"file={saved_path}, size={file_size}, hash={file_hash[:16]}..."
        )
        return version

    async def restore_version(
        self,
        document_id: int,
        version_number: int,
        company_id: int,
        author_id: int,
        db: AsyncSession,
    ) -> DocumentVersion:
        """Restore a version: create a new version with the content of the specified version."""
        # Get the version to restore
        version = await self.get_version(document_id, version_number, company_id, db)

        # Read file content
        file_content = await storage.get_version_file_content(version)
        if not file_content:
            raise NotFoundException(
                message=f"File for version {version_number} not found on disk",
                field="version_number",
            )

        # Determine filename from path
        filename = os.path.basename(version.file_path or "document.docx")

        # Create new version with restored content
        restored_comment = f"Восстановлено из версии v{version_number}"
        new_version = await self.create_version(
            document_id=document_id,
            company_id=company_id,
            file_content=file_content,
            filename=filename,
            author_id=author_id,
            comment=restored_comment,
            db=db,
        )

        return new_version

    async def download_version(
        self,
        document_id: int,
        version_number: int,
        company_id: int,
        db: AsyncSession,
    ) -> tuple[bytes, str, str]:
        """Download a specific version's file.

        Returns (file_content, filename, content_type).
        """
        version = await self.get_version(document_id, version_number, company_id, db)

        file_content = await storage.get_version_file_content(version)
        if not file_content:
            raise NotFoundException(
                message=f"File for version {version_number} not found on disk",
                field="version_number",
            )

        filename = f"document_v{version.version_number}.{version.file_type}"
        content_type = version.mime_type or "application/octet-stream"

        return file_content, filename, content_type

    async def compare_versions(
        self,
        document_id: int,
        version_a: int,
        version_b: int,
        company_id: int,
        db: AsyncSession,
    ) -> DiffResult:
        """Compare two versions and return diff."""
        v_a = await self.get_version(document_id, version_a, company_id, db)
        v_b = await self.get_version(document_id, version_b, company_id, db)

        # Try full_text first
        text_a = v_a.full_text or await storage.get_text_by_path(v_a.file_path) or ""
        text_b = v_b.full_text or await storage.get_text_by_path(v_b.file_path) or ""

        if not text_a and not text_b:
            raise BadRequestException(
                message="Neither version has extractable text content",
            )

        return diff_service.generate_diff(text_a, text_b)


# Singleton
version_service = VersionService()
