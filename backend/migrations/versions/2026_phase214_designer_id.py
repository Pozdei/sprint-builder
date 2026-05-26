"""direction designer_id

Revision ID: 2026_phase214
Revises: 2026_phase213
"""
from alembic import op
import sqlalchemy as sa

revision = "2026_phase214_designer_id"
down_revision = "2026_phase214_improvements"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("config_directions",
                  sa.Column("designer_id", sa.String(200), nullable=True, server_default=None))


def downgrade() -> None:
    op.drop_column("config_directions", "designer_id")
