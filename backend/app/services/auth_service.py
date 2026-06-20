import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    ConflictException,
    ForbiddenException,
    NotFoundException,
    UnauthorizedException,
)
from app.core.security import create_access_token, create_refresh_token, decode_token
from app.models.holding import Holding
from app.models.user import User
from app.models.user_holding import UserHolding
from app.schemas.holding import HoldingBrief
from app.services.code_service import CodeService
from app.services.email_service import EmailService

logger = logging.getLogger(__name__)


class AuthService:
    """Service for authentication operations."""

    def __init__(self, db: AsyncSession, email_service: EmailService):
        self.db = db
        self.email_service = email_service
        self.code_service = CodeService()

    async def register(self, email: str) -> dict:
        """Register a new user or resend code for unverified user."""
        # Check if user exists and is verified
        stmt = select(User).where(User.email == email)
        result = await self.db.execute(stmt)
        user = result.scalar_one_or_none()

        if user and user.is_verified:
            raise ConflictException(
                message="A user with this email already exists",
                field="email",
            )

        if user is None:
            # Create new user
            user = User(email=email, is_verified=False)
            self.db.add(user)
            await self.db.flush()

        # Generate and save code
        code = self.code_service.generate_code()
        await self.code_service.save_code(
            self.db, email, code, "registration", invalidate_previous=True
        )

        # Send code via email service
        await self.email_service.send_code(email, code, "registration")

        return {
            "message": "Verification code sent to email",
            "code_length": 6,
        }

    async def verify_registration(self, email: str, code: str) -> dict:
        """Verify a registration code."""
        # Find user
        stmt = select(User).where(User.email == email)
        result = await self.db.execute(stmt)
        user = result.scalar_one_or_none()

        if user is None:
            raise NotFoundException(
                message="User not found",
                field="email",
            )

        # Verify code
        stored_code = await self.code_service.verify_code(
            self.db, email, code, "registration"
        )

        # Mark code as used
        stored_code.used = True

        # Mark user as verified
        user.is_verified = True

        return {
            "message": "Email verified successfully",
            "verified": True,
        }

    async def login(self, email: str) -> dict:
        """Initiate a login flow by sending a verification code."""
        # Find user
        stmt = select(User).where(User.email == email)
        result = await self.db.execute(stmt)
        user = result.scalar_one_or_none()

        if user is None:
            raise NotFoundException(
                message="User not found",
                field="email",
            )

        if not user.is_verified:
            raise ForbiddenException(
                message="Email is not verified. Please register first.",
            )

        # Generate and save code
        code = self.code_service.generate_code()
        await self.code_service.save_code(
            self.db, email, code, "login", invalidate_previous=True
        )

        # Send code
        await self.email_service.send_code(email, code, "login")

        return {"message": "Verification code sent to email"}

    async def verify_login(self, email: str, code: str) -> dict:
        """Verify a login code and return JWT tokens."""
        # Find user
        stmt = select(User).where(User.email == email)
        result = await self.db.execute(stmt)
        user = result.scalar_one_or_none()

        if user is None:
            raise NotFoundException(
                message="User not found",
                field="email",
            )

        # Verify code
        stored_code = await self.code_service.verify_code(
            self.db, email, code, "login"
        )

        # Mark code as used
        stored_code.used = True

        # Generate tokens
        access_token = create_access_token(user.id)
        refresh_token = create_refresh_token(user.id)

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "expires_in": 900,
        }

    async def refresh_token(self, refresh_token_str: str) -> dict:
        """Refresh an access token using a refresh token."""
        payload = decode_token(refresh_token_str)

        if payload is None:
            raise UnauthorizedException(
                message="Invalid or expired refresh token"
            )

        if payload.get("type") != "refresh":
            raise UnauthorizedException(
                message="Invalid token type"
            )

        user_id = int(payload.get("sub", 0))
        if not user_id:
            raise UnauthorizedException(message="Invalid token payload")

        # Find user
        stmt = select(User).where(User.id == user_id)
        result = await self.db.execute(stmt)
        user = result.scalar_one_or_none()

        if user is None or not user.is_verified:
            raise UnauthorizedException(
                message="User not found or not verified"
            )

        new_access_token = create_access_token(user.id)
        new_refresh_token = create_refresh_token(user.id)

        return {
            "access_token": new_access_token,
            "refresh_token": new_refresh_token,
            "expires_in": 900,
        }

    async def get_current_user(self, user_id: int) -> User:
        """Load a user by ID with active_holding relationship."""
        stmt = select(User).where(User.id == user_id)
        result = await self.db.execute(stmt)
        user = result.scalar_one_or_none()

        if user is None or not user.is_verified:
            raise UnauthorizedException(
                message="User not found or not verified"
            )

        return user

    async def get_user_profile(self, user_id: int) -> User:
        """Get user profile with active holding."""
        return await self.get_current_user(user_id)

    async def set_active_holding(self, user_id: int, holding_id: int) -> dict:
        """Set the active holding for a user."""
        # Check holding exists
        stmt = select(Holding).where(Holding.id == holding_id)
        result = await self.db.execute(stmt)
        holding = result.scalar_one_or_none()

        if holding is None:
            raise NotFoundException(
                message="Holding not found",
                field="holding_id",
            )

        # Check membership
        stmt = select(UserHolding).where(
            UserHolding.user_id == user_id,
            UserHolding.holding_id == holding_id,
        )
        result = await self.db.execute(stmt)
        membership = result.scalar_one_or_none()

        if membership is None:
            raise ForbiddenException(
                message="User is not a member of this holding",
            )

        # Update user's active holding
        stmt = select(User).where(User.id == user_id)
        result = await self.db.execute(stmt)
        user = result.scalar_one()
        user.active_holding_id = holding_id

        return {
            "message": "Active holding set successfully",
            "active_holding": HoldingBrief.model_validate(holding),
        }

    async def get_holdings_list(self, user_id: int) -> list[Holding]:
        """Get list of user's holdings with their roles."""
        stmt = (
            select(Holding)
            .join(UserHolding)
            .where(UserHolding.user_id == user_id)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())
