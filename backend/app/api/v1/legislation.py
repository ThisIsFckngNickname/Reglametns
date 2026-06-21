"""
API router for legislation search endpoints.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.database import get_db
from app.models.user import User
from app.schemas.legislation import (
    LegislationSearchResponse,
    LegislationSourceListResponse,
    UserLegislationSource,
    UserLegislationSourceCreate,
    UserLegislationSourceUpdate,
    UserLegislationSourceSearchRequest,
    UserLegislationSourceSearchResult,
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
        items=results,
        total=len(results),
        cached=was_cached,
    )


# ─── Adapter sources (built-in) ──────────────────────────────────────


@router.get("/sources/available", response_model=list[dict])
async def list_available_sources(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    List all available legislation sources (built-in adapters).

    Returns format matching the frontend AvailableSource interface:
    id, display_name, description, is_paid, is_builtin, is_active.
    """
    sources = legislation_service.get_sources()
    return [
        {
            "id": s.id,
            "display_name": s.name,
            "description": s.description,
            "is_paid": False,
            "is_builtin": True,
            "is_active": True,
        }
        for s in sources
    ]


@router.get("/sources/adapters", response_model=LegislationSourceListResponse)
async def list_adapter_sources(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    List all registered built-in adapter sources with metadata.
    """
    sources = legislation_service.get_sources()
    return LegislationSourceListResponse(sources=sources)


# ─── User-defined sources CRUD ───────────────────────────────────────


@router.get("/sources", response_model=list[UserLegislationSource])
async def list_legislation_sources(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    List all user-defined legislation sources.
    """
    return legislation_service.get_user_sources()


@router.post("/sources", response_model=UserLegislationSource, status_code=201)
async def create_legislation_source(
    data: UserLegislationSourceCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Create a new user-defined legislation source.
    """
    source = legislation_service.create_user_source(data.model_dump())
    return source


@router.get("/sources/{source_id}", response_model=UserLegislationSource)
async def get_legislation_source(
    source_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get a single user-defined legislation source by ID.
    """
    source = legislation_service.get_user_source(source_id)
    if not source:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "NOT_FOUND",
                "message": "Source not found",
                "field": "source_id",
            },
        )
    return source


@router.put("/sources/{source_id}", response_model=UserLegislationSource)
async def update_legislation_source(
    source_id: int,
    data: UserLegislationSourceUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Update a user-defined legislation source.
    """
    source = legislation_service.update_user_source(
        source_id,
        data.model_dump(exclude_unset=True),
    )
    if not source:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "NOT_FOUND",
                "message": "Source not found",
                "field": "source_id",
            },
        )
    return source


@router.delete("/sources/{source_id}", status_code=204)
async def delete_legislation_source(
    source_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Delete a user-defined legislation source.
    """
    deleted = legislation_service.delete_user_source(source_id)
    if not deleted:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "NOT_FOUND",
                "message": "Source not found",
                "field": "source_id",
            },
        )
    return None


@router.post(
    "/sources/{source_id}/search",
    response_model=list[UserLegislationSourceSearchResult],
)
async def search_legislation_source(
    source_id: int,
    body: UserLegislationSourceSearchRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Search within a specific user-defined legislation source.
    """
    source = legislation_service.get_user_source(source_id)
    if not source:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "NOT_FOUND",
                "message": "Source not found",
                "field": "source_id",
            },
        )

    results = legislation_service.search_user_source(source_id, body.query)
    return results
