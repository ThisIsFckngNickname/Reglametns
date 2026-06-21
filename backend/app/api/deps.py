from typing import AsyncGenerator

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ForbiddenException, UnauthorizedException
from app.core.rate_limiter import RateLimiter
from app.core.security import decode_token
from app.database import get_db
from app.models.user import User
from app.models.user_company import UserCompany
from app.services.auth_service import AuthService

security_scheme = HTTPBearer(auto_error=False)


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

    if user is None:
        raise UnauthorizedException(
            message="User not found"
        )

    return user


async def require_admin(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Dependency that checks if the user has admin role in any company."""
    stmt = select(UserCompany).where(
        UserCompany.user_id == user.id,
        UserCompany.role == "admin",
    ).limit(1)
    result = await db.execute(stmt)
    admin_entry = result.scalar_one_or_none()

    if admin_entry is None:
        raise ForbiddenException(
            message="Admin privileges required"
        )

    return user


async def get_auth_service(
    db: AsyncSession = Depends(get_db),
) -> AsyncGenerator[AuthService, None]:
    """Get an AuthService instance."""
    service = AuthService(db=db)
    yield service


async def require_active_company(
    current_user: User = Depends(get_current_user),
) -> User:
    """Check that user has an active company selected."""
    if not current_user.active_company_id:
        from app.core.exceptions import NoActiveCompany
        raise NoActiveCompany()
    return current_user
