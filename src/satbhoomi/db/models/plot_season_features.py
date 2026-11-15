"""PlotSeasonFeatures entity model for pre-cutoff feature snapshots."""

from datetime import UTC, date, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, Date, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from satbhoomi.db.base import Base

if TYPE_CHECKING:
    from satbhoomi.db.models.plot import Plot


class PlotSeasonFeatures(Base):
    """Cut-off features and provenance snapshot for an agricultural plot-season.

    Label Blindness: Label columns (stressed, label_unavailable, peak_drop_pct)
    are strictly prohibited from being stored here.
    """

    __tablename__ = "plot_season_features"
    __table_args__ = (
        UniqueConstraint("plot_id", "season", name="uq_plot_season_features_plot_season"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    plot_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("plot.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    season: Mapped[str] = mapped_column(String(20), nullable=False)
    cutoff_date: Mapped[date] = mapped_column(Date, nullable=False)
    feature_set_version: Mapped[str] = mapped_column(String(50), nullable=False)
    features: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    provenance: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    imported_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )

    # Relationships
    plot: Mapped["Plot"] = relationship(
        "Plot",
        back_populates="season_features",
    )
