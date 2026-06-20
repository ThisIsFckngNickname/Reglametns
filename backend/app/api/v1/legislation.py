"""
API router for legislation search endpoints.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.database import get_db
from app.models.user import User
from app.schemas.legislation import (
    LegislationSearchResponse,
    LegislationSourceListResponse,
)
from app.services.legislation_service import legislation_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/legislation", tags=["legislation"])


@router.get("/search", response_model=LegislationSearchResponse)
async def search_legislation(
    query: str = Query(..., min_length=2, description="Search query"),
    source: Optional[str] = Query(None, description="Source ID filter"),
    max_results: int = Query(10, ge=1, le=50, description="Max results"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Search external legislation sources for legal documents matching the query.

    Uses the built-in pravo.gov.ru adapter. Results are cached for 5 minutes.
    """
    results, used_source, was_cached = await legislation_service.search(
        query=query,
        source_id=source,
        max_results=max_results,
    )

    return LegislationSearchResponse(
        query=query,
        source=used_source,
        results=results,
        total=len(results),
        cached=was_cached,
    )


@router.get("/sources", response_model=LegislationSourceListResponse)
async def list_legislation_sources(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    List all registered legislation sources with metadata.
    """
    sources = legislation_service.get_sources()
    return LegislationSourceListResponse(sources=sources)
