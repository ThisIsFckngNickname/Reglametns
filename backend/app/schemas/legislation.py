"""
Pydantic schemas for legislation search.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class LegislationSource(BaseModel):
    """Represents a legislation data source."""

    id: str
    name: str
    description: str
    base_url: str
    enabled: bool = True


class LegislationSearchResult(BaseModel):
    """A single result from a legislation search."""

    title: str
    url: Optional[str] = None
    snippet: Optional[str] = None
    document_number: Optional[str] = None
    document_date: Optional[str] = None
    source: str = "pravo.gov.ru"


class LegislationSearchResponse(BaseModel):
    """Response wrapper for legislation search."""

    query: str
    source: str
    results: list[LegislationSearchResult]
    total: int
    cached: bool = False


class LegislationSourceListResponse(BaseModel):
    """Response wrapper for listing legislation sources."""

    sources: list[LegislationSource]
