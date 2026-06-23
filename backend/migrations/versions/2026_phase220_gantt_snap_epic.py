"""sprint_gantt_snapshots: разрешаем привязку к эпику прогноза (config_id + epic_key)

sprint_id становится nullable — снимок привязан либо к спринту, либо к эпику.
Единый механизм снимков Ганта для истории спринтов и прогноза реализации.

Revision ID: 2026_phase220_gantt_epic
Revises: 2026_phase219_role_overr
Create Date: 2026-06-24
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "2026_phase220_gantt_epic"
down_revision: Union[str, None] = "2026_phase219_role_overr"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column("sprint_gantt_snapshots", "sprint_id", nullable=True)
    op.add_column(
        "sprint_gantt_snapshots",
        sa.Column("config_id", sa.Integer,
                  sa.ForeignKey("configs.id", ondelete="CASCADE"), nullable=True),
    )
    op.add_column(
        "sprint_gantt_snapshots",
        sa.Column("epic_key", sa.String(50), nullable=True),
    )
    op.create_index(
        "ix_sprint_gantt_snapshots_epic", "sprint_gantt_snapshots",
        ["config_id", "epic_key"],
    )


def downgrade() -> None:
    op.drop_index("ix_sprint_gantt_snapshots_epic", table_name="sprint_gantt_snapshots")
    op.drop_column("sprint_gantt_snapshots", "epic_key")
    op.drop_column("sprint_gantt_snapshots", "config_id")
    op.alter_column("sprint_gantt_snapshots", "sprint_id", nullable=False)
