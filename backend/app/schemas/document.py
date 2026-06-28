from datetime import datetime
from typing import Generic, List, Optional, TypeVar

from pydantic import BaseModel, field_validator

from app.models.document_status import DocumentStatus

T = TypeVar("T")


# ─── Paginated Response ───────────────────────────────────────────────

class PaginatedResponse(BaseModel, Generic[T]):
    items: List[T]
    total: int
    page: int
    page_size: int
    pages: int


# ─── Document ──────────────────────────────────────────────────────────

class DocumentCreate(BaseModel):
    title: str
    description: Optional[str] = None

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: str) -> str:
        if not v or len(v) > 500:
            raise ValueError("Title must be between 1 and 500 characters")
        return v.strip()


class DocumentUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[DocumentStatus] = None

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            if not v or len(v) > 500:
                raise ValueError("Title must be between 1 and 500 characters")
            return v.strip()
        return v

    @field_validator("status")
    @classmethod
    def validate_status(cls, v):
        if v is not None:
            allowed = {s.value for s in DocumentStatus}
            if v not in allowed:
                raise ValueError(f"Invalid status '{v}'. Allowed: {', '.join(sorted(allowed))}")
        return v


class StatusChangeRequest(BaseModel):
    """Request body for changing document status with optional comment."""
    status: DocumentStatus
    comment: Optional[str] = None


class DocumentStats(BaseModel):
    """Statistics about a document."""
    sections_count: int = 0
    tables_count: int = 0
    terms_count: int = 0
    abbreviations_count: int = 0
    versions_count: int = 0


class DocumentVersionBrief(BaseModel):
    """Brief information about a document version for display."""
    id: int
    version_number: int
    file_type: str
    file_size: int
    created_at: datetime

    model_config = {"from_attributes": True}


class DocumentResponse(BaseModel):
    id: int
    company_id: int
    title: str
    description: Optional[str] = None
    status: DocumentStatus
    created_by: Optional[dict] = None  # {"id": int, "email": str}
    was_analyzed: bool = False
    current_version: Optional[DocumentVersionBrief] = None
    stats: DocumentStats = DocumentStats()
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DocumentListItem(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    status: DocumentStatus
    was_analyzed: bool = False
    created_at: datetime
    updated_at: datetime
    file_type: Optional[str] = None
    file_size: Optional[int] = None
    version_number: Optional[int] = None

    model_config = {"from_attributes": True}


# ─── Document Version ──────────────────────────────────────────────────

class DocumentVersionResponse(BaseModel):
    id: int
    document_id: int
    version_number: int
    file_type: str
    file_size: int
    mime_type: str
    version_notes: Optional[str] = None
    uploaded_by: Optional[int] = None
    created_at: datetime

    model_config = {"from_attributes": True}


# ─── Document Section ──────────────────────────────────────────────────

class DocumentSectionResponse(BaseModel):
    id: int
    document_version_id: int
    parent_id: Optional[int] = None
    title: str
    level: int
    order_num: int
    content: Optional[str] = None
    children: List["DocumentSectionResponse"] = []

    model_config = {"from_attributes": True}


# ─── Document Term ─────────────────────────────────────────────────────

class DocumentTermResponse(BaseModel):
    id: int
    document_id: int
    term: str
    definition: str

    model_config = {"from_attributes": True}


# ─── Document Abbreviation ─────────────────────────────────────────────

class DocumentAbbreviationResponse(BaseModel):
    id: int
    document_id: int
    abbreviation: str
    full_form: str

    model_config = {"from_attributes": True}


# ─── Document Table ────────────────────────────────────────────────────

class DocumentTableResponse(BaseModel):
    id: int
    document_version_id: int
    section_id: Optional[int] = None
    caption: Optional[str] = None
    order_num: int
    html_content: str
    rows_count: int
    cols_count: int

    model_config = {"from_attributes": True}


# ─── Version Diff ──────────────────────────────────────────────────────

class SectionDiffItem(BaseModel):
    """Diff status for a single section between two versions."""
    section_id: int
    title: str
    status: str  # "added", "removed", "changed", "unchanged"


class VersionDiffResponse(BaseModel):
    from_version: DocumentVersionResponse
    to_version: DocumentVersionResponse
    changes: List[str] = []
    sections_diff: List[SectionDiffItem] = []
    metadata_changes: dict = {}
    full_text_diff: Optional[str] = None


# ─── Upload Response ───────────────────────────────────────────────────

class UploadResponse(BaseModel):
    id: int
    title: str
    status: str
    file_type: str
    file_size: int
    sections_count: int = 0
    tables_count: int = 0
    terms_count: int = 0
    abbreviations_count: int = 0
    lists_count: int = 0

    model_config = {"from_attributes": True}
