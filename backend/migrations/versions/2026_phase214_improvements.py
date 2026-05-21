"""phase 2.14 improvements: is_pinned on forecast snapshots

Revision ID: 2026_phase214_improvements
Revises: 2026_phase212_forecast_snapshots
Create Date: 2026-05-21
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "2026_phase214_improvements"
down_revision: Union[str, None] = "2026_phase212_forecast_snapshots"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "epic_forecast_snapshots",
        sa.Column("is_pinned", sa.Boolean(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("epic_forecast_snapshots", "is_pinned")
