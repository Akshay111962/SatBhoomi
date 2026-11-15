"""PlotSeasonTimeline entity model (T-11C, blueprint section 8)."""

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from satbhoomi.db.base import Base

if TYPE_CHECKING:
    from satbhoomi.db.models.plot import Plot


class PlotSeasonTimeline(Base):
    """Stores sequential time-series monitoring checkpoints and data gap records per plot-season."""

    __tablename__ = "plot_season_timeline"
    __table_args__ = (UniqueConstraint("plot_id", "season", name="uq_plot_season_timeline"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    plot_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("plot.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    season: Mapped[str] = mapped_column(String(20), nullable=False)
    timeline_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    data_gaps_json: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON, nullable=True)
    checkpoint_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    imported_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )

    plot: Mapped["Plot"] = relationship("Plot", back_populates="timelines")
