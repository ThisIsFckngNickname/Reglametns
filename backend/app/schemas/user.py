from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from app.schemas.company import CompanyBrief


class UserCompanyInfo(BaseModel):
    company_id: int
    company_name: str
    role: str

    model_config = {"from_attributes": True}


class UserResponse(BaseModel):
    id: int
    email: str
    is_verified: bool
    active_company: Optional[CompanyBrief] = None
    companies: list[UserCompanyInfo] = []

    model_config = {"from_attributes": True}


class AdminUserCreate(BaseModel):
    email: str
    password: str
    company_id: Optional[int] = None
    role: str = "user"


class AdminUserUpdate(BaseModel):
    email: Optional[str] = None
    password: Optional[str] = None
    is_verified: Optional[bool] = None
    is_banned: Optional[bool] = None


class AdminUserResponse(BaseModel):
    id: int
    email: str
    is_verified: bool
    is_banned: bool = False
    active_company: Optional[CompanyBrief] = None
    companies: list[UserCompanyInfo] = []
    created_at: datetime

    model_config = {"from_attributes": True}


class SetCompanyRequest(BaseModel):
    company_id: int


class SetCompanyResponse(BaseModel):
    message: str
    active_company: CompanyBrief
