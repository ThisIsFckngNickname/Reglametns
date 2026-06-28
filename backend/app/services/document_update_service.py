"""
Document update service — status changes, archiving, and deletion.
"""

import logging
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import BadRequestException, NotFoundException
from app.models.document import Document
from app.models.document_link import DocumentLink
from app.models.document_status import DocumentStatus
from app.schemas.document import DocumentResponse, DocumentUpdate
from app.schemas.links import DocumentLinkCreate
from app.services.storage_service import storage

logger = logging.getLogger(__name__)

# ─── Status Transition Rules ──────────────────────────────────────────

STATUS_TRANSITIONS = {
    DocumentStatus.DRAFT: {DocumentStatus.REVIEW, DocumentStatus.ARCHIVED},
    DocumentStatus.REVIEW: {DocumentStatus.DRAFT, DocumentStatus.APPROVED, DocumentStatus.ARCHIVED},
    DocumentStatus.APPROVED: {DocumentStatus.CANCELLED, DocumentStatus.ARCHIVED},
    DocumentStatus.CANCELLED: {DocumentStatus.DRAFT, DocumentStatus.ARCHIVED},  # Cancelled → Draft or Archived
    DocumentStatus.ARCHIVED: set(),   # Terminal
}


class DocumentUpdateService:
    """Document metadata updates and lifecycle operations."""

    # Note: update_document calls self.get_document() which is defined in
    # DocumentReadService. At runtime via the DocumentService facade (multiple
    # inheritance), MRO resolves it correctly. This is a standard Python mixin
    # pattern.

    async def update_document(
        self, id: int, data: DocumentUpdate, company_id: int, db: AsyncSession,
        user_id: Optional[int] = None,
        is_admin: bool = False,
    ) -> DocumentResponse:
        """Update document metadata."""
        stmt = select(Document).where(
            Document.id == id,
            Document.company_id == company_id,
        )
        result = await db.execute(stmt)
        doc = result.scalar_one_or_none()

        if doc is None:
            raise NotFoundException(message="Document not found", field="document_id")

        old_status = doc.status

        if data.title is not None:
            doc.title = data.title
        if data.description is not None:
            doc.description = data.description
        if data.status is not None:
            # Validate transition (admins can bypass)
            if old_status != data.status:
                if not is_admin:
                    allowed = STATUS_TRANSITIONS.get(old_status, set())
                    if data.status not in allowed:
                        raise BadRequestException(
                            message=f"Cannot change status from {old_status} to {data.status}",
                        )
            doc.status = data.status

        await db.flush()

        # Log status change
        if data.status is not None and data.status != old_status:
            await self._log_status_change(
                document_id=id,
                from_status=old_status,
                to_status=data.status,
                user_id=user_id,
                reason=getattr(data, 'comment', None),
                db=db,
            )

            # Trigger pattern analysis if document is approved and not yet analyzed
            if data.status == DocumentStatus.APPROVED and not doc.was_analyzed:
                from app.services.pattern_analysis_service import pattern_analysis_service
                try:
                    analysis_result = await pattern_analysis_service.analyze_document(
                        document_id=id,
                        db=db,
                    )
                    logger.info(
                        f"Pattern analysis triggered for document {id}: {analysis_result}"
                    )
                except Exception as e:
                    logger.error(f"Pattern analysis failed for document {id}: {e}", exc_info=True)
                    # Don't fail the update if analysis fails

            # Trigger RAG indexing when document is approved
            if data.status == DocumentStatus.APPROVED:
                await self._trigger_rag_indexing(id, company_id, db)

        return await self.get_document(id, company_id, db)

    async def change_status(
        self,
        document_id: int,
        new_status: DocumentStatus,
        comment: Optional[str],
        company_id: int,
        user_id: int,
        db: AsyncSession,
        is_admin: bool = False,
    ) -> dict:
        """Change document status with validation and optional comment."""
        # Verify document ownership
        stmt = select(Document).where(
            Document.id == document_id,
            Document.company_id == company_id,
        )
        result = await db.execute(stmt)
        doc = result.scalar_one_or_none()

        if doc is None:
            raise NotFoundException(message="Document not found", field="document_id")

        old_status = doc.status

        if old_status == new_status:
            return {"message": "Status unchanged", "status": new_status.value}

        # Validate transition (admins can bypass)
        if not is_admin:
            allowed = STATUS_TRANSITIONS.get(old_status, set())
            if new_status not in allowed:
                raise BadRequestException(
                    message=f"Cannot change status from {old_status} to {new_status}",
                )

        # Apply new status
        doc.status = new_status
        await db.flush()

        # Log status change with optional comment
        await self._log_status_change(
            document_id=document_id,
            from_status=old_status,
            to_status=new_status,
            user_id=user_id,
            reason=comment,
            db=db,
        )

        # Trigger pattern analysis if approved and not yet analyzed
        if new_status == DocumentStatus.APPROVED and not doc.was_analyzed:
            from app.services.pattern_analysis_service import pattern_analysis_service
            try:
                analysis_result = await pattern_analysis_service.analyze_document(
                    document_id=document_id,
                    db=db,
                )
                logger.info(
                    f"Pattern analysis triggered for document {document_id}: {analysis_result}"
                )
            except Exception as e:
                logger.error(f"Pattern analysis failed for document {document_id}: {e}", exc_info=True)

        # Trigger RAG indexing when approved
        if new_status == DocumentStatus.APPROVED:
            await self._trigger_rag_indexing(document_id, company_id, db)

        return {
            "message": f"Status changed from {old_status.value} to {new_status.value}",
            "from_status": old_status.value,
            "to_status": new_status.value,
        }

    async def _log_status_change(
        self,
        document_id: int,
        from_status: Optional[DocumentStatus],
        to_status: DocumentStatus,
        user_id: Optional[int],
        db: AsyncSession,
        reason: Optional[str] = None,
    ) -> None:
        """Log a document status change."""
        from app.models.document_status_log import DocumentStatusLog
        log = DocumentStatusLog(
            document_id=document_id,
            from_status=from_status,
            to_status=to_status,
            changed_by=user_id,
            reason=reason,
        )
        db.add(log)

    async def _trigger_rag_indexing(
        self,
        document_id: int,
        company_id: int,
        db: AsyncSession,
    ) -> None:
        """Index the approved document in the RAG service."""
        try:
            from app.services.rag_service import rag_service

            # Reload document with versions to get full_text
            stmt = (
                select(Document)
                .where(Document.id == document_id, Document.company_id == company_id)
                .options(selectinload(Document.versions))
            )
            result = await db.execute(stmt)
            doc = result.scalar_one_or_none()
            if not doc:
                return

            # Get latest version's full_text
            latest_version = None
            if doc.versions:
                latest_version = max(doc.versions, key=lambda v: v.version_number)

            if latest_version and latest_version.full_text:
                chunks_count = await rag_service.index_document(
                    document_id=document_id,
                    company_id=company_id,
                    title=doc.title,
                    full_text=latest_version.full_text,
                )
                logger.info(
                    f"RAG indexed {chunks_count} chunks for document {document_id}"
                )
            else:
                logger.warning(
                    f"No full_text found for document {document_id}, "
                    "skipping RAG indexing"
                )
        except ImportError:
            logger.warning("RAG service not available, skipping indexing")
        except Exception as e:
            logger.error(
                f"RAG indexing failed for document {document_id}: {e}",
                exc_info=True,
            )
            # Don't fail the update if RAG indexing fails

    async def archive_document(self, id: int, company_id: int, db: AsyncSession) -> None:
        """Archive a document by setting status to 'archived'."""
        stmt = select(Document).where(
            Document.id == id,
            Document.company_id == company_id,
        )
        result = await db.execute(stmt)
        doc = result.scalar_one_or_none()

        if doc is None:
            raise NotFoundException(message="Document not found", field="document_id")

        doc.status = DocumentStatus.ARCHIVED
        await db.flush()

    async def hard_delete_document(self, id: int, db: AsyncSession) -> None:
        """Permanently delete a document and all related data from DB and storage.

        This includes:
        - All versions (and their files from storage)
        - All terms, abbreviations, tables, sections
        - All links (source and target)
        - All order-document links
        """
        stmt = select(Document).where(Document.id == id)
        result = await db.execute(stmt)
        doc = result.scalar_one_or_none()

        if doc is None:
            raise NotFoundException(message="Document not found", field="document_id")

        # Delete version files from storage first
        for version in doc.versions:
            try:
                await storage.delete(version.file_path)
            except Exception:
                pass  # Log but don't fail if file already missing

        # Delete the document - ORM cascades will delete all related records
        await db.delete(doc)
        await db.flush()

    async def analyze_document(
        self, document_id: int, company_id: int, db: AsyncSession
    ) -> dict:
        """Manually trigger pattern analysis for a document."""
        from app.services.pattern_analysis_service import pattern_analysis_service

        # Verify ownership
        stmt = select(Document).where(
            Document.id == document_id,
            Document.company_id == company_id,
        )
        result = await db.execute(stmt)
        doc = result.scalar_one_or_none()
        if doc is None:
            raise NotFoundException(message="Document not found", field="document_id")

        result = await pattern_analysis_service.analyze_document(
            document_id=document_id,
            db=db,
        )

        return {
            "document_id": document_id,
            "company_id": company_id,
            "structure_extracted": result.get("structure_extracted", False),
            "style_extracted": result.get("style_extracted", False),
            "terms_collected": result.get("terms_collected", 0),
            "abbreviations_collected": result.get("abbreviations_collected", 0),
            "message": "Document analyzed successfully" if "error" not in result else result["error"],
        }

    async def create_link(
        self,
        document_id: int,
        data: DocumentLinkCreate,
        user_id: int,
        company_id: int,
        db: AsyncSession,
    ) -> dict:
        """Create a document-to-document link."""
        # Verify source document ownership
        stmt = select(Document).where(
            Document.id == document_id,
            Document.company_id == company_id,
        )
        result = await db.execute(stmt)
        source_doc = result.scalar_one_or_none()
        if source_doc is None:
            raise NotFoundException(message="Source document not found", field="document_id")

        # Verify target document exists (in any company)
        tgt_stmt = select(Document).where(Document.id == data.target_document_id)
        tgt_result = await db.execute(tgt_stmt)
        target_doc = tgt_result.scalar_one_or_none()
        if target_doc is None:
            raise NotFoundException(message="Target document not found", field="target_document_id")

        # Prevent self-link
        if document_id == data.target_document_id:
            raise ValueError("Cannot create a link to itself")

        # Create link
        link = DocumentLink(
            source_document_id=document_id,
            target_document_id=data.target_document_id,
            link_type=data.link_type,
            description=data.description,
            is_manual=True,
            created_by=user_id,
        )
        db.add(link)
        await db.flush()
        await db.refresh(link)

        return {
            "id": link.id,
            "source_document_id": link.source_document_id,
            "target_document_id": link.target_document_id,
            "link_type": link.link_type,
            "is_manual": link.is_manual,
            "description": link.description,
            "created_by": link.created_by,
            "created_at": link.created_at.isoformat(),
            "target_title": target_doc.title,
            "target_status": target_doc.status,
        }

    async def delete_link(
        self,
        document_id: int,
        link_id: int,
        company_id: int,
        db: AsyncSession,
    ) -> None:
        """Delete a document link."""
        # Verify source document ownership
        stmt = select(Document).where(
            Document.id == document_id,
            Document.company_id == company_id,
        )
        result = await db.execute(stmt)
        if result.scalar_one_or_none() is None:
            raise NotFoundException(message="Document not found", field="document_id")

        # Find the link
        link_stmt = select(DocumentLink).where(
            DocumentLink.id == link_id,
            DocumentLink.source_document_id == document_id,
        )
        link_result = await db.execute(link_stmt)
        link = link_result.scalar_one_or_none()
        if link is None:
            raise NotFoundException(message="Link not found", field="link_id")

        await db.delete(link)
        await db.flush()
