import logging
import random
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.verification_code import VerificationCode

logger = logging.getLogger(__name__)


class CodeService:
    """Service for generating and verifying 6-digit codes."""

    CODE_LENGTH = 6
    CODE_EXPIRY_MINUTES = 15

    def generate_code(self) -> str:
        """Generate a 6-digit code as a zero-padded string."""
        return f"{random.randint(0, 999999):06d}"

    def get_expires_at(self) -> datetime:
        """Get the expiration timestamp for a new code (naive UTC)."""
        return datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(minutes=self.CODE_EXPIRY_MINUTES)

    async def save_code(
        self,
        db: AsyncSession,
        email: str,
        code: str,
        purpose: str,
        *,
        invalidate_previous: bool = False,
    ) -> VerificationCode:
        """
        Save a verification code.
        If invalidate_previous is True, mark all previous codes for this email+purpose as used.
        """
        if invalidate_previous:
            stmt = (
                select(VerificationCode)
                .where(
                    VerificationCode.email == email,
                    VerificationCode.purpose == purpose,
                    VerificationCode.used == False,
                )
            )
            result = await db.execute(stmt)
            old_codes = result.scalars().all()
            for old_code in old_codes:
                old_code.used = True

        verification_code = VerificationCode(
            email=email,
            code=code,
            purpose=purpose,
            expires_at=self.get_expires_at(),
            used=False,
        )
        db.add(verification_code)
        await db.flush()
        return verification_code

    async def verify_code(
        self,
        db: AsyncSession,
        email: str,
        code: str,
        purpose: str,
    ) -> VerificationCode:
        """
        Verify a code for the given email and purpose.
        Returns the VerificationCode if valid.
        Raises appropriate exceptions if invalid.
        """
        from app.core.exceptions import BadRequestException, CodeExpiredException

        stmt = (
            select(VerificationCode)
            .where(
                VerificationCode.email == email,
                VerificationCode.purpose == purpose,
            )
            .order_by(VerificationCode.created_at.desc())
            .limit(1)
        )
        result = await db.execute(stmt)
        stored_code = result.scalar_one_or_none()

        if stored_code is None:
            raise BadRequestException(
                code="UNAUTHORIZED",
                message="Invalid verification code",
                field="code",
            )

        if stored_code.used:
            raise BadRequestException(
                code="UNAUTHORIZED",
                message="Verification code has already been used",
                field="code",
            )

        if datetime.now(timezone.utc).replace(tzinfo=None) > stored_code.expires_at:
            raise CodeExpiredException()

        if stored_code.code != code:
            raise BadRequestException(
                code="UNAUTHORIZED",
                message="Invalid verification code",
                field="code",
            )

        return stored_code
