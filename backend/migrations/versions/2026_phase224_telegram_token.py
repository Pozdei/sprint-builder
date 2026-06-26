"""configs: telegram_bot_token_enc — токен бота per-конфиг (с fallback на .env)

Revision ID: 2026_phase224_telegram_token
Revises: 2026_phase223_telegram
Create Date: 2026-06-26
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "2026_phase224_telegram_token"
down_revision: Union[str, None] = "2026_phase223_telegram"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("configs", sa.Column("telegram_bot_token_enc", sa.String(500), nullable=False, server_default=""))


def downgrade() -> None:
    op.drop_column("configs", "telegram_bot_token_enc")
