"""direction tester_role and analyst_role

Revision ID: 2026_phase213
Revises: 2026_phase212_developer_field
"""
from alembic import op
import sqlalchemy as sa

revision = "2026_phase213"
down_revision = "2026_phase212_developer_field"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("config_directions",
                  sa.Column("tester_role", sa.String(50), nullable=True, server_default=None))
    op.add_column("config_directions",
                  sa.Column("analyst_role", sa.String(50), nullable=True, server_default=None))


def downgrade() -> None:
    op.drop_column("config_directions", "analyst_role")
    op.drop_column("config_directions", "tester_role")
