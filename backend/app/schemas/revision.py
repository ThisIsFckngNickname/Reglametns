"""
Pydantic schemas for Phase 6 — document revision.

Defines request/response models for:
- ReviseRequest / ReviseResponse
- DiffResult / DiffStats
- RevisionHistoryItem / RevisionDetail
- RevisionDiffResponse
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class DiffStats(BaseModel):
    """Statistics about a diff operation."""
    added: int = 0
    removed: int = 0
    changed: int = 0


class DiffResult(BaseModel):
    """Result of a diff operation."""
    unified_diff: str = ""
    html_diff: str = ""
    stats: DiffStats


class ReviseRequest(BaseModel):
    """Request body for POST /documents/{id}/revise."""
    comment: str = Field(
        ..., min_length=10, max_length=5000,
        description="Описание замечания к документу",
    )
    target_section: Optional[str] = Field(
        None, max_length=200,
        description="Целевой раздел для правки (опционально)",
    )


class ReviseResponse(BaseModel):
    """Response after successfully revising a document."""
    document_id: int
    old_text: str
    new_text: str
    diff: DiffResult
    revision_id: Optional[int] = None
    changed: bool = True


class RevisionHistoryItem(BaseModel):
    """Single revision item shown in history list."""
    id: int
    comment: str
    target_section: Optional[str]
    stats: Optional[DiffStats] = None
    created_by_email: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class RevisionDetail(BaseModel):
    """Full detail of a single revision."""
    id: int
    document_id: int
    comment: str
    target_section: Optional[str]
    stats: Optional[DiffStats] = None
    created_by_email: Optional[str] = None
    created_at: datetime
    old_text: Optional[str] = None
    new_text: Optional[str] = None

    model_config = {"from_attributes": True}


class RevisionDiffResponse(BaseModel):
    """Diff response for a specific revision."""
    old_text: str
    new_text: str
    diff: DiffResult
