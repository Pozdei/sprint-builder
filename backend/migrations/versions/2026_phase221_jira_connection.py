"""configs: jira_base_url/jira_email/jira_api_token_enc — подключение к Jira per-конфиг

Revision ID: 2026_phase221_jira_conn
Revises: 2026_phase220_gantt_epic
Create Date: 2026-06-24
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "2026_phase221_jira_conn"
down_revision: Union[str, None] = "2026_phase220_gantt_epic"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("configs", sa.Column("jira_base_url", sa.String(200), nullable=False, server_default=""))
    op.add_column("configs", sa.Column("jira_email", sa.String(200), nullable=False, server_default=""))
    op.add_column("configs", sa.Column("jira_api_token_enc", sa.String(500), nullable=False, server_default=""))


def downgrade() -> None:
    op.drop_column("configs", "jira_api_token_enc")
    op.drop_column("configs", "jira_email")
    op.drop_column("configs", "jira_base_url")
