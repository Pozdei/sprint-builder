"""epic forecast snapshots

Revision ID: 2026_phase212_forecast_snapshots
Revises: 2026_phase212_epic_deps
Create Date: 2026-05-21
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "2026_phase212_forecast_snapshots"
down_revision: Union[str, None] = "2026_phase212_epic_deps"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "epic_forecast_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "config_id", sa.Integer(),
            sa.ForeignKey("configs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("epic_key", sa.String(50), nullable=False),
        sa.Column("captured_date", sa.String(10), nullable=False),
        sa.Column("start_date", sa.String(10), nullable=False),
        sa.Column("hours_per_day", sa.Float(), nullable=False),
        sa.Column("completion_date", sa.String(10), nullable=True),
        sa.Column("total_issues", sa.Integer(), nullable=False),
        sa.Column("done_issues", sa.Integer(), nullable=False),
        sa.Column("remaining_work_items", sa.Integer(), nullable=False),
        sa.Column("total_planned_hours", sa.Float(), nullable=False),
        sa.UniqueConstraint(
            "config_id", "epic_key", "captured_date",
            name="uq_epic_snapshot_day",
        ),
    )
    op.create_index(
        "ix_epic_snapshot_config_epic",
        "epic_forecast_snapshots",
        ["config_id", "epic_key"],
    )


def downgrade() -> None:
    op.drop_index("ix_epic_snapshot_config_epic", table_name="epic_forecast_snapshots")
    op.drop_table("epic_forecast_snapshots")
