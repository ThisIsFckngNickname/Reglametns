"""
Pydantic schemas for generation requests.
"""

from typing import Optional

from pydantic import BaseModel, field_validator

ALLOWED_DOCUMENT_TYPES = {"regulation", "order", "provision", "policy", "directive"}


class GenerateRequestV2(BaseModel):
    """Request body for V2 generation endpoint."""
    topic: str
    document_type: str = "regulation"
    company_id: int
    draft_file_id: Optional[int] = None
    influence_document_ids: Optional[list[int]] = None
    search_enabled: bool = True

    @field_validator("topic")
    @classmethod
    def validate_topic(cls, v: str) -> str:
        if not v or len(v) < 20:
            raise ValueError("Topic must be at least 20 characters")
        return v.strip()

    @field_validator("document_type")
    @classmethod
    def validate_document_type(cls, v: str) -> str:
        if v not in ALLOWED_DOCUMENT_TYPES:
            raise ValueError(
                f"Invalid document_type '{v}'. "
                f"Allowed: {', '.join(sorted(ALLOWED_DOCUMENT_TYPES))}"
            )
        return v

    @field_validator("company_id")
    @classmethod
    def validate_company_id(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("company_id must be a positive integer")
        return v
