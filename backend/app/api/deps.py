from typing import AsyncGenerator

from fastapi import Depends, Header, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ForbiddenException, UnauthorizedException
from app.core.rate_limiter import RateLimiter
from app.core.security import decode_token
from app.database import get_db
from app.models.user import User
from app.models.user_holding import UserHolding
from app.services.auth_service import AuthService
from app.services.email_service import ConsoleEmailService, EmailService

security_scheme = HTTPBearer(auto_error=False)


async def get_email_service(request: Request) -> EmailService:
    """Get the email service from app state."""
    return request.app.state.email_service


async def get_rate_limiter(request: Request) -> RateLimiter:
    """Get the rate limiter from app state."""
    return request.app.state.rate_limiter


async def get_current_user(
    db: AsyncSession = Depends(get_db),
    credentials: HTTPAuthorizationCredentials | None = Depends(security_scheme),
) -> User:
    """Dependency that extracts and validates JWT, returns User."""
    if credentials is None:
        raise UnauthorizedException(message="Not authenticated")

    token = credentials.credentials
    payload = decode_token(token)

    if payload is None:
        raise UnauthorizedException(message="Invalid or expired token")

    if payload.get("type") != "access":
        raise UnauthorizedException(message="Invalid token type")

    user_id = int(payload.get("sub", 0))
    if not user_id:
        raise UnauthorizedException(message="Invalid token payload")

    stmt = select(User).where(User.id == user_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if user is None or not user.is_verified:
        raise UnauthorizedException(
            message="User not found or not verified"
        )

    return user


async def require_admin(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Dependency that checks if the user has admin role in any holding."""
    stmt = select(UserHolding).where(
        UserHolding.user_id == user.id,
        UserHolding.role == "admin",
    )
    result = await db.execute(stmt)
    admin_entry = result.scalar_one_or_none()

    if admin_entry is None:
        raise ForbiddenException(
            message="Admin privileges required"
        )

    return user


async def get_auth_service(
    db: AsyncSession = Depends(get_db),
    email_service: EmailService = Depends(get_email_service),
) -> AsyncGenerator[AuthService, None]:
    """Get an AuthService instance."""
    service = AuthService(db=db, email_service=email_service)
    yield service


async def require_active_holding(
    current_user: User = Depends(get_current_user),
) -> User:
    """Check that user has an active holding selected."""
    if not current_user.active_holding_id:
        from app.core.exceptions import NoActiveHolding
        raise NoActiveHolding()
    return current_user
