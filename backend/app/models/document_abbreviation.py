from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.document import Document


class DocumentAbbreviation(Base):
    __tablename__ = "document_abbreviations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    document_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("documents.id", ondelete="CASCADE"), index=True, nullable=False
    )
    abbreviation: Mapped[str] = mapped_column(String(100), nullable=False)
    full_form: Mapped[str] = mapped_column(String(500), nullable=False)

    document: Mapped["Document"] = relationship(
        "Document", back_populates="abbreviations", lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<DocumentAbbreviation(id={self.id}, abbr={self.abbreviation})>"
