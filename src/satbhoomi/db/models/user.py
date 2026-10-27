"""User entity model."""

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from satbhoomi.db.base import Base

if TYPE_CHECKING:
    from satbhoomi.db.models.action_log import ActionLog
    from satbhoomi.db.models.assessment import Assessment
    from satbhoomi.db.models.audit_log import AuditLog


class User(Base):
    """System user representing loan officers and branch admins."""

    __tablename__ = "user"
    __table_args__ = (
        CheckConstraint(
            "role IN ('officer', 'admin')",
            name="check_user_role",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="officer")
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )

    # Relationships
    assessments: Mapped[list["Assessment"]] = relationship(
        "Assessment",
        back_populates="officer",
    )
    action_logs: Mapped[list["ActionLog"]] = relationship(
        "ActionLog",
        back_populates="officer",
    )
    audit_logs: Mapped[list["AuditLog"]] = relationship(
        "AuditLog",
        back_populates="user",
    )
