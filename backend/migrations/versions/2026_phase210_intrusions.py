"""sprint intrusions

Revision ID: 2026_phase210_intrusions
Revises: 2026_phase28_people
Create Date: 2026-05-19
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "2026_phase210_intrusions"
down_revision: Union[str, None] = "2026_phase28_people"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("sprints") as b:
        b.add_column(sa.Column("intrusions", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("sprints") as b:
        b.drop_column("intrusions")
