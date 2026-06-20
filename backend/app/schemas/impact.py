"""
Pydantic schemas for Impact Map (document relations).
"""

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel


class DocumentLinkImpact(BaseModel):
    """A link from a DocumentLink record."""

    id: int
    linked_document_id: int
    linked_document_title: str
    linked_document_status: str
    link_type: str
    is_manual: bool
    description: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class OrderLinkImpact(BaseModel):
    """A link from an OrderDocumentLink record."""

    id: int
    order_id: int
    order_title: str
    order_number: Optional[str] = None
    order_date: Optional[date] = None
    order_status: str = "active"
    link_type: str
    description: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class GraphNode(BaseModel):
    """A node in the visualisation graph."""
    id: str
    type: str  # "document" or "order"
    title: str
    status: str


class GraphEdge(BaseModel):
    """An edge in the visualisation graph."""
    source: str
    target: str
    type: str
    label: str


class ImpactMapResponse(BaseModel):
    """Aggregated impact map for a document."""

    document_id: int
    document_title: str
    document_links: list[DocumentLinkImpact] = []
    order_links: list[OrderLinkImpact] = []
    total_relations: int = 0
    graph: Optional[dict] = None  # {"nodes": [...], "edges": [...]}
