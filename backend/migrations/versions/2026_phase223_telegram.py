"""configs: telegram_chat_id/telegram_daily_enabled/telegram_daily_time — дайджест в Telegram

Revision ID: 2026_phase223_telegram
Revises: 2026_phase222_dep_bucket
Create Date: 2026-06-26
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "2026_phase223_telegram"
down_revision: Union[str, None] = "2026_phase222_dep_bucket"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("configs", sa.Column("telegram_chat_id", sa.String(100), nullable=False, server_default=""))
    op.add_column("configs", sa.Column("telegram_daily_enabled", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("configs", sa.Column("telegram_daily_time", sa.String(5), nullable=False, server_default=""))


def downgrade() -> None:
    op.drop_column("configs", "telegram_daily_time")
    op.drop_column("configs", "telegram_daily_enabled")
    op.drop_column("configs", "telegram_chat_id")
