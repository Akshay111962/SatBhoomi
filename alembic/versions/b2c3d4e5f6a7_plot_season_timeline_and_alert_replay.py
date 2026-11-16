"""plot_season_timeline_and_alert_replay

Revision ID: b2c3d4e5f6a7
Revises: f1a2b3c4d5e6
Create Date: 2026-11-15 16:55:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b2c3d4e5f6a7"
down_revision: str | Sequence[str] | None = "f1a2b3c4d5e6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create plot_season_timeline table; add replay and checkpoint fields to alert; add transition fields to action_log."""
    # 1. Create plot_season_timeline table
    op.create_table(
        "plot_season_timeline",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("plot_id", sa.Integer(), nullable=False),
        sa.Column("season", sa.String(length=20), nullable=False),
        sa.Column("timeline_json", sa.JSON(), nullable=False),
        sa.Column("data_gaps_json", sa.JSON(), nullable=True),
        sa.Column("checkpoint_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("imported_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["plot_id"], ["plot.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("plot_id", "season", name="uq_plot_season_timeline"),
    )
    op.create_index(
        "ix_plot_season_timeline_plot_id",
        "plot_season_timeline",
        ["plot_id"],
        unique=False,
    )

    # 2. Add checkpoint, replay, and descriptive fields to alert table
    with op.batch_alter_table("alert", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "season",
                sa.String(length=20),
                nullable=False,
                server_default="2024-25",
            )
        )
        batch_op.add_column(sa.Column("checkpoint_label", sa.String(length=50), nullable=True))
        batch_op.add_column(sa.Column("headline", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("detail", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("supportive_action", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("data_gap_warning", sa.Text(), nullable=True))
        batch_op.add_column(
            sa.Column(
                "is_replay",
                sa.Boolean(),
                nullable=False,
                server_default="1",
            )
        )
        batch_op.create_unique_constraint(
            "uq_alert_plot_season_type",
            ["plot_id", "season", "type"],
        )

    # 3. Add transition status columns to action_log
    with op.batch_alter_table("action_log", schema=None) as batch_op:
        batch_op.add_column(sa.Column("status_before", sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column("status_after", sa.String(length=20), nullable=True))


def downgrade() -> None:
    """Revert alert, action_log, and plot_season_timeline changes."""
    with op.batch_alter_table("action_log", schema=None) as batch_op:
        batch_op.drop_column("status_after")
        batch_op.drop_column("status_before")

    with op.batch_alter_table("alert", schema=None) as batch_op:
        batch_op.drop_constraint("uq_alert_plot_season_type", type_="unique")
        batch_op.drop_column("is_replay")
        batch_op.drop_column("data_gap_warning")
        batch_op.drop_column("supportive_action")
        batch_op.drop_column("detail")
        batch_op.drop_column("headline")
        batch_op.drop_column("checkpoint_label")
        batch_op.drop_column("season")

    op.drop_index("ix_plot_season_timeline_plot_id", table_name="plot_season_timeline")
    op.drop_table("plot_season_timeline")
