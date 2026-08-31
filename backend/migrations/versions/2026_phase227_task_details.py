"""task_details: тема/фича задачи ("Детализация") для группировки в Roadmap

Revision ID: 2026_phase227_task_details
Revises: 2026_phase226_ai_provider
Create Date: 2026-08-05
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "2026_phase227_task_details"
down_revision: Union[str, None] = "2026_phase226_ai_provider"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "task_details",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("config_id", sa.Integer(), sa.ForeignKey("configs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("task_key", sa.String(50), nullable=False),
        sa.Column("detail", sa.String(300), nullable=False),
        sa.UniqueConstraint("config_id", "task_key", name="uq_task_detail_config_key"),
    )


def downgrade() -> None:
    op.drop_table("task_details")
