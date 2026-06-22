"""designer_field и tester_field в configs

Revision ID: 2026_phase216_dt_fields
Revises: 2026_phase215_salary
Create Date: 2026-06-22
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "2026_phase216_dt_fields"
down_revision: Union[str, None] = "2026_phase215_salary"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("configs") as b:
        b.add_column(sa.Column("designer_field", sa.String(50), nullable=False, server_default=""))
        b.add_column(sa.Column("tester_field", sa.String(50), nullable=False, server_default=""))


def downgrade() -> None:
    with op.batch_alter_table("configs") as b:
        b.drop_column("designer_field")
        b.drop_column("tester_field")
