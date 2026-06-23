"""sprint_gantt_snapshots — статичные снимки Ганта спринта

Revision ID: 2026_phase218_gantt_snap
Revises: 2026_phase217_root_tasks
Create Date: 2026-06-23
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "2026_phase218_gantt_snap"
down_revision: Union[str, None] = "2026_phase217_root_tasks"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "sprint_gantt_snapshots",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("sprint_id", sa.Integer,
                  sa.ForeignKey("sprints.id", ondelete="CASCADE"), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("label", sa.String(100), nullable=True),
        sa.Column("gantt_start", sa.String(10), nullable=False),
        sa.Column("hours_per_day", sa.Float, nullable=False),
        sa.Column("gantt_items", sa.JSON, nullable=False),
    )
    op.create_index(
        "ix_sprint_gantt_snapshots_sprint", "sprint_gantt_snapshots", ["sprint_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_sprint_gantt_snapshots_sprint", table_name="sprint_gantt_snapshots")
    op.drop_table("sprint_gantt_snapshots")
