"""ActionLog entity model."""

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from satbhoomi.db.base import Base

if TYPE_CHECKING:
    from satbhoomi.db.models.alert import Alert
    from satbhoomi.db.models.user import User


class ActionLog(Base):
    """Log of actions taken by loan officers in response to stress alerts."""

    __tablename__ = "action_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    alert_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("alert.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    action_type: Mapped[str] = mapped_column(String(50), nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    done_by: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("user.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    done_on: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )

    # Relationships
    alert: Mapped["Alert"] = relationship(
        "Alert",
        back_populates="action_logs",
    )
    officer: Mapped[Optional["User"]] = relationship(
        "User",
        back_populates="action_logs",
    )
