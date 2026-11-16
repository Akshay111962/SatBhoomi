"""farmer_data_origin_consent_recorded_by_audit_triggers

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-11-16 16:15:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c3d4e5f6a7b8"
down_revision: str | Sequence[str] | None = "b2c3d4e5f6a7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add data_origin to farmer, recorded_by to consent, and SQLite immutability triggers on audit_log."""
    # 1. Add data_origin to farmer with check constraint
    with op.batch_alter_table("farmer", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "data_origin",
                sa.String(length=20),
                nullable=False,
                server_default="synthetic",
            )
        )
        batch_op.create_check_constraint(
            "ck_farmer_data_origin",
            "data_origin IN ('synthetic', 'real')",
        )

    # 2. Add recorded_by to consent with foreign key to user.id
    with op.batch_alter_table("consent", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "recorded_by",
                sa.Integer(),
                nullable=True,
            )
        )
        batch_op.create_foreign_key(
            "fk_consent_recorded_by_user",
            "user",
            ["recorded_by"],
            ["id"],
            ondelete="SET NULL",
        )

    # 3. Add SQLite triggers on audit_log to block UPDATE and DELETE
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        op.execute(
            """
            CREATE TRIGGER IF NOT EXISTS trg_audit_log_prevent_update
            BEFORE UPDATE ON audit_log
            BEGIN
                SELECT RAISE(ABORT, 'Audit log entries are immutable and cannot be updated');
            END;
            """
        )
        op.execute(
            """
            CREATE TRIGGER IF NOT EXISTS trg_audit_log_prevent_delete
            BEFORE DELETE ON audit_log
            BEGIN
                SELECT RAISE(ABORT, 'Audit log entries are immutable and cannot be deleted');
            END;
            """
        )


def downgrade() -> None:
    """Remove SQLite audit triggers, consent.recorded_by, and farmer.data_origin."""
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        op.execute("DROP TRIGGER IF EXISTS trg_audit_log_prevent_update;")
        op.execute("DROP TRIGGER IF EXISTS trg_audit_log_prevent_delete;")

    with op.batch_alter_table("consent", schema=None) as batch_op:
        batch_op.drop_constraint("fk_consent_recorded_by_user", type_="foreignkey")
        batch_op.drop_column("recorded_by")

    with op.batch_alter_table("farmer", schema=None) as batch_op:
        batch_op.drop_constraint("ck_farmer_data_origin", type_="check")
        batch_op.drop_column("data_origin")
