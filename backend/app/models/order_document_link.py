from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.order import Order
    from app.models.document import Document


def _utcnow() -> datetime:
    """Return naive UTC datetime."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class OrderDocumentLink(Base):
    __tablename__ = "order_document_links"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True
    )
    document_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    link_type: Mapped[str] = mapped_column(String(20), nullable=False)  # amends, supersedes, relates_to
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)

    order: Mapped["Order"] = relationship("Order", back_populates="document_links", lazy="selectin")
    document: Mapped["Document"] = relationship("Document", lazy="selectin")

    def __repr__(self) -> str:
        return f"<OrderDocumentLink(id={self.id}, order={self.order_id}, doc={self.document_id})>"
