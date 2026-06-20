from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.document import Document
    from app.models.user import User
    from app.models.document_section import DocumentSection
    from app.models.document_table import DocumentTable


def _utcnow() -> datetime:
    """Return naive UTC datetime."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class DocumentVersion(Base):
    __tablename__ = "document_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    document_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("documents.id", ondelete="CASCADE"), index=True, nullable=False
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    file_type: Mapped[str] = mapped_column(String(10), nullable=False)  # docx / pdf
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    version_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    full_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    uploaded_by: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utcnow, nullable=False
    )

    document: Mapped["Document"] = relationship("Document", back_populates="versions", lazy="selectin")
    uploader: Mapped[Optional["User"]] = relationship("User", lazy="selectin")
    sections: Mapped[list["DocumentSection"]] = relationship(
        "DocumentSection", back_populates="version", cascade="all, delete-orphan",
        lazy="selectin",
    )
    tables: Mapped[list["DocumentTable"]] = relationship(
        "DocumentTable", back_populates="version", cascade="all, delete-orphan",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<DocumentVersion(id={self.id}, doc_id={self.document_id}, v={self.version_number})>"
