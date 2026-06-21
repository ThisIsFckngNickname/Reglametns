"""
Pydantic schemas for Impact Map (document relations).
"""

from typing import Optional

from pydantic import BaseModel


class ImpactMapItem(BaseModel):
    """A single relation item in the impact map (matches frontend ImpactItem type).

    Contains only the fields the frontend needs for table display.
    Extra fields (document_id, order_id) are included for test assertions
    and future extensibility but are not consumed by the frontend.
    """
    id: int  # link record id (DocumentLink.id or OrderDocumentLink.id)
    title: str  # linked entity title
    type: str  # link_type e.g. "amends", "references", "supersedes", "related"
    date: Optional[str] = None  # ISO date string
    document_id: Optional[int] = None
    order_id: Optional[int] = None


class ImpactMapDirection(BaseModel):
    """Links grouped by entity type for one direction (incoming or outgoing)."""
    orders: list[ImpactMapItem] = []
    documents: list[ImpactMapItem] = []


class GraphNode(BaseModel):
    """A node in the visualisation graph."""
    id: str
    label: str  # display text for cytoscape node
    type: str  # "document" or "order"
    status: str
    documentId: Optional[int] = None
    orderId: Optional[int] = None


class GraphEdge(BaseModel):
    """An edge in the visualisation graph."""
    source: str
    target: str
    type: str
    label: str


class ImpactGraphResponse(BaseModel):
    """Graph data (nodes + edges) for the impact visualisation."""
    nodes: list[GraphNode] = []
    edges: list[GraphEdge] = []


class ImpactMapResponse(BaseModel):
    """Aggregated impact map for a document."""

    document_id: int
    document_title: str
    incoming: ImpactMapDirection = ImpactMapDirection()
    outgoing: ImpactMapDirection = ImpactMapDirection()
    total_relations: int = 0
    graph: Optional[dict] = None  # {"nodes": [...], "edges": [...]}
