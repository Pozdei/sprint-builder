"""epic_plans: ручной план старта/окончания эпика для Roadmap

Revision ID: 2026_phase228_epic_plan
Revises: 2026_phase227_task_details
Create Date: 2026-08-06
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "2026_phase228_epic_plan"
down_revision: Union[str, None] = "2026_phase227_task_details"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "epic_plans",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("config_id", sa.Integer(), sa.ForeignKey("configs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("epic_key", sa.String(50), nullable=False),
        sa.Column("planned_start", sa.String(10), nullable=False),
        sa.Column("planned_end", sa.String(10), nullable=False),
        sa.UniqueConstraint("config_id", "epic_key", name="uq_epic_plan_config_key"),
    )


def downgrade() -> None:
    op.drop_table("epic_plans")
