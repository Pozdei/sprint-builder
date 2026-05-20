"""directions — pipeline направлений задач

Revision ID: 2026_phase211_directions
Revises: 2026_phase210_intrusions
Create Date: 2026-05-20
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "2026_phase211_directions"
down_revision: Union[str, None] = "2026_phase210_intrusions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "config_directions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "config_id", sa.Integer(),
            sa.ForeignKey("configs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("labels", sa.JSON(), nullable=False),
        sa.Column("work_types", sa.JSON(), nullable=False),
        sa.UniqueConstraint("config_id", "name", name="uq_direction_config_name"),
    )


def downgrade() -> None:
    op.drop_table("config_directions")
