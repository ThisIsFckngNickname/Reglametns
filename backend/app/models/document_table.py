from typing import TYPE_CHECKING, Optional

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.document_version import DocumentVersion
    from app.models.document_section import DocumentSection


class DocumentTable(Base):
    __tablename__ = "document_tables"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    document_version_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("document_versions.id", ondelete="CASCADE"), index=True, nullable=False
    )
    section_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("document_sections.id", ondelete="SET NULL"), nullable=True
    )
    caption: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    order_num: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    html_content: Mapped[str] = mapped_column(Text, nullable=False)
    rows_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    cols_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    version: Mapped["DocumentVersion"] = relationship(
        "DocumentVersion", back_populates="tables", lazy="selectin"
    )
    section: Mapped[Optional["DocumentSection"]] = relationship(
        "DocumentSection", lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<DocumentTable(id={self.id}, caption={self.caption})>"
