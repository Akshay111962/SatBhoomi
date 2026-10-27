"""Consent entity model."""

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from satbhoomi.db.base import Base

if TYPE_CHECKING:
    from satbhoomi.db.models.farmer import Farmer


class Consent(Base):
    """Farmer consent record for data usage (DPDP Act, 2023 compliance)."""

    __tablename__ = "consent"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    farmer_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("farmer.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    purpose: Mapped[str] = mapped_column(String(255), nullable=False)
    given_on: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
    withdrawn_on: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    farmer: Mapped["Farmer"] = relationship(
        "Farmer",
        back_populates="consents",
        foreign_keys=[farmer_id],
    )
