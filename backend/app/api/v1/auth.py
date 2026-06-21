from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_auth_service, get_current_user, get_rate_limiter
from app.config import settings
from app.core.exceptions import RateLimitedException
from app.core.rate_limiter import RateLimiter
from app.database import get_db
from app.models.user import User
from app.schemas.auth import (
    LoginRequest,
    LogoutResponse,
    RefreshRequest,
    RefreshResponse,
    RegisterRequest,
    RegisterResponse,
    LoginResponse,
    TokenResponse,
)
from app.schemas.holding import HoldingBrief
from app.schemas.user import UserResponse
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


def _set_refresh_cookie(response: Response, refresh_token: str) -> None:
    """Set refresh token as httpOnly cookie."""
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        max_age=settings.refresh_token_expire_days * 24 * 3600,
        path="/api/v1/auth",
        domain=settings.cookie_domain,
    )


def _delete_refresh_cookie(response: Response) -> None:
    """Clear refresh token cookie."""
    response.delete_cookie(
        key="refresh_token",
        path="/api/v1/auth",
        httponly=True,
        samesite="lax",
        domain=settings.cookie_domain,
    )


@router.post("/register", response_model=RegisterResponse, status_code=201)
async def register(
    request: Request,
    body: RegisterRequest,
    auth_service: AuthService = Depends(get_auth_service),
    rate_limiter: RateLimiter = Depends(get_rate_limiter),
):
    """Register a new user with email and password. Returns tokens immediately."""
    # Rate limiting by email
    rate_key = f"auth:{body.email}"
    allowed, limit, remaining, reset_at = await rate_limiter.is_allowed(rate_key)
    if not allowed:
        headers = {
            "X-RateLimit-Limit": str(limit),
            "X-RateLimit-Remaining": "0",
            "X-RateLimit-Reset": str(reset_at) if reset_at else "0",
        }
        raise RateLimitedException(headers=headers)

    result = await auth_service.register(body.email, body.password)
    return result


@router.post("/login", response_model=LoginResponse)
async def login(
    request: Request,
    response: Response,
    body: LoginRequest,
    auth_service: AuthService = Depends(get_auth_service),
    rate_limiter: RateLimiter = Depends(get_rate_limiter),
):
    """Authenticate with email and password. Returns JWT tokens."""
    # Rate limiting by email
    rate_key = f"auth:{body.email}"
    allowed, limit, remaining, reset_at = await rate_limiter.is_allowed(rate_key)
    if not allowed:
        headers = {
            "X-RateLimit-Limit": str(limit),
            "X-RateLimit-Remaining": "0",
            "X-RateLimit-Reset": str(reset_at) if reset_at else "0",
        }
        raise RateLimitedException(headers=headers)

    result = await auth_service.login(body.email, body.password)

    # Set refresh token as httpOnly cookie
    _set_refresh_cookie(response, result["refresh_token"])

    return LoginResponse(
        access_token=result["access_token"],
        refresh_token=result["refresh_token"],
        token_type="bearer",
        expires_in=result["expires_in"],
    )


@router.post("/refresh", response_model=RefreshResponse)
async def refresh_token(
    request: Request,
    response: Response,
    body: RefreshRequest,
    auth_service: AuthService = Depends(get_auth_service),
):
    """Refresh an access token using a refresh token.
    Reads the refresh token from the httpOnly cookie first.
    Falls back to the request body for backward compatibility.
    The refresh token is rotated: a new cookie is set on success.
    """
    refresh_token_value = request.cookies.get("refresh_token")
    if not refresh_token_value:
        refresh_token_value = body.refresh_token

    if not refresh_token_value:
        from app.core.exceptions import UnauthorizedException
        raise UnauthorizedException(message="Refresh token is required")

    result = await auth_service.refresh_token(refresh_token_value)

    # Rotate refresh token: set new cookie
    _set_refresh_cookie(response, result["refresh_token"])

    return {
        "access_token": result["access_token"],
        "refresh_token": result["refresh_token"],
        "expires_in": result["expires_in"],
    }


@router.post("/logout", response_model=LogoutResponse)
async def logout(response: Response):
    """Clear refresh token cookie to log out."""
    _delete_refresh_cookie(response)
    return {"message": "Logged out"}


@router.get("/me", response_model=UserResponse)
async def get_me(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get current user's profile with holdings."""
    from app.models.holding import Holding
    from app.models.user_holding import UserHolding
    from app.schemas.user import UserHoldingInfo

    active_holding = None
    if user.active_holding:
        active_holding = HoldingBrief.model_validate(user.active_holding)

    # Load user's holdings with roles
    stmt = (
        select(UserHolding, Holding.name)
        .join(Holding, UserHolding.holding_id == Holding.id)
        .where(UserHolding.user_id == user.id)
    )
    result = await db.execute(stmt)
    holdings = []
    for row in result:
        uh, holding_name = row
        holdings.append(UserHoldingInfo(
            holding_id=uh.holding_id,
            holding_name=holding_name,
            role=uh.role,
        ))

    return UserResponse(
        id=user.id,
        email=user.email,
        is_verified=user.is_verified,
        active_holding=active_holding,
        holdings=holdings,
    )
