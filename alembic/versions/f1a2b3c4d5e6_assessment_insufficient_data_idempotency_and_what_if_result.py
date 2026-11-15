"""assessment_insufficient_data_idempotency_and_what_if_result

Revision ID: f1a2b3c4d5e6
Revises: e4f5a6b7c8d9
Create Date: 2026-11-15 15:20:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f1a2b3c4d5e6"
down_revision: str | Sequence[str] | None = "e4f5a6b7c8d9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add status, season, scorer, cutoff_date, data_warnings, idempotency to assessment; make score/band nullable; add result_json to what_if."""
    with op.batch_alter_table("assessment", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "season",
                sa.String(length=20),
                nullable=False,
                server_default="2024-25",
            )
        )
        batch_op.add_column(
            sa.Column(
                "status",
                sa.String(length=30),
                nullable=False,
                server_default="ok",
            )
        )
        batch_op.add_column(
            sa.Column(
                "scorer",
                sa.String(length=50),
                nullable=False,
                server_default="rules_baseline",
            )
        )
        batch_op.add_column(sa.Column("cutoff_date", sa.Date(), nullable=True))
        batch_op.add_column(sa.Column("data_warnings", sa.JSON(), nullable=True))
        batch_op.add_column(
            sa.Column(
                "insufficient_data_reason",
                sa.String(length=255),
                nullable=True,
            )
        )
        batch_op.add_column(
            sa.Column("idempotency_key", sa.String(length=64), nullable=True)
        )
        batch_op.add_column(
            sa.Column("request_hash", sa.String(length=64), nullable=True)
        )
        batch_op.alter_column("score", existing_type=sa.Float(), nullable=True)
        batch_op.alter_column(
            "band", existing_type=sa.String(length=10), nullable=True
        )
        batch_op.alter_column(
            "loan_suggestion_json", existing_type=sa.JSON(), nullable=True
        )
        batch_op.create_unique_constraint(
            "uq_assessment_idempotency",
            ["created_by", "plot_id", "idempotency_key"],
        )

    with op.batch_alter_table("what_if", schema=None) as batch_op:
        batch_op.add_column(sa.Column("result_json", sa.JSON(), nullable=True))


def downgrade() -> None:
    """Revert assessment and what_if alterations."""
    with op.batch_alter_table("what_if", schema=None) as batch_op:
        batch_op.drop_column("result_json")

    with op.batch_alter_table("assessment", schema=None) as batch_op:
        batch_op.drop_constraint("uq_assessment_idempotency", type_="unique")
        batch_op.alter_column(
            "loan_suggestion_json", existing_type=sa.JSON(), nullable=False
        )
        batch_op.alter_column(
            "band", existing_type=sa.String(length=10), nullable=False
        )
        batch_op.alter_column("score", existing_type=sa.Float(), nullable=False)
        batch_op.drop_column("request_hash")
        batch_op.drop_column("idempotency_key")
        batch_op.drop_column("insufficient_data_reason")
        batch_op.drop_column("data_warnings")
        batch_op.drop_column("cutoff_date")
        batch_op.drop_column("scorer")
        batch_op.drop_column("status")
        batch_op.drop_column("season")
