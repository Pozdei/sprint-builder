"""epic task dependencies

Revision ID: 2026_phase212_epic_deps
Revises: 2026_phase212_vacations_deps
Create Date: 2026-05-21
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "2026_phase212_epic_deps"
down_revision: Union[str, None] = "2026_phase212_vacations_deps"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "epic_task_dependencies",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "config_id", sa.Integer(),
            sa.ForeignKey("configs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("epic_key", sa.String(50), nullable=False),
        sa.Column("from_key", sa.String(50), nullable=False),
        sa.Column("to_key", sa.String(50), nullable=False),
        sa.UniqueConstraint(
            "config_id", "epic_key", "from_key", "to_key",
            name="uq_epic_dep_unique",
        ),
    )


def downgrade() -> None:
    op.drop_table("epic_task_dependencies")
