from typing import TYPE_CHECKING, Optional

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.document_version import DocumentVersion


class DocumentSection(Base):
    __tablename__ = "document_sections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    document_version_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("document_versions.id", ondelete="CASCADE"), index=True, nullable=False
    )
    parent_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("document_sections.id", ondelete="CASCADE"), nullable=True
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    level: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    order_num: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    version: Mapped["DocumentVersion"] = relationship(
        "DocumentVersion", back_populates="sections", lazy="selectin"
    )
    children: Mapped[list["DocumentSection"]] = relationship(
        "DocumentSection",
        back_populates="parent_section",
        lazy="selectin",
        remote_side=[id],
    )
    parent_section: Mapped[Optional["DocumentSection"]] = relationship(
        "DocumentSection",
        back_populates="children",
        remote_side=[parent_id],
        lazy="selectin",
        foreign_keys=[parent_id],
    )

    def __repr__(self) -> str:
        return f"<DocumentSection(id={self.id}, title={self.title}, level={self.level})>"
