"""pseudo target sprint

Revision ID: 2026_phase23_pseudo_target
Revises: 2026_phase2_multirole
Create Date: 2026-05-13
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "2026_phase23_pseudo_target"
down_revision: Union[str, None] = "2026_phase2_multirole"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("pseudo_tasks") as b:
        b.add_column(sa.Column("target_sprint_num", sa.Integer(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("pseudo_tasks") as b:
        b.drop_column("target_sprint_num")
