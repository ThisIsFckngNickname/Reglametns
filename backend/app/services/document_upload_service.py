"""
Document upload service — file upload, parsing, and version creation.
"""

import hashlib
import logging
import os
from io import BytesIO
from typing import Optional

from fastapi import UploadFile as FastAPIUploadFile
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.core.exceptions import (
    FileTooLarge,
    InvalidFileType,
    ParseError,
)
from app.models.document import Document
from app.models.document_status import DocumentStatus
from app.models.document_version import DocumentVersion
from app.models.user import User
from app.schemas.document import UploadResponse
from app.services.document_persistence_service import document_persistence_service
from app.services.parser_service import document_parser, enhanced_document_parser
from app.services.storage_service import storage

logger = logging.getLogger(__name__)


def _get_file_type(filename: str) -> str:
    """Get file type from filename extension."""
    _, ext = os.path.splitext(filename)
    ext = ext.lower().replace(".", "")
    if ext in ("docx",):
        return "docx"
    elif ext in ("pdf",):
        return "pdf"
    return ext


def _get_mime_type(file_type: str) -> str:
    """Get MIME type from file type."""
    mimes = {
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "pdf": "application/pdf",
    }
    return mimes.get(file_type, "application/octet-stream")


class DocumentUploadService:
    """File upload and version creation."""

    async def upload(
        self,
        file: FastAPIUploadFile,
        title: Optional[str],
        description: Optional[str],
        user: User,
        company_id: int,
        db: AsyncSession,
        document_type: str = "regulation",
    ) -> UploadResponse:
        """Upload a file, parse it, and store all extracted data."""
        # Validate file
        if not file.filename:
            raise InvalidFileType(message="File has no name")

        ext = os.path.splitext(file.filename)[1].lower()
        if ext not in settings.allowed_extensions:
            raise InvalidFileType(
                message=f"Invalid file type '{ext}'. Allowed: {', '.join(settings.allowed_extensions)}"
            )

        # Check file size
        content = await file.read()
        file_size = len(content)
        if file_size > settings.max_upload_size:
            raise FileTooLarge(
                message=f"File too large ({file_size} bytes). "
                        f"Maximum is {settings.max_upload_size} bytes"
            )

        file_type = _get_file_type(file.filename)

        # Determine title
        doc_title = title
        if not doc_title:
            doc_title = os.path.splitext(file.filename)[0]

        # Create Document record
        document = Document(
            company_id=company_id,
            title=doc_title,
            description=description,
            document_type=document_type,
            status=DocumentStatus.DRAFT,
            created_by=user.id,
        )
        db.add(document)
        await db.flush()
        await db.refresh(document)

        # Determine version number
        version_stmt = select(func.max(DocumentVersion.version_number)).where(
            DocumentVersion.document_id == document.id
        )
        version_result = await db.execute(version_stmt)
        max_version = version_result.scalar() or 0
        version_number = max_version + 1

        # Save file
        rel_path = await self._save_file(
            file.filename, content, company_id, document.id, version_number
        )

        # Create DocumentVersion record
        mime_type = _get_mime_type(file_type)
        file_hash = hashlib.sha256(content).hexdigest()
        version = DocumentVersion(
            document_id=document.id,
            version_number=version_number,
            file_path=rel_path,
            file_type=file_type,
            file_size=file_size,
            mime_type=mime_type,
            file_hash=file_hash,
            uploaded_by=user.id,
        )
        db.add(version)
        await db.flush()
        await db.refresh(version)

        # Parse document (use enhanced parser for PDFs)
        try:
            full_path = await storage.get_full_path(rel_path)
            if not os.path.exists(full_path):
                raise FileNotFoundError(f"Saved file not found at {full_path}")

            # Use enhanced parser for PDFs to support complex layouts
            parser = enhanced_document_parser if file_type == "pdf" else document_parser
            parse_result = parser.parse(full_path, file_type)
        except Exception as e:
            logger.error(f"Parse error for document {document.id}: {e}", exc_info=True)
            raise ParseError(message=f"Failed to parse document: {str(e)}")

        # Persist all parsed data via the shared persistence service
        await document_persistence_service.persist_parse_result(
            parse_result=parse_result,
            version=version,
            document_id=document.id,
            db=db,
        )

        # Trigger RAG indexing if document is uploaded with approved status
        if document.status == DocumentStatus.APPROVED:
            try:
                from app.services.rag_service import rag_service
                # Reload document with versions to access full_text
                stmt = select(Document).where(
                    Document.id == document.id
                ).options(selectinload(Document.versions))
                result = await db.execute(stmt)
                doc_with_versions = result.scalar_one_or_none()
                if doc_with_versions and doc_with_versions.versions:
                    latest = max(doc_with_versions.versions, key=lambda v: v.version_number)
                    if latest.full_text:
                        await rag_service.index_document(
                            document_id=document.id,
                            company_id=company_id,
                            title=document.title,
                            full_text=latest.full_text,
                        )
                        logger.info(
                            f"RAG indexing triggered for document {document.id}"
                        )
            except Exception as e:
                logger.warning(f"RAG indexing skipped for document {document.id}: {e}")

        return UploadResponse(
            id=document.id,
            title=document.title,
            status=document.status,
            file_type=file_type,
            file_size=file_size,
            sections_count=len(parse_result.sections),
            tables_count=len(parse_result.tables),
            terms_count=len(parse_result.terms),
            abbreviations_count=len(parse_result.abbreviations),
            lists_count=len(parse_result.lists),
        )

    async def _save_file(
        self, filename: str, content: bytes, company_id: int, document_id: int, version_number: int
    ) -> str:
        """Save file bytes to disk using the storage service."""
        fake_file = FastAPIUploadFile(
            filename=filename,
            file=BytesIO(content),
        )
        return await storage.save(fake_file, company_id, document_id, version_number)

    async def create_version(
        self,
        document_id: int,
        file: FastAPIUploadFile,
        version_notes: Optional[str],
        user: User,
        company_id: int,
        db: AsyncSession,
    ) -> dict:
        """Create a new version for an existing document."""
        # Verify document exists and belongs to company
        stmt = select(Document).where(
            Document.id == document_id,
            Document.company_id == company_id,
        )
        result = await db.execute(stmt)
        doc = result.scalar_one_or_none()
        if doc is None:
            raise NotFoundException(message="Document not found", field="document_id")

        # Validate file
        if not file.filename:
            raise InvalidFileType(message="File has no name")

        ext = os.path.splitext(file.filename)[1].lower()
        if ext not in settings.allowed_extensions:
            raise InvalidFileType(
                message=f"Invalid file type '{ext}'. Allowed: {', '.join(settings.allowed_extensions)}"
            )

        content = await file.read()
        file_size = len(content)
        if file_size > settings.max_upload_size:
            raise FileTooLarge(
                message=f"File too large ({file_size} bytes). "
                        f"Maximum is {settings.max_upload_size} bytes"
            )

        file_type = _get_file_type(file.filename)
        mime_type = _get_mime_type(file_type)

        # Determine version number
        version_stmt = select(func.max(DocumentVersion.version_number)).where(
            DocumentVersion.document_id == document_id
        )
        version_result = await db.execute(version_stmt)
        max_version = version_result.scalar() or 0
        version_number = max_version + 1

        # Save file
        rel_path = await self._save_file(
            file.filename, content, company_id, document_id, version_number
        )

        # Create version record
        file_hash = hashlib.sha256(content).hexdigest()
        version = DocumentVersion(
            document_id=document_id,
            version_number=version_number,
            file_path=rel_path,
            file_type=file_type,
            file_size=file_size,
            mime_type=mime_type,
            file_hash=file_hash,
            version_notes=version_notes,
            uploaded_by=user.id,
        )
        db.add(version)
        await db.flush()
        await db.refresh(version)

        # Parse document and save sections + full_text
        try:
            full_path = await storage.get_full_path(rel_path)
            if not os.path.exists(full_path):
                raise FileNotFoundError(f"Saved file not found at {full_path}")
            parser = enhanced_document_parser if file_type == "pdf" else document_parser
            parse_result = parser.parse(full_path, file_type)
        except Exception as e:
            logger.error(f"Parse error for version {version.id}: {e}", exc_info=True)
            raise ParseError(message=f"Failed to parse document: {str(e)}")

        # Persist all parsed data via the shared persistence service
        await document_persistence_service.persist_parse_result(
            parse_result=parse_result,
            version=version,
            document_id=document_id,
            db=db,
        )

        return {
            "id": version.id,
            "document_id": version.document_id,
            "version_number": version.version_number,
            "file_type": version.file_type,
            "file_size": version.file_size,
            "file_hash": version.file_hash,
            "mime_type": version.mime_type,
            "version_notes": version.version_notes,
            "uploaded_by": version.uploaded_by,
            "created_at": version.created_at,
        }
