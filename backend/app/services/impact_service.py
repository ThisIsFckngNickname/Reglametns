"""
Impact Map service.

Aggregates relations from DocumentLink and OrderDocumentLink
to build a complete impact map for a given document.
"""

import logging
from typing import Dict, List, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundException
from app.models.document import Document
from app.models.document_link import DocumentLink
from app.models.order import Order
from app.models.order_document_link import OrderDocumentLink
from app.schemas.impact import (
    GraphEdge,
    GraphNode,
    ImpactGraphResponse,
    ImpactMapDirection,
    ImpactMapItem,
    ImpactMapResponse,
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

        Links are classified as:
        - incoming: other documents/orders that link TO this document
        - outgoing: this document links TO other documents/orders
        """
        doc = await self._get_document(document_id, holding_id, db)
        doc_links, od_links, linked_docs, orders = await self._load_all_relations(
            document_id, db
        )

        incoming_orders, incoming_docs, outgoing_docs = self._classify_links(
            doc_id=doc.id,
            doc_links=doc_links,
            od_links=od_links,
            linked_docs=linked_docs,
            orders=orders,
        )

        total = len(incoming_docs) + len(outgoing_docs) + len(incoming_orders)

        graph = self._build_graph_dict(
            doc, doc_links, od_links, linked_docs, orders
        )

        return ImpactMapResponse(
            document_id=doc.id,
            document_title=doc.title,
            incoming=ImpactMapDirection(
                orders=incoming_orders,
                documents=incoming_docs,
            ),
            outgoing=ImpactMapDirection(
                orders=[],  # No outgoing orders in current model
                documents=outgoing_docs,
            ),
            total_relations=total,
            graph=graph,
        )

    async def get_impact_graph(
        self,
        document_id: int,
        holding_id: int,
        db: AsyncSession,
    ) -> ImpactGraphResponse:
        """Build only the graph data for the impact visualisation."""
        doc = await self._get_document(document_id, holding_id, db)
        doc_links, od_links, linked_docs, orders = await self._load_all_relations(
            document_id, db
        )
        return self._build_graph(doc, doc_links, od_links, linked_docs, orders)

    # ------------------------------------------------------------------
    # Data loading
    # ------------------------------------------------------------------

    async def _load_all_relations(
        self,
        document_id: int,
        db: AsyncSession,
    ) -> Tuple[
        List[DocumentLink],
        List[OrderDocumentLink],
        Dict[int, Document],
        Dict[int, Order],
    ]:
        """Load all link records and their referenced entities in batch."""
        # Document links
        stmt = select(DocumentLink).where(
            (DocumentLink.source_document_id == document_id)
            | (DocumentLink.target_document_id == document_id)
        ).order_by(DocumentLink.created_at.desc())
        result = await db.execute(stmt)
        doc_links: List[DocumentLink] = list(result.scalars().all())

        # Order-document links
        stmt2 = select(OrderDocumentLink).where(
            OrderDocumentLink.document_id == document_id,
        ).order_by(OrderDocumentLink.created_at.desc())
        result2 = await db.execute(stmt2)
        od_links: List[OrderDocumentLink] = list(result2.scalars().all())

        # Collect referenced document IDs
        linked_doc_ids: set[int] = set()
        for link in doc_links:
            if link.target_document_id == document_id:
                linked_doc_ids.add(link.source_document_id)
            else:
                linked_doc_ids.add(link.target_document_id)

        # Collect referenced order IDs
        order_ids: set[int] = {odl.order_id for odl in od_links}

        # Batch-load linked documents
        linked_docs: Dict[int, Document] = {}
        if linked_doc_ids:
            stmt3 = select(Document).where(Document.id.in_(linked_doc_ids))
            result3 = await db.execute(stmt3)
            for d in result3.scalars().all():
                linked_docs[d.id] = d

        # Batch-load orders
        orders: Dict[int, Order] = {}
        if order_ids:
            stmt4 = select(Order).where(Order.id.in_(order_ids))
            result4 = await db.execute(stmt4)
            for o in result4.scalars().all():
                orders[o.id] = o

        return doc_links, od_links, linked_docs, orders

    # ------------------------------------------------------------------
    # Classification
    # ------------------------------------------------------------------

    def _classify_links(
        self,
        doc_id: int,
        doc_links: List[DocumentLink],
        od_links: List[OrderDocumentLink],
        linked_docs: Dict[int, Document],
        orders: Dict[int, Order],
    ) -> Tuple[List[ImpactMapItem], List[ImpactMapItem], List[ImpactMapItem]]:
        """Classify links into incoming/outgoing groups.

        Returns:
            (incoming_orders, incoming_docs, outgoing_docs)
        """
        incoming_docs: List[ImpactMapItem] = []
        outgoing_docs: List[ImpactMapItem] = []

        for link in doc_links:
            if link.target_document_id == doc_id:
                # Another document links TO this document -> incoming
                linked_doc = linked_docs.get(link.source_document_id)
                incoming_docs.append(self._make_doc_item(link, linked_doc))
            else:
                # This document links TO another document -> outgoing
                linked_doc = linked_docs.get(link.target_document_id)
                outgoing_docs.append(self._make_doc_item(link, linked_doc))

        # Order links are always incoming from the document's perspective
        incoming_orders: List[ImpactMapItem] = [
            self._make_order_item(odl, orders.get(odl.order_id))
            for odl in od_links
        ]

        return incoming_orders, incoming_docs, outgoing_docs

    # ------------------------------------------------------------------
    # Item builders
    # ------------------------------------------------------------------

    def _make_doc_item(
        self,
        link: DocumentLink,
        linked_doc: Document | None,
    ) -> ImpactMapItem:
        """Build an ImpactMapItem from a DocumentLink record."""
        return ImpactMapItem(
            id=link.id,
            title=linked_doc.title if linked_doc else "Unknown",
            type=link.link_type,
            date=link.created_at.isoformat() if link.created_at else None,
            document_id=linked_doc.id if linked_doc else None,
        )

    def _make_order_item(
        self,
        odl: OrderDocumentLink,
        order: Order | None,
    ) -> ImpactMapItem:
        """Build an ImpactMapItem from an OrderDocumentLink record."""
        # Prefer order_date for display, fall back to created_at
        date_str: str | None = None
        if order and order.order_date:
            date_str = order.order_date.isoformat()
        elif odl.created_at:
            date_str = odl.created_at.isoformat()

        return ImpactMapItem(
            id=odl.id,
            title=order.title if order else "Unknown",
            type=odl.link_type,
            date=date_str,
            order_id=odl.order_id,
        )

    # ------------------------------------------------------------------
    # Graph builders
    # ------------------------------------------------------------------

    def _build_graph_dict(
        self,
        doc: Document,
        doc_links: List[DocumentLink],
        od_links: List[OrderDocumentLink],
        linked_docs: Dict[int, Document],
        orders: Dict[int, Order],
    ) -> dict:
        """Build graph dict for embedding in ImpactMapResponse."""
        graph = self._build_graph(doc, doc_links, od_links, linked_docs, orders)
        return graph.model_dump(mode="json")

    def _build_graph(
        self,
        doc: Document,
        doc_links: List[DocumentLink],
        od_links: List[OrderDocumentLink],
        linked_docs: Dict[int, Document],
        orders: Dict[int, Order],
    ) -> ImpactGraphResponse:
        """Build nodes and edges for visual graph."""
        nodes: List[GraphNode] = []
        edges: List[GraphEdge] = []
        seen_node_ids: set[str] = set()

        # Central document node
        center_id = f"doc:{doc.id}"
        nodes.append(GraphNode(
            id=center_id,
            label=doc.title,
            type="document",
            status=doc.status,
            documentId=doc.id,
        ))
        seen_node_ids.add(center_id)

        # Document link nodes + edges
        for link in doc_links:
            # Determine the "other" document
            if link.source_document_id == doc.id:
                linked_id = link.target_document_id
            else:
                linked_id = link.source_document_id

            node_id = f"doc:{linked_id}"
            if node_id not in seen_node_ids:
                linked_doc = linked_docs.get(linked_id)
                nodes.append(GraphNode(
                    id=node_id,
                    label=linked_doc.title if linked_doc else "Unknown",
                    type="document",
                    status=linked_doc.status if linked_doc else "unknown",
                    documentId=linked_id,
                ))
                seen_node_ids.add(node_id)

            edges.append(GraphEdge(
                source=f"doc:{link.source_document_id}",
                target=f"doc:{link.target_document_id}",
                type=link.link_type,
                label=link.link_type,
            ))

        # Order link nodes + edges
        for odl in od_links:
            node_id = f"order:{odl.order_id}"
            if node_id not in seen_node_ids:
                order = orders.get(odl.order_id)
                nodes.append(GraphNode(
                    id=node_id,
                    label=order.title if order else "Unknown",
                    type="order",
                    status=order.status if order else "active",
                    orderId=odl.order_id,
                ))
                seen_node_ids.add(node_id)

            edges.append(GraphEdge(
                source=node_id,
                target=center_id,
                type=odl.link_type,
                label=odl.link_type,
            ))

        return ImpactGraphResponse(nodes=nodes, edges=edges)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

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
