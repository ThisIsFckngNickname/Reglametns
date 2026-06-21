from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.holding import Holding


def _utcnow() -> datetime:
    """Return naive UTC datetime."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_banned: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(256), nullable=False, default='')
    active_holding_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("holdings.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=_utcnow,
        onupdate=_utcnow,
        nullable=False,
    )

    active_holding: Mapped[Optional["Holding"]] = relationship(
        "Holding", foreign_keys=[active_holding_id], lazy="selectin"
    )

    def set_password(self, password: str) -> None:
        """Hash and set password."""
        from app.core.security import hash_password as _hash
        self.password_hash = _hash(password)

    def check_password(self, password: str) -> bool:
        """Verify password against stored hash."""
        from app.core.security import verify_password as _verify
        return _verify(password, self.password_hash)

    def __repr__(self) -> str:
        return f"<User(id={self.id}, email={self.email}, verified={self.is_verified})>"
