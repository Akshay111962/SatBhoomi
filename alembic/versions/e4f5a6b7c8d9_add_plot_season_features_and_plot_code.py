"""add_plot_season_features_and_plot_code

Revision ID: e4f5a6b7c8d9
Revises: ccd1da2ae408
Create Date: 2026-11-15 14:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e4f5a6b7c8d9"
down_revision: str | Sequence[str] | None = "ccd1da2ae408"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add plot_code to plot table and create plot_season_features table."""
    with op.batch_alter_table("plot", schema=None) as batch_op:
        batch_op.add_column(sa.Column("plot_code", sa.String(length=50), nullable=True))
        batch_op.create_index(batch_op.f("ix_plot_plot_code"), ["plot_code"], unique=True)

    op.create_table(
        "plot_season_features",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("plot_id", sa.Integer(), nullable=False),
        sa.Column("season", sa.String(length=20), nullable=False),
        sa.Column("cutoff_date", sa.Date(), nullable=False),
        sa.Column("feature_set_version", sa.String(length=50), nullable=False),
        sa.Column("features", sa.JSON(), nullable=False),
        sa.Column("provenance", sa.JSON(), nullable=False),
        sa.Column("imported_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["plot_id"],
            ["plot.id"],
            name="fk_plot_season_features_plot_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("plot_id", "season", name="uq_plot_season_features_plot_season"),
    )
    op.create_index(
        "ix_plot_season_features_plot_id",
        "plot_season_features",
        ["plot_id"],
        unique=False,
    )


def downgrade() -> None:
    """Drop plot_season_features table and remove plot_code from plot."""
    op.drop_index("ix_plot_season_features_plot_id", table_name="plot_season_features")
    op.drop_table("plot_season_features")

    with op.batch_alter_table("plot", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_plot_plot_code"))
        batch_op.drop_column("plot_code")
