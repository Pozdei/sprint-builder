"""epic_task_dependencies: from_bucket/to_bucket — FS-зависимости по этапам, а не только по задаче целиком

Revision ID: 2026_phase222_dep_bucket
Revises: 2026_phase221_jira_conn
Create Date: 2026-06-24
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "2026_phase222_dep_bucket"
down_revision: Union[str, None] = "2026_phase221_jira_conn"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "epic_task_dependencies",
        sa.Column("from_bucket", sa.String(50), nullable=False, server_default=""),
    )
    op.add_column(
        "epic_task_dependencies",
        sa.Column("to_bucket", sa.String(50), nullable=False, server_default=""),
    )
    op.drop_constraint("uq_epic_dep_unique", "epic_task_dependencies", type_="unique")
    op.create_unique_constraint(
        "uq_epic_dep_unique", "epic_task_dependencies",
        ["config_id", "epic_key", "from_key", "to_key", "from_bucket", "to_bucket"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_epic_dep_unique", "epic_task_dependencies", type_="unique")
    op.create_unique_constraint(
        "uq_epic_dep_unique", "epic_task_dependencies",
        ["config_id", "epic_key", "from_key", "to_key"],
    )
    op.drop_column("epic_task_dependencies", "to_bucket")
    op.drop_column("epic_task_dependencies", "from_bucket")
