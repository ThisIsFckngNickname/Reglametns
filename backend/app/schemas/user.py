from typing import Optional

from pydantic import BaseModel

from app.schemas.holding import HoldingBrief


class UserResponse(BaseModel):
    id: int
    email: str
    is_verified: bool
    active_holding: Optional[HoldingBrief] = None

    model_config = {"from_attributes": True}


class SetHoldingRequest(BaseModel):
    holding_id: int


class SetHoldingResponse(BaseModel):
    message: str
    active_holding: HoldingBrief


class ErrorDetail(BaseModel):
    code: str
    message: str
    field: Optional[str] = None


class ErrorResponse(BaseModel):
    detail: ErrorDetail
