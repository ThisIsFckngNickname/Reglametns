from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    Boolean, DateTime, ForeignKey, Integer, String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.company import Company
    from app.models.document import Document


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class CompanyAbbreviation(Base):
    __tablename__ = "company_abbreviations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("companies.id", ondelete="CASCADE"),
        index=True, nullable=False,
    )
    abbreviation: Mapped[str] = mapped_column(String(50), nullable=False)
    full_form: Mapped[str] = mapped_column(String(500), nullable=False)
    source_document_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("documents.id", ondelete="SET NULL"),
        nullable=True,
    )
    is_manual: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utcnow, nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utcnow, onupdate=_utcnow, nullable=False,
    )

    company: Mapped["Company"] = relationship("Company", lazy="selectin")
    source_document: Mapped[Optional["Document"]] = relationship(
        "Document", lazy="selectin",
    )

    __table_args__ = (
        UniqueConstraint("company_id", "abbreviation", name="uq_company_abbreviation"),
    )

    def __repr__(self) -> str:
        return (
            f"<CompanyAbbreviation(id={self.id}, "
            f"company_id={self.company_id}, "
            f"abbreviation={self.abbreviation})>"
        )
