import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictException, ForbiddenException, NotFoundException, UnauthorizedException
from app.core.security import create_access_token, create_refresh_token, decode_token
from app.models.company import Company
from app.models.user import User
from app.models.user_company import UserCompany
from app.schemas.company import CompanyBrief

logger = logging.getLogger(__name__)


class AuthService:
    """Service for authentication operations with email/password."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def register(self, email: str, password: str) -> dict:
        """Register a new user with email and password. Returns tokens."""
        # Check if user exists
        stmt = select(User).where(User.email == email)
        result = await self.db.execute(stmt)
        user = result.scalar_one_or_none()

        if user:
            raise ConflictException(
                message="A user with this email already exists",
                field="email",
            )

        # Create new user
        user = User(email=email, is_verified=True)
        user.set_password(password)
        self.db.add(user)
        await self.db.flush()

        # Auto-assign to the first available company
        first_company_stmt = select(Company).order_by(Company.id).limit(1)
        first_company_result = await self.db.execute(first_company_stmt)
        first_company = first_company_result.scalar_one_or_none()
        if first_company:
            user_company = UserCompany(
                user_id=user.id,
                company_id=first_company.id,
                role="member",
            )
            self.db.add(user_company)
            user.active_company_id = first_company.id
            await self.db.flush()

        # Generate tokens
        access_token = create_access_token(user.id)
        refresh_token = create_refresh_token(user.id)

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "expires_in": 900,
        }

    async def login(self, email: str, password: str) -> dict:
        """Authenticate user with email and password. Returns tokens."""
        # Find user
        stmt = select(User).where(User.email == email)
        result = await self.db.execute(stmt)
        user = result.scalar_one_or_none()

        if user is None:
            raise NotFoundException(
                message="User not found",
                field="email",
            )

        # Check if user is banned
        if user.is_banned:
            raise UnauthorizedException(
                message="Ваш аккаунт заблокирован",
            )

        # Verify password
        if not user.check_password(password):
            raise UnauthorizedException(
                message="Invalid email or password",
            )

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
        """Load a user by ID with active_company relationship."""
        stmt = select(User).where(User.id == user_id)
        result = await self.db.execute(stmt)
        user = result.scalar_one_or_none()

        if user is None or not user.is_verified:
            raise UnauthorizedException(
                message="User not found or not verified"
            )

        return user

    async def get_user_profile(self, user_id: int) -> User:
        """Get user profile with active company."""
        return await self.get_current_user(user_id)

    async def set_active_company(self, user_id: int, company_id: int) -> dict:
        """Set the active company for a user."""
        # Check company exists
        stmt = select(Company).where(Company.id == company_id)
        result = await self.db.execute(stmt)
        company = result.scalar_one_or_none()

        if company is None:
            raise NotFoundException(
                message="Company not found",
                field="company_id",
            )

        # Check membership
        stmt = select(UserCompany).where(
            UserCompany.user_id == user_id,
            UserCompany.company_id == company_id,
        )
        result = await self.db.execute(stmt)
        membership = result.scalar_one_or_none()

        if membership is None:
            raise ForbiddenException(
                message="User is not a member of this company",
            )

        # Update user's active company
        stmt = select(User).where(User.id == user_id)
        result = await self.db.execute(stmt)
        user = result.scalar_one()
        user.active_company_id = company_id

        return {
            "message": "Active company set successfully",
            "active_company": CompanyBrief.model_validate(company),
        }

    async def get_companies_list(self, user_id: int) -> list[Company]:
        """Get list of user's companies with their roles."""
        stmt = (
            select(Company)
            .join(UserCompany)
            .where(UserCompany.user_id == user_id)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())
