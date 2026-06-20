from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.document import Document
    from app.models.user import User


def _utcnow() -> datetime:
    """Return naive UTC datetime."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class DocumentLink(Base):
    __tablename__ = "document_links"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_document_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    target_document_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    link_type: Mapped[str] = mapped_column(String(20), nullable=False)  # references, amends, supersedes, related
    is_manual: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_by: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)

    source_document: Mapped["Document"] = relationship(
        "Document", foreign_keys=[source_document_id], back_populates="source_links", lazy="selectin"
    )
    target_document: Mapped["Document"] = relationship(
        "Document", foreign_keys=[target_document_id], back_populates="target_links", lazy="selectin"
    )
    creator: Mapped[Optional["User"]] = relationship("User", lazy="selectin")

    def __repr__(self) -> str:
        return f"<DocumentLink(id={self.id}, src={self.source_document_id}->{self.target_document_id}, type={self.link_type})>"
