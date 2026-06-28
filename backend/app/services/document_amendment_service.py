"""
Document Amendment Service — manages 'amends' relationships between orders and documents.
"""

import logging
from typing import List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document
from app.models.document_link import DocumentLink

logger = logging.getLogger(__name__)


class DocumentAmendmentService:
    """Service for querying amendment relationships (link_type='amends')."""

    async def get_amendments(
        self,
        document_id: int,
        company_id: int,
        db: AsyncSession,
    ) -> List[dict]:
        """Get all orders (link_type='amends') that target this document.

        Args:
            document_id: ID of the document being amended.
            company_id: Company ID for access control.
            db: Database session.

        Returns:
            List of amendment items (incoming: orders that amend this doc).
        """
        # First verify the document belongs to the company
        doc_stmt = select(Document).where(
            Document.id == document_id,
            Document.company_id == company_id,
        )
        doc_result = await db.execute(doc_stmt)
        doc = doc_result.scalar_one_or_none()
        if doc is None:
            return []

        # Find all amends links where this document is the target
        stmt = (
            select(DocumentLink)
            .where(
                DocumentLink.target_document_id == document_id,
                DocumentLink.link_type == "amends",
            )
            .order_by(DocumentLink.created_at.desc())
        )
        result = await db.execute(stmt)
        links = result.scalars().all()

        items = []
        for link in links:
            # Load source document (the order)
            src_stmt = select(Document).where(Document.id == link.source_document_id)
            src_result = await db.execute(src_stmt)
            src_doc = src_result.scalar_one_or_none()
            if src_doc is None:
                continue

            items.append({
                "document_id": src_doc.id,
                "link_id": link.id,
                "title": src_doc.title,
                "document_type": src_doc.document_type,
                "status": src_doc.status,
                "created_at": link.created_at,
            })

        return items

    async def get_amended_documents(
        self,
        document_id: int,
        company_id: int,
        db: AsyncSession,
    ) -> List[dict]:
        """Get all documents amended by this order (link_type='amends').

        Args:
            document_id: ID of the order document.
            company_id: Company ID for access control.
            db: Database session.

        Returns:
            List of amendment items (outgoing: docs amended by this order).
        """
        # Verify document belongs to company
        doc_stmt = select(Document).where(
            Document.id == document_id,
            Document.company_id == company_id,
        )
        doc_result = await db.execute(doc_stmt)
        doc = doc_result.scalar_one_or_none()
        if doc is None:
            return []

        # Find all amends links where this document is the source
        stmt = (
            select(DocumentLink)
            .where(
                DocumentLink.source_document_id == document_id,
                DocumentLink.link_type == "amends",
            )
            .order_by(DocumentLink.created_at.desc())
        )
        result = await db.execute(stmt)
        links = result.scalars().all()

        items = []
        for link in links:
            tgt_stmt = select(Document).where(Document.id == link.target_document_id)
            tgt_result = await db.execute(tgt_stmt)
            tgt_doc = tgt_result.scalar_one_or_none()
            if tgt_doc is None:
                continue

            items.append({
                "document_id": tgt_doc.id,
                "link_id": link.id,
                "title": tgt_doc.title,
                "document_type": tgt_doc.document_type,
                "status": tgt_doc.status,
                "created_at": link.created_at,
            })

        return items


# Singleton
document_amendment_service = DocumentAmendmentService()
