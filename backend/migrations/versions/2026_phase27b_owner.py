"""configs owner_user_id

Revision ID: 2026_phase27b_owner
Revises: 2026_phase27a_users
Create Date: 2026-05-15
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "2026_phase27b_owner"
down_revision: Union[str, None] = "2026_phase27a_users"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("configs") as b:
        b.add_column(sa.Column("owner_user_id", sa.Integer(), nullable=True))
        b.create_foreign_key(
            "fk_configs_owner_user",
            "users",
            ["owner_user_id"],
            ["id"],
            ondelete="CASCADE",
        )

    # Привязка существующих конфигов к первому admin-у — временно,
    # в 2.7c можно будет передать lead-юзеру через UI.
    conn = op.get_bind()
    row = conn.execute(
        sa.text("SELECT id FROM users WHERE role = 'admin' ORDER BY id LIMIT 1")
    ).fetchone()
    admin_id = row[0] if row else None
    if admin_id is not None:
        conn.execute(
            sa.text("UPDATE configs SET owner_user_id = :uid WHERE owner_user_id IS NULL"),
            {"uid": admin_id},
        )

    # Добавляем sprints.config_id и привязываем существующие спринты к ним
    # по config_snapshot.id (этот id всегда есть в снапшоте, мы его пишем при save).
    with op.batch_alter_table("sprints") as b:
        b.add_column(sa.Column("config_id", sa.Integer(), nullable=True))
        b.create_foreign_key(
            "fk_sprints_config",
            "configs",
            ["config_id"],
            ["id"],
            ondelete="CASCADE",
        )

    # Бэкафил: тащим config_id из config_snapshot->>'id'
    conn.execute(sa.text(
        "UPDATE sprints SET config_id = (config_snapshot->>'id')::int "
        "WHERE config_id IS NULL"
    ))


def downgrade() -> None:
    with op.batch_alter_table("sprints") as b:
        b.drop_constraint("fk_sprints_config", type_="foreignkey")
        b.drop_column("config_id")
    with op.batch_alter_table("configs") as b:
        b.drop_constraint("fk_configs_owner_user", type_="foreignkey")
        b.drop_column("owner_user_id")
