from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, field_validator


class CompanyCreate(BaseModel):
    name: str
    inn: Optional[str] = None
    legal_form: str
    document_structure: Optional[dict[str, Any]] = None
    style_settings: Optional[dict[str, Any]] = None
    use_gost: bool = False

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        if not v or len(v) > 255:
            raise ValueError("Name must be between 1 and 255 characters")
        return v.strip()

    @field_validator("inn")
    @classmethod
    def validate_inn(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            if not v.isdigit() or (len(v) != 10 and len(v) != 12):
                raise ValueError("INN must be 10 or 12 digits")
        return v

    @field_validator("legal_form")
    @classmethod
    def validate_legal_form(cls, v: str) -> str:
        allowed = ["ООО", "АО", "ПАО", "иное"]
        if v not in allowed:
            raise ValueError(f"Legal form must be one of: {', '.join(allowed)}")
        return v


class CompanyUpdate(BaseModel):
    name: Optional[str] = None
    inn: Optional[str] = None
    legal_form: Optional[str] = None
    document_structure: Optional[dict[str, Any]] = None
    style_settings: Optional[dict[str, Any]] = None
    use_gost: Optional[bool] = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            if not v or len(v) > 255:
                raise ValueError("Name must be between 1 and 255 characters")
        return v.strip() if v else v

    @field_validator("inn")
    @classmethod
    def validate_inn(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            if not v.isdigit() or (len(v) != 10 and len(v) != 12):
                raise ValueError("INN must be 10 or 12 digits")
        return v

    @field_validator("legal_form")
    @classmethod
    def validate_legal_form(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            allowed = ["ООО", "АО", "ПАО", "иное"]
            if v not in allowed:
                raise ValueError(f"Legal form must be one of: {', '.join(allowed)}")
        return v


class CompanyResponse(BaseModel):
    id: int
    name: str
    inn: Optional[str] = None
    legal_form: str
    document_structure: Optional[dict[str, Any]] = None
    style_settings: Optional[dict[str, Any]] = None
    use_gost: bool = False
    created_at: datetime

    model_config = {"from_attributes": True}


class CompanyBrief(BaseModel):
    id: int
    name: str
    inn: Optional[str] = None
    legal_form: str
    document_structure: Optional[dict[str, Any]] = None
    style_settings: Optional[dict[str, Any]] = None
    use_gost: bool = False

    model_config = {"from_attributes": True}
