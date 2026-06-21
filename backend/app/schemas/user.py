from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from app.schemas.holding import HoldingBrief


class UserHoldingInfo(BaseModel):
    holding_id: int
    holding_name: str
    role: str

    model_config = {"from_attributes": True}


class UserResponse(BaseModel):
    id: int
    email: str
    is_verified: bool
    active_holding: Optional[HoldingBrief] = None
    holdings: list[UserHoldingInfo] = []

    model_config = {"from_attributes": True}


class AdminUserCreate(BaseModel):
    email: str
    password: str
    holding_id: Optional[int] = None
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
    active_holding: Optional[HoldingBrief] = None
    holdings: list[UserHoldingInfo] = []
    created_at: datetime

    model_config = {"from_attributes": True}


class SetHoldingRequest(BaseModel):
    holding_id: int


class SetHoldingResponse(BaseModel):
    message: str
    active_holding: HoldingBrief
