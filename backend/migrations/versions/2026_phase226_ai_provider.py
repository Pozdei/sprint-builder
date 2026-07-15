"""configs: ai_provider + deepseek_api_key_enc — выбор провайдера AI-среза (Anthropic/DeepSeek)

Revision ID: 2026_phase226_ai_provider
Revises: 2026_phase225_ai_summary
Create Date: 2026-07-15
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "2026_phase226_ai_provider"
down_revision: Union[str, None] = "2026_phase225_ai_summary"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("configs", sa.Column("ai_provider", sa.String(20), nullable=False, server_default="anthropic"))
    op.add_column("configs", sa.Column("deepseek_api_key_enc", sa.String(500), nullable=False, server_default=""))


def downgrade() -> None:
    op.drop_column("configs", "deepseek_api_key_enc")
    op.drop_column("configs", "ai_provider")
