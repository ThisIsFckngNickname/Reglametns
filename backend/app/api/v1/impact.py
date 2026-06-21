"""
API router for Impact Map endpoints.
"""

import logging

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_active_holding
from app.database import get_db
from app.models.user import User
from app.schemas.impact import ImpactGraphResponse, ImpactMapResponse
from app.services.impact_service import impact_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/documents", tags=["impact"])


@router.get("/{document_id}/impact", response_model=ImpactMapResponse)
async def get_document_impact_map(
    document_id: int,
    user: User = Depends(require_active_holding),
    db: AsyncSession = Depends(get_db),
):
    """
    Build an impact map for the given document.

    Aggregates all relations from:
    - DocumentLink (manual and automatic links between documents)
    - OrderDocumentLink (orders that affect this document)

    Returns a unified view of:
    - document_links: all other documents linked to this one
    - order_links: all orders that reference this document
    - total_relations: count of all relations
    """
    result = await impact_service.get_impact_map(
        document_id=document_id,
        holding_id=user.active_holding_id,
        db=db,
    )
    return result


@router.get("/{document_id}/impact/graph", response_model=ImpactGraphResponse)
async def get_document_impact_graph(
    document_id: int,
    user: User = Depends(require_active_holding),
    db: AsyncSession = Depends(get_db),
):
    """
    Build graph data (nodes + edges) for the impact visualisation.

    This is a separate endpoint so the graph can be lazy-loaded
    independently of the table data.
    """
    return await impact_service.get_impact_graph(
        document_id=document_id,
        holding_id=user.active_holding_id,
        db=db,
    )
