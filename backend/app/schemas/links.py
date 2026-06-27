from datetime import datetime
from typing import Optional

from pydantic import BaseModel, field_validator


class DocumentLinkCreate(BaseModel):
    target_document_id: int
    link_type: str  # references, amends, supersedes, related
    description: Optional[str] = None

    @field_validator("link_type")
    @classmethod
    def validate_link_type(cls, v: str) -> str:
        allowed = {"references", "amends", "supersedes", "related"}
        if v not in allowed:
            raise ValueError(f"link_type must be one of: {', '.join(sorted(allowed))}")
        return v


class DocumentLinkResponse(BaseModel):
    id: int
    source_document_id: int
    target_document_id: int
    link_type: str
    is_manual: bool
    description: Optional[str] = None
    created_by: Optional[int] = None
    created_at: datetime
    target_title: Optional[str] = None
    target_status: Optional[str] = None

    model_config = {"from_attributes": True}


class DocumentLinkSourceResponse(BaseModel):
    """A link shown from the source document's perspective."""
    id: int
    target_document_id: int
    link_type: str
    is_manual: bool
    description: Optional[str] = None
    created_by: Optional[int] = None
    created_at: datetime
    target_title: Optional[str] = None
    target_status: Optional[str] = None

    model_config = {"from_attributes": True}


class AnalysisResponse(BaseModel):
    """Response from a document analysis trigger."""
    document_id: int
    company_id: int
    structure_extracted: bool = False
    style_extracted: bool = False
    terms_collected: int = 0
    abbreviations_collected: int = 0
    message: str = ""
