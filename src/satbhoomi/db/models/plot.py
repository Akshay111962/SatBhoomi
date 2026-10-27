"""Plot entity model."""

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from satbhoomi.db.base import Base

if TYPE_CHECKING:
    from satbhoomi.db.models.alert import Alert
    from satbhoomi.db.models.assessment import Assessment
    from satbhoomi.db.models.farmer import Farmer
    from satbhoomi.db.models.season_observation import SeasonObservation


class Plot(Base):
    """Agricultural farm plot entity with location and cropping details."""

    __tablename__ = "plot"
    __table_args__ = (
        CheckConstraint(
            "area_acre > 0",
            name="check_plot_area_positive",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    farmer_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("farmer.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    crop: Mapped[str] = mapped_column(String(50), nullable=False)
    area_acre: Mapped[float] = mapped_column(Float, nullable=False)
    geometry: Mapped[str | None] = mapped_column(Text, nullable=True)
    lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    lon: Mapped[float | None] = mapped_column(Float, nullable=True)
    irrigation: Mapped[str | None] = mapped_column(String(50), nullable=True)
    insured: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )

    # Relationships
    farmer: Mapped["Farmer"] = relationship(
        "Farmer",
        back_populates="plots",
    )
    season_observations: Mapped[list["SeasonObservation"]] = relationship(
        "SeasonObservation",
        back_populates="plot",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    assessments: Mapped[list["Assessment"]] = relationship(
        "Assessment",
        back_populates="plot",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    alerts: Mapped[list["Alert"]] = relationship(
        "Alert",
        back_populates="plot",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
