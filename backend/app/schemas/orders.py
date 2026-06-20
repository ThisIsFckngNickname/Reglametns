from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, field_validator


class OrderUploadResponse(BaseModel):
    id: int
    title: str
    order_number: Optional[str] = None
    order_date: Optional[date] = None
    status: str
    file_type: Optional[str] = None
    file_size: Optional[int] = None

    model_config = {"from_attributes": True}


class OrderResponse(BaseModel):
    id: int
    holding_id: int
    title: str
    order_number: Optional[str] = None
    order_date: Optional[date] = None
    description: Optional[str] = None
    status: str
    file_path: Optional[str] = None
    file_type: Optional[str] = None
    file_size: Optional[int] = None
    created_by: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class OrderListItem(BaseModel):
    id: int
    title: str
    order_number: Optional[str] = None
    order_date: Optional[date] = None
    status: str
    file_type: Optional[str] = None
    file_size: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class OrderUpdate(BaseModel):
    title: Optional[str] = None
    order_number: Optional[str] = None
    order_date: Optional[date] = None
    description: Optional[str] = None
    status: Optional[str] = None

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            allowed = {"draft", "active", "cancelled"}
            if v not in allowed:
                raise ValueError(f"Status must be one of: {', '.join(sorted(allowed))}")
        return v

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            if not v or len(v) > 500:
                raise ValueError("Title must be between 1 and 500 characters")
            return v.strip()
        return v


class OrderDocumentLinkResponse(BaseModel):
    id: int
    order_id: int
    document_id: int
    link_type: str
    description: Optional[str] = None
    created_at: datetime
    document_title: Optional[str] = None
    document_status: Optional[str] = None

    model_config = {"from_attributes": True}


class OrderLinkDocumentRequest(BaseModel):
    document_id: int
    link_type: str = "relates_to"
    description: Optional[str] = None

    @field_validator("link_type")
    @classmethod
    def validate_link_type(cls, v: str) -> str:
        allowed = {"amends", "supersedes", "relates_to"}
        if v not in allowed:
            raise ValueError(f"link_type must be one of: {', '.join(sorted(allowed))}")
        return v
