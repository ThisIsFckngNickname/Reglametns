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
    items: list[LegislationSearchResult]
    total: int
    cached: bool = False


class LegislationSourceListResponse(BaseModel):
    """Response wrapper for listing legislation sources."""

    sources: list[LegislationSource]


# ─── User-Defined Legislation Source Schemas ──────────────────────────


class UserLegislationSource(BaseModel):
    """User-defined legislation source (CRUD-managed)."""

    id: int
    holding_id: int = 0
    name: str
    source_type: str  # 'template_url' | 'static_list' | 'custom_parser'
    url_template: Optional[str] = None
    parser_type: Optional[str] = None  # 'html' | 'json' | 'xml' | 'text'
    selector: Optional[str] = None
    is_active: bool = True
    is_paid: bool = False
    icon_url: Optional[str] = None
    description: Optional[str] = None
    created_at: str
    updated_at: str


class UserLegislationSourceCreate(BaseModel):
    """Create a new user-defined legislation source."""

    name: str
    source_type: str = "template_url"
    url_template: Optional[str] = None
    parser_type: Optional[str] = None
    selector: Optional[str] = None
    is_paid: bool = False
    icon_url: Optional[str] = None
    description: Optional[str] = None


class UserLegislationSourceUpdate(BaseModel):
    """Update an existing user-defined legislation source."""

    name: Optional[str] = None
    source_type: Optional[str] = None
    url_template: Optional[str] = None
    parser_type: Optional[str] = None
    selector: Optional[str] = None
    is_active: Optional[bool] = None
    is_paid: Optional[bool] = None
    icon_url: Optional[str] = None
    description: Optional[str] = None


class UserLegislationSourceSearchResult(BaseModel):
    """A single search result from a user-defined source."""

    title: str
    url: str
    snippet: str
    date: Optional[str] = None
    source_name: str = ""


class UserLegislationSourceSearchRequest(BaseModel):
    """Search request body."""

    query: str
