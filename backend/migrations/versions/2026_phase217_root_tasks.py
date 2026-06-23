"""employee_root_tasks — стартовая задача сотрудника

Revision ID: 2026_phase217_root_tasks
Revises: 2026_phase216_dt_fields
Create Date: 2026-06-23
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "2026_phase217_root_tasks"
down_revision: Union[str, None] = "2026_phase216_dt_fields"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "employee_root_tasks",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("config_id", sa.Integer,
                  sa.ForeignKey("configs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("epic_key", sa.String(50), nullable=False),
        sa.Column("owner_id", sa.String(100), nullable=False),
        sa.Column("task_key", sa.String(50), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("config_id", "epic_key", "owner_id", name="uq_root_task_owner"),
    )


def downgrade() -> None:
    op.drop_table("employee_root_tasks")
