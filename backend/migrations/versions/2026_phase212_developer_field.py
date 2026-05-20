"""developer_field в configs + dev_role в directions

Revision ID: 2026_phase212_developer_field
Revises: 2026_phase211_directions
Create Date: 2026-05-20
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "2026_phase212_developer_field"
down_revision: Union[str, None] = "2026_phase211_directions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("configs") as b:
        b.add_column(sa.Column("developer_field", sa.String(50), nullable=False, server_default=""))

    with op.batch_alter_table("config_directions") as b:
        b.add_column(sa.Column("dev_role", sa.String(50), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("configs") as b:
        b.drop_column("developer_field")

    with op.batch_alter_table("config_directions") as b:
        b.drop_column("dev_role")
