from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.holding import Holding
    from app.models.user import User


class UserHolding(Base):
    __tablename__ = "user_holdings"
    __table_args__ = (
        UniqueConstraint("user_id", "holding_id", name="uq_user_holdings"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    holding_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("holdings.id", ondelete="CASCADE"), index=True, nullable=False
    )
    role: Mapped[str] = mapped_column(String(20), default="member", nullable=False)

    user: Mapped["User"] = relationship("User", lazy="selectin")
    holding: Mapped["Holding"] = relationship("Holding", lazy="selectin")

    def __repr__(self) -> str:
        return f"<UserHolding(user_id={self.user_id}, holding_id={self.holding_id}, role={self.role})>"
