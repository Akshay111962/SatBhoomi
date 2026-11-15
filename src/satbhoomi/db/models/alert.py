"""Alert entity model."""

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from satbhoomi.db.base import Base

if TYPE_CHECKING:
    from satbhoomi.db.models.action_log import ActionLog
    from satbhoomi.db.models.plot import Plot


class Alert(Base):
    """In-season farm stress alert (Raksha module).

    Wording Rule: Alerts describe farm and repayment stress, never mental state.
    """

    __tablename__ = "alert"
    __table_args__ = (
        CheckConstraint(
            "severity IN ('low', 'medium', 'high')",
            name="check_alert_severity",
        ),
        CheckConstraint(
            "status IN ('open', 'acknowledged', 'in_progress', 'resolved', 'dismissed')",
            name="check_alert_status",
        ),
        UniqueConstraint("plot_id", "season", "type", name="uq_alert_plot_season_type"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    plot_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("plot.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    season: Mapped[str] = mapped_column(String(20), nullable=False, default="2024-25")
    type: Mapped[str] = mapped_column(String(50), nullable=False)
    severity: Mapped[str] = mapped_column(String(10), nullable=False, default="medium")
    detected_on: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open")
    checkpoint_label: Mapped[str | None] = mapped_column(String(50), nullable=True)
    headline: Mapped[str | None] = mapped_column(String(255), nullable=True)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    supportive_action: Mapped[str | None] = mapped_column(Text, nullable=True)
    data_gap_warning: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_replay: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Relationships
    plot: Mapped["Plot"] = relationship(
        "Plot",
        back_populates="alerts",
    )
    action_logs: Mapped[list["ActionLog"]] = relationship(
        "ActionLog",
        back_populates="alert",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
