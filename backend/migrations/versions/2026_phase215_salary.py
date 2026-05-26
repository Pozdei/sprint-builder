"""team member salary

Revision ID: 2026_phase215_salary
Revises: 2026_phase214_designer_id
"""
from alembic import op
import sqlalchemy as sa

revision = "2026_phase215_salary"
down_revision = "2026_phase214_designer_id"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("team_members",
                  sa.Column("salary", sa.Integer(), nullable=True, server_default=None))


def downgrade() -> None:
    op.drop_column("team_members", "salary")
