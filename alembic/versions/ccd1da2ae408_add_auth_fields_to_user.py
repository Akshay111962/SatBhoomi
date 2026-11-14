"""add_auth_fields_to_user

Revision ID: ccd1da2ae408
Revises: 35c220ad71ed
Create Date: 2026-11-14 23:47:10.271985

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "ccd1da2ae408"
down_revision: str | Sequence[str] | None = "35c220ad71ed"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema adding user authentication and security audit fields."""
    with op.batch_alter_table("user", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("username", sa.String(length=50), nullable=False, server_default="")
        )
        batch_op.add_column(
            sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False)
        )
        batch_op.add_column(
            sa.Column("failed_login_count", sa.Integer(), server_default="0", nullable=False)
        )
        batch_op.add_column(sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.create_index(batch_op.f("ix_user_username"), ["username"], unique=True)

    with op.batch_alter_table("audit_log", schema=None) as batch_op:
        batch_op.alter_column("user_id", existing_type=sa.Integer(), nullable=True)


def downgrade() -> None:
    """Downgrade schema removing authentication fields."""
    with op.batch_alter_table("audit_log", schema=None) as batch_op:
        batch_op.alter_column("user_id", existing_type=sa.Integer(), nullable=True)

    with op.batch_alter_table("user", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_user_username"))
        batch_op.drop_column("last_login_at")
        batch_op.drop_column("locked_until")
        batch_op.drop_column("failed_login_count")
        batch_op.drop_column("is_active")
        batch_op.drop_column("username")
