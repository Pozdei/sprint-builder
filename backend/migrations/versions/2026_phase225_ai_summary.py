"""configs: anthropic_api_key_enc — токен AI-среза per-конфиг (с fallback на .env)

Revision ID: 2026_phase225_ai_summary
Revises: 2026_phase224_telegram_token
Create Date: 2026-07-15
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "2026_phase225_ai_summary"
down_revision: Union[str, None] = "2026_phase224_telegram_token"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("configs", sa.Column("anthropic_api_key_enc", sa.String(500), nullable=False, server_default=""))


def downgrade() -> None:
    op.drop_column("configs", "anthropic_api_key_enc")
