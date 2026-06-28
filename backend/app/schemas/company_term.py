"""
Pydantic schemas for CompanyTerm and CompanyAbbreviation.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, field_validator


# ─── CompanyTerm ─────────────────────────────────────────────────────────

class CompanyTermCreate(BaseModel):
    term: str
    definition: str

    @field_validator("term")
    @classmethod
    def validate_term(cls, v: str) -> str:
        if not v or len(v) > 255:
            raise ValueError("Term must be between 1 and 255 characters")
        return v.strip()

    @field_validator("definition")
    @classmethod
    def validate_definition(cls, v: str) -> str:
        if not v:
            raise ValueError("Definition is required")
        return v.strip()


class CompanyTermUpdate(BaseModel):
    term: Optional[str] = None
    definition: Optional[str] = None

    @field_validator("term")
    @classmethod
    def validate_term(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            if not v or len(v) > 255:
                raise ValueError("Term must be between 1 and 255 characters")
            return v.strip()
        return v

    @field_validator("definition")
    @classmethod
    def validate_definition(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not v:
            raise ValueError("Definition cannot be empty")
        if v is not None:
            return v.strip()
        return v


class CompanyTermResponse(BaseModel):
    id: int
    company_id: int
    term: str
    definition: str
    source_document_id: Optional[int] = None
    source_document_title: Optional[str] = None
    is_manual: bool = False
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CompanyTermListResponse(BaseModel):
    items: list[CompanyTermResponse]
    total: int
    page: int
    page_size: int
    pages: int


# ─── CompanyAbbreviation ─────────────────────────────────────────────────

class CompanyAbbreviationCreate(BaseModel):
    abbreviation: str
    full_form: str

    @field_validator("abbreviation")
    @classmethod
    def validate_abbreviation(cls, v: str) -> str:
        if not v or len(v) > 50:
            raise ValueError("Abbreviation must be between 1 and 50 characters")
        return v.strip()

    @field_validator("full_form")
    @classmethod
    def validate_full_form(cls, v: str) -> str:
        if not v or len(v) > 500:
            raise ValueError("Full form must be between 1 and 500 characters")
        return v.strip()


class CompanyAbbreviationUpdate(BaseModel):
    abbreviation: Optional[str] = None
    full_form: Optional[str] = None

    @field_validator("abbreviation")
    @classmethod
    def validate_abbreviation(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            if not v or len(v) > 50:
                raise ValueError("Abbreviation must be between 1 and 50 characters")
            return v.strip()
        return v

    @field_validator("full_form")
    @classmethod
    def validate_full_form(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            if not v or len(v) > 500:
                raise ValueError("Full form must be between 1 and 500 characters")
            return v.strip()
        return v


class CompanyAbbreviationResponse(BaseModel):
    id: int
    company_id: int
    abbreviation: str
    full_form: str
    source_document_id: Optional[int] = None
    source_document_title: Optional[str] = None
    is_manual: bool = False
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CompanyAbbreviationListResponse(BaseModel):
    items: list[CompanyAbbreviationResponse]
    total: int
    page: int
    page_size: int
    pages: int
