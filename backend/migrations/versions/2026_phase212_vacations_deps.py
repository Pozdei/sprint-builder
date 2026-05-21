"""vacations and task dependencies

Revision ID: 2026_phase212_vacations_deps
Revises: 2026_phase213_direction_roles
Create Date: 2026-05-21
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "2026_phase212_vacations_deps"
down_revision: Union[str, None] = "2026_phase213"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "employee_vacations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "config_id", sa.Integer(),
            sa.ForeignKey("configs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("jira_account_id", sa.String(100), nullable=False),
        sa.Column("display_name", sa.String(200), nullable=False, server_default=""),
        sa.Column("start_date", sa.String(10), nullable=False),
        sa.Column("end_date", sa.String(10), nullable=False),
    )
    op.create_index(
        "ix_emp_vac_config_owner",
        "employee_vacations",
        ["config_id", "jira_account_id"],
    )

    with op.batch_alter_table("sprints") as b:
        b.add_column(sa.Column("task_dependencies", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("sprints") as b:
        b.drop_column("task_dependencies")

    op.drop_index("ix_emp_vac_config_owner", table_name="employee_vacations")
    op.drop_table("employee_vacations")
