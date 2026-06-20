from fastapi import APIRouter, Depends

from app.api.deps import get_auth_service, get_current_user
from app.models.user import User
from app.schemas.user import SetHoldingRequest, SetHoldingResponse
from app.services.auth_service import AuthService

router = APIRouter(prefix="/user", tags=["user"])


@router.put("/holding", response_model=SetHoldingResponse)
async def set_active_holding(
    body: SetHoldingRequest,
    user: User = Depends(get_current_user),
    auth_service: AuthService = Depends(get_auth_service),
):
    """Set the active holding for the current user."""
    result = await auth_service.set_active_holding(user.id, body.holding_id)
    return result
