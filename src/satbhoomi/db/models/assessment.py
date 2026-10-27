"""Assessment entity model."""

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Optional

from sqlalchemy import JSON, CheckConstraint, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from satbhoomi.db.base import Base

if TYPE_CHECKING:
    from satbhoomi.db.models.plot import Plot
    from satbhoomi.db.models.user import User
    from satbhoomi.db.models.what_if import WhatIf


class Assessment(Base):
    """Credit risk assessment result for a farm plot.

    Every score stores its model_version for auditability and reproducibility.
    """

    __tablename__ = "assessment"
    __table_args__ = (
        CheckConstraint(
            "score >= 0 AND score <= 100",
            name="check_assessment_score_range",
        ),
        CheckConstraint(
            "band IN ('low', 'medium', 'high')",
            name="check_assessment_band",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    plot_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("plot.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    model_version: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    score: Mapped[float] = mapped_column(Float, nullable=False)
    band: Mapped[str] = mapped_column(String(10), nullable=False)
    reasons_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    loan_suggestion_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_by: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("user.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )

    # Relationships
    plot: Mapped["Plot"] = relationship(
        "Plot",
        back_populates="assessments",
    )
    officer: Mapped[Optional["User"]] = relationship(
        "User",
        back_populates="assessments",
    )
    what_ifs: Mapped[list["WhatIf"]] = relationship(
        "WhatIf",
        back_populates="assessment",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
