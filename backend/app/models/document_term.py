from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.document import Document


class DocumentTerm(Base):
    __tablename__ = "document_terms"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    document_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("documents.id", ondelete="CASCADE"), index=True, nullable=False
    )
    term: Mapped[str] = mapped_column(String(500), nullable=False)
    definition: Mapped[str] = mapped_column(Text, nullable=False)

    document: Mapped["Document"] = relationship(
        "Document", back_populates="terms", lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<DocumentTerm(id={self.id}, term={self.term})>"
