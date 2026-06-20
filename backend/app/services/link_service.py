"""
Service for document link operations.
"""

import logging
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestException, NotFoundException
from app.models.document import Document
from app.models.document_link import DocumentLink
from app.schemas.links import DocumentLinkCreate, DocumentLinkSourceResponse

logger = logging.getLogger(__name__)


class LinkService:
    """Service for managing document links."""

    async def create_link(
        self,
        source_document_id: int,
        body: DocumentLinkCreate,
        user_id: int,
        holding_id: int,
        db: AsyncSession,
    ) -> DocumentLinkSourceResponse:
        """Create a manual link between two documents."""
        # Verify source document exists and belongs to holding
        source_doc = await self._get_document(source_document_id, holding_id, db)

        # Verify target document exists and belongs to holding
        target_doc = await self._get_document(body.target_document_id, holding_id, db)

        if source_document_id == body.target_document_id:
            raise BadRequestException(
                code="SELF_LINK",
                message="Cannot link a document to itself",
            )

        # Check for duplicate link
        stmt = select(DocumentLink).where(
            DocumentLink.source_document_id == source_document_id,
            DocumentLink.target_document_id == body.target_document_id,
            DocumentLink.link_type == body.link_type,
        )
        result = await db.execute(stmt)
        existing = result.scalar_one_or_none()
        if existing:
            raise BadRequestException(
                code="DUPLICATE_LINK",
                message="This link already exists",
            )

        link = DocumentLink(
            source_document_id=source_document_id,
            target_document_id=body.target_document_id,
            link_type=body.link_type,
            description=body.description,
            is_manual=True,
            created_by=user_id,
        )
        db.add(link)
        await db.flush()
        await db.refresh(link)

        return DocumentLinkSourceResponse(
            id=link.id,
            target_document_id=link.target_document_id,
            link_type=link.link_type,
            is_manual=link.is_manual,
            description=link.description,
            created_by=link.created_by,
            created_at=link.created_at,
            target_title=target_doc.title,
            target_status=target_doc.status,
        )

    async def list_links(
        self,
        document_id: int,
        holding_id: int,
        db: AsyncSession,
    ) -> List[DocumentLinkSourceResponse]:
        """List all links for a document (both source and target)."""
        # Verify document exists
        await self._get_document(document_id, holding_id, db)

        # Get outgoing links
        stmt_out = (
            select(DocumentLink)
            .where(DocumentLink.source_document_id == document_id)
            .order_by(DocumentLink.created_at.desc())
        )
        result_out = await db.execute(stmt_out)
        outgoing = result_out.scalars().all()

        # Get incoming links
        stmt_in = (
            select(DocumentLink)
            .where(DocumentLink.target_document_id == document_id)
            .order_by(DocumentLink.created_at.desc())
        )
        result_in = await db.execute(stmt_in)
        incoming = result_in.scalars().all()

        # Combine: outgoing list as-source, incoming list as-target
        items = []
        for link in outgoing:
            target = await self._get_document(link.target_document_id, holding_id, db, raise_not_found=False)
            items.append(DocumentLinkSourceResponse(
                id=link.id,
                target_document_id=link.target_document_id,
                link_type=link.link_type,
                is_manual=link.is_manual,
                description=link.description,
                created_by=link.created_by,
                created_at=link.created_at,
                target_title=target.title if target else "Unknown",
                target_status=target.status if target else None,
            ))
        for link in incoming:
            source = await self._get_document(link.source_document_id, holding_id, db, raise_not_found=False)
            items.append(DocumentLinkSourceResponse(
                id=link.id,
                target_document_id=link.source_document_id,
                link_type=link.link_type,
                is_manual=link.is_manual,
                description=link.description,
                created_by=link.created_by,
                created_at=link.created_at,
                target_title=source.title if source else "Unknown",
                target_status=source.status if source else None,
            ))

        return items

    async def delete_link(
        self,
        link_id: int,
        user_id: int,
        holding_id: int,
        db: AsyncSession,
    ) -> None:
        """Delete a document link."""
        stmt = select(DocumentLink).where(DocumentLink.id == link_id)
        result = await db.execute(stmt)
        link = result.scalar_one_or_none()

        if link is None:
            raise NotFoundException(message="Link not found", field="link_id")

        # Verify at least one of the documents belongs to the holding
        doc_ids = {link.source_document_id, link.target_document_id}
        for doc_id in doc_ids:
            doc = await self._get_document(doc_id, holding_id, db, raise_not_found=False)
            if doc is not None:
                break
        else:
            raise NotFoundException(message="Link not found in your holding")

        await db.delete(link)

    async def _get_document(
        self, document_id: int, holding_id: int, db: AsyncSession, raise_not_found: bool = True
    ) -> Optional[Document]:
        """Get document by id and holding_id."""
        stmt = select(Document).where(
            Document.id == document_id,
            Document.holding_id == holding_id,
        )
        result = await db.execute(stmt)
        doc = result.scalar_one_or_none()
        if doc is None and raise_not_found:
            raise NotFoundException(message="Document not found", field="document_id")
        return doc


# Singleton
link_service = LinkService()
