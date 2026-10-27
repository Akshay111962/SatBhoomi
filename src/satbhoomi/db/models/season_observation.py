"""SeasonObservation entity model."""

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from satbhoomi.db.base import Base

if TYPE_CHECKING:
    from satbhoomi.db.models.plot import Plot


class SeasonObservation(Base):
    """Derived season features aggregated from satellite, rainfall, and mandi data."""

    __tablename__ = "season_observation"
    __table_args__ = (
        UniqueConstraint(
            "plot_id",
            "season",
            name="uq_season_observation_plot_season",
        ),
        Index("idx_obs_plot", "plot_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    plot_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("plot.id", ondelete="CASCADE"),
        nullable=False,
    )
    season: Mapped[str] = mapped_column(String(20), nullable=False)
    ndvi_mean: Mapped[float | None] = mapped_column(Float, nullable=True)
    ndvi_peak: Mapped[float | None] = mapped_column(Float, nullable=True)
    ndvi_std: Mapped[float | None] = mapped_column(Float, nullable=True)
    rain_total_mm: Mapped[float | None] = mapped_column(Float, nullable=True)
    rain_deficit_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    price_mean: Mapped[float | None] = mapped_column(Float, nullable=True)
    yield_district: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )

    # Relationships
    plot: Mapped["Plot"] = relationship(
        "Plot",
        back_populates="season_observations",
    )
