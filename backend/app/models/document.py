from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.document_status_log import DocumentStatusLog
    from app.models.holding import Holding
    from app.models.user import User
    from app.models.document_version import DocumentVersion
    from app.models.document_term import DocumentTerm
    from app.models.document_abbreviation import DocumentAbbreviation
    from app.models.document_link import DocumentLink
    from app.models.order_document_link import OrderDocumentLink


def _utcnow() -> datetime:
    """Return naive UTC datetime."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    holding_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("holdings.id", ondelete="CASCADE"), index=True, nullable=False
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="draft", nullable=False)
    was_analyzed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_by: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
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

    holding: Mapped["Holding"] = relationship("Holding", lazy="selectin")
    creator: Mapped[Optional["User"]] = relationship("User", lazy="selectin")
    versions: Mapped[list["DocumentVersion"]] = relationship(
        "DocumentVersion", back_populates="document", cascade="all, delete-orphan",
        lazy="selectin",
    )
    terms: Mapped[list["DocumentTerm"]] = relationship(
        "DocumentTerm", back_populates="document", cascade="all, delete-orphan",
        lazy="selectin",
    )
    abbreviations: Mapped[list["DocumentAbbreviation"]] = relationship(
        "DocumentAbbreviation", back_populates="document", cascade="all, delete-orphan",
        lazy="selectin",
    )
    source_links: Mapped[list["DocumentLink"]] = relationship(
        "DocumentLink", foreign_keys="DocumentLink.source_document_id",
        back_populates="source_document", cascade="all, delete-orphan",
        lazy="selectin",
    )
    target_links: Mapped[list["DocumentLink"]] = relationship(
        "DocumentLink", foreign_keys="DocumentLink.target_document_id",
        back_populates="target_document", cascade="all, delete-orphan",
        lazy="selectin",
    )
    order_links: Mapped[list["OrderDocumentLink"]] = relationship(
        "OrderDocumentLink", back_populates="document", cascade="all, delete-orphan",
        lazy="selectin",
    )
    status_logs: Mapped[list["DocumentStatusLog"]] = relationship(
        "DocumentStatusLog", back_populates="document", cascade="all, delete-orphan",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Document(id={self.id}, title={self.title}, status={self.status})>"
