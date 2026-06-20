from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Boolean, DateTime, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def _utcnow() -> datetime:
    """Return naive UTC datetime."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Holding(Base):
    __tablename__ = "holdings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    inn: Mapped[Optional[str]] = mapped_column(String(12), nullable=True)
    legal_form: Mapped[str] = mapped_column(String(20), nullable=False)
    document_structure: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    style_settings: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    use_gost: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=_utcnow,
        onupdate=_utcnow,
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<Holding(id={self.id}, name={self.name})>"
