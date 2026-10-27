"""WhatIf simulation model."""

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from satbhoomi.db.base import Base

if TYPE_CHECKING:
    from satbhoomi.db.models.assessment import Assessment


class WhatIf(Base):
    """What-if simulation record estimating score sensitivity to intervention.

    Permanent rule: Output is labeled 'estimate', not proof of causation.
    """

    __tablename__ = "what_if"
    __table_args__ = (
        CheckConstraint(
            "new_score >= 0 AND new_score <= 100",
            name="check_what_if_score_range",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    assessment_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("assessment.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    changed_input: Mapped[str] = mapped_column(String(50), nullable=False)
    old_value: Mapped[str] = mapped_column(String(100), nullable=False)
    new_value: Mapped[str] = mapped_column(String(100), nullable=False)
    new_score: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )

    # Relationships
    assessment: Mapped["Assessment"] = relationship(
        "Assessment",
        back_populates="what_ifs",
    )
