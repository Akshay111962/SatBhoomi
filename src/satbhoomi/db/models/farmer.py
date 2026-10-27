"""Farmer entity model."""

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from satbhoomi.db.base import Base

if TYPE_CHECKING:
    from satbhoomi.db.models.consent import Consent
    from satbhoomi.db.models.plot import Plot


class Farmer(Base):
    """Farmer entity representing smallholder farm owners.

    Strict Privacy Rule: Only synthetic or anonymized codes/display names are stored.
    Never store national ID numbers, bank account numbers, or phone numbers.
    """

    __tablename__ = "farmer"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    display_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        unique=True,
        index=True,
    )
    village: Mapped[str] = mapped_column(String(100), nullable=False)
    district: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    consent_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("consent.id", ondelete="SET NULL", use_alter=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )

    # Relationships - Deleting a farmer cascades to all plots and consents (DPDP erasure compliance)
    plots: Mapped[list["Plot"]] = relationship(
        "Plot",
        back_populates="farmer",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    consents: Mapped[list["Consent"]] = relationship(
        "Consent",
        back_populates="farmer",
        foreign_keys="[Consent.farmer_id]",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
