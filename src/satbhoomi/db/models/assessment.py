"""Assessment entity model."""

from datetime import UTC, date, datetime
from typing import TYPE_CHECKING, Any, Optional

from sqlalchemy import (
    JSON,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from satbhoomi.db.base import Base

if TYPE_CHECKING:
    from satbhoomi.db.models.plot import Plot
    from satbhoomi.db.models.user import User
    from satbhoomi.db.models.what_if import WhatIf


class Assessment(Base):
    """Credit risk assessment result for a farm plot.

    Every score stores its model_version for auditability and reproducibility.
    Supports status='ok' (with numeric score and band) and status='insufficient_data'
    (with nullable score/band and structured explanation).
    """

    __tablename__ = "assessment"
    __table_args__ = (
        CheckConstraint(
            "score IS NULL OR (score >= 0 AND score <= 100)",
            name="check_assessment_score_range",
        ),
        CheckConstraint(
            "band IS NULL OR band IN ('low', 'medium', 'high')",
            name="check_assessment_band",
        ),
        UniqueConstraint(
            "created_by",
            "plot_id",
            "idempotency_key",
            name="uq_assessment_idempotency",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    plot_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("plot.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    season: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="2024-25",
    )
    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="ok",
    )
    scorer: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="rules_baseline",
    )
    model_version: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    band: Mapped[str | None] = mapped_column(String(10), nullable=True)
    cutoff_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    reasons_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    loan_suggestion_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    data_warnings: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    insufficient_data_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    request_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
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
