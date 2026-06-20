"""
Impact Map service.

Aggregates relations from DocumentLink and OrderDocumentLink
to build a complete impact map for a given document.
"""

import logging
from typing import List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundException
from app.models.document import Document
from app.models.document_link import DocumentLink
from app.models.order import Order
from app.models.order_document_link import OrderDocumentLink
from app.schemas.impact import (
    DocumentLinkImpact,
    ImpactMapResponse,
    OrderLinkImpact,
)

logger = logging.getLogger(__name__)


class ImpactService:
    """Service for building impact maps (document relations)."""

    async def get_impact_map(
        self,
        document_id: int,
        holding_id: int,
        db: AsyncSession,
    ) -> ImpactMapResponse:
        """
        Build a complete impact map for a document.

        Combines:
        - DocumentLink records (both directions)
        - OrderDocumentLink records (orders affecting/related to the document)
        """
        # Verify document exists and belongs to holding
        doc = await self._get_document(document_id, holding_id, db)

        # Collect document links (both directions)
        doc_links = await self._get_document_links(document_id, db)

        # Collect order links
        order_links = await self._get_order_links(document_id, db)

        total = len(doc_links) + len(order_links)

        # Build graph (nodes + edges for visualisation)
        graph = self._build_graph(doc, doc_links, order_links)

        return ImpactMapResponse(
            document_id=doc.id,
            document_title=doc.title,
            document_links=doc_links,
            order_links=order_links,
            total_relations=total,
            graph=graph,
        )

    async def _get_document_links(
        self,
        document_id: int,
        db: AsyncSession,
    ) -> List[DocumentLinkImpact]:
        """Get all DocumentLink records involving this document."""
        stmt = select(DocumentLink).where(
            (DocumentLink.source_document_id == document_id)
            | (DocumentLink.target_document_id == document_id)
        ).order_by(DocumentLink.created_at.desc())
        result = await db.execute(stmt)
        links = result.scalars().all()

        impacts: list[DocumentLinkImpact] = []
        for link in links:
            # The "other" document id
            if link.source_document_id == document_id:
                linked_id = link.target_document_id
            else:
                linked_id = link.source_document_id

            # Get linked document title/status
            linked_doc = await db.get(Document, linked_id)
            linked_title = linked_doc.title if linked_doc else "Unknown"
            linked_status = linked_doc.status if linked_doc else "unknown"

            impacts.append(DocumentLinkImpact(
                id=link.id,
                linked_document_id=linked_id,
                linked_document_title=linked_title,
                linked_document_status=linked_status,
                link_type=link.link_type,
                is_manual=link.is_manual,
                description=link.description,
                created_at=link.created_at,
            ))

        return impacts

    async def _get_order_links(
        self,
        document_id: int,
        db: AsyncSession,
    ) -> List[OrderLinkImpact]:
        """Get all OrderDocumentLink records for this document."""
        stmt = select(OrderDocumentLink).where(
            OrderDocumentLink.document_id == document_id,
        ).order_by(OrderDocumentLink.created_at.desc())
        result = await db.execute(stmt)
        od_links = result.scalars().all()

        impacts: list[OrderLinkImpact] = []
        for odl in od_links:
            order = await db.get(Order, odl.order_id)
            order_title = order.title if order else "Unknown"
            order_number = order.order_number if order else None
            order_date = order.order_date if order else None

            order_status = order.status if order else "unknown"

            impacts.append(OrderLinkImpact(
                id=odl.id,
                order_id=odl.order_id,
                order_title=order_title,
                order_number=order_number,
                order_date=order_date,
                order_status=order_status,
                link_type=odl.link_type,
                description=odl.description,
                created_at=odl.created_at,
            ))

        return impacts

    def _build_graph(
        self,
        doc: Document,
        doc_links: List,
        order_links: List,
    ) -> dict:
        """Build nodes and edges for visual graph."""
        nodes = []
        edges = []
        seen_node_ids = set()

        # Central document node
        center_id = f"doc:{doc.id}"
        nodes.append({
            "id": center_id,
            "type": "document",
            "title": doc.title,
            "status": doc.status,
        })
        seen_node_ids.add(center_id)

        # Document link nodes + edges
        for link in doc_links:
            linked_id = f"doc:{link.linked_document_id}"
            if linked_id not in seen_node_ids:
                nodes.append({
                    "id": linked_id,
                    "type": "document",
                    "title": link.linked_document_title,
                    "status": link.linked_document_status,
                })
                seen_node_ids.add(linked_id)

            # Edge from linked doc to center (or center to linked?)
            # Convention: source=linked, target=center, type=link_type
            edges.append({
                "source": linked_id,
                "target": center_id,
                "type": link.link_type,
                "label": link.link_type,
            })

        # Order link nodes + edges
        for odl in order_links:
            order_id = f"order:{odl.order_id}"
            if order_id not in seen_node_ids:
                nodes.append({
                    "id": order_id,
                    "type": "order",
                    "title": odl.order_title,
                    "status": odl.order_status,
                })
                seen_node_ids.add(order_id)

            edges.append({
                "source": order_id,
                "target": center_id,
                "type": odl.link_type,
                "label": odl.link_type,
            })

        return {"nodes": nodes, "edges": edges}

    async def _get_document(
        self,
        document_id: int,
        holding_id: int,
        db: AsyncSession,
    ) -> Document:
        """Get document by id and holding_id, or raise 404."""
        stmt = select(Document).where(
            Document.id == document_id,
            Document.holding_id == holding_id,
        )
        result = await db.execute(stmt)
        doc = result.scalar_one_or_none()
        if doc is None:
            raise NotFoundException(message="Document not found", field="document_id")
        return doc


# Singleton
impact_service = ImpactService()
