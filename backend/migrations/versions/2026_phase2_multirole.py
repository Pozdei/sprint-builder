"""phase 2 multirole

Revision ID: 2026_phase2_multirole
Revises: fb07ae715234
Create Date: 2026-05-13

ВАЖНО: эта миграция написана вручную, не через --autogenerate.
Она переносит данные из status_buckets в role_status_buckets, прежде чем
удалять старую таблицу.

Шаги upgrade():
  1. Добавить колонки в configs (leader_hours, leader_management_enabled).
  2. Добавить колонку role в team_members.
  3. Создать новые таблицы (roles, role_status_buckets, role_status_default_hours,
     pseudo_tasks).
  4. Перенести данные:
     - Создать роли (5 штук) в каждом config.
     - Скопировать status_buckets → role_status_buckets для роли analyst.
     - Назначить всем существующим team_members роль analyst.
     - Создать дефолтные часы для лидов на ревью.
  5. Удалить unique-constraint в team_members со старого формата и добавить новый
     (с role).
  6. Удалить таблицы status_buckets и strict_assignee_buckets.

downgrade() пишем урезанно — только основные операции, без обратного переноса
данных. Если откатываем — лучше восстановить из бэкапа БД.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "2026_phase2_multirole"
down_revision: Union[str, None] = "310c41fe20f8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Дефолтный набор ролей для нового конфига
_ROLES = [
    ("analyst",         "Аналитик",         False, 0),
    ("designer",        "Дизайнер",         False, 1),
    ("designer_lead",   "Лид дизайна",      True,  2),
    ("developer",       "Разработчик",      False, 3),
    ("developer_lead",  "Лид разработки",   True,  4),
]


def upgrade() -> None:
    # 1) configs: новые колонки
    with op.batch_alter_table("configs") as b:
        b.add_column(sa.Column("leader_hours", sa.Float(), nullable=False,
                               server_default="20.0"))
        b.add_column(sa.Column("leader_management_enabled", sa.Boolean(),
                               nullable=False, server_default=sa.true()))

    # 2) team_members: новая колонка role
    with op.batch_alter_table("team_members") as b:
        b.add_column(sa.Column("role", sa.String(50), nullable=False,
                               server_default="analyst"))

    # 3) Новые таблицы
    op.create_table(
        "roles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("config_id", sa.Integer(),
                  sa.ForeignKey("configs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(50), nullable=False),
        sa.Column("display_name", sa.String(100), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("is_lead", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.UniqueConstraint("config_id", "name", name="uq_role_config_name"),
    )

    op.create_table(
        "role_status_buckets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("config_id", sa.Integer(),
                  sa.ForeignKey("configs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(50), nullable=False),
        sa.Column("jira_status", sa.String(100), nullable=False),
        sa.Column("bucket", sa.String(50), nullable=False),
        sa.UniqueConstraint("config_id", "role", "jira_status",
                            name="uq_rsb_config_role_status"),
    )
    op.create_index("ix_rsb_config_role", "role_status_buckets",
                    ["config_id", "role"])

    op.create_table(
        "role_status_default_hours",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("config_id", sa.Integer(),
                  sa.ForeignKey("configs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(50), nullable=False),
        sa.Column("jira_status", sa.String(100), nullable=False),
        sa.Column("hours", sa.Float(), nullable=False),
        sa.UniqueConstraint("config_id", "role", "jira_status",
                            name="uq_rsdh_config_role_status"),
    )

    op.create_table(
        "pseudo_tasks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("config_id", sa.Integer(),
                  sa.ForeignKey("configs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("member_id", sa.Integer(),
                  sa.ForeignKey("team_members.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("bucket", sa.String(50), nullable=False),
        sa.Column("hours", sa.Float(), nullable=False),
        sa.Column("recurring", sa.Boolean(), nullable=False, server_default=sa.false()),
    )

    # 4) Перенос данных
    conn = op.get_bind()

    # 4.1) Для каждого config — создать 5 ролей
    configs = conn.execute(sa.text("SELECT id FROM configs")).fetchall()
    for (cfg_id,) in configs:
        for name, display, is_lead, order in _ROLES:
            # analyst включён, остальные — выключены (нет людей в них)
            enabled = (name == "analyst")
            conn.execute(
                sa.text(
                    "INSERT INTO roles (config_id, name, display_name, enabled, "
                    "is_lead, sort_order) "
                    "VALUES (:cid, :name, :display, :enabled, :is_lead, :order)"
                ),
                {"cid": cfg_id, "name": name, "display": display,
                 "enabled": enabled, "is_lead": is_lead, "order": order},
            )

    # 4.2) Скопировать status_buckets → role_status_buckets для analyst
    conn.execute(sa.text(
        "INSERT INTO role_status_buckets (config_id, role, jira_status, bucket) "
        "SELECT config_id, 'analyst', jira_status, bucket FROM status_buckets"
    ))

    # 4.3) team_members.role уже заполнен server_default'ом 'analyst' — ничего не делаем

    # 4.4) Дефолтные часы для лидов на ревью
    for (cfg_id,) in configs:
        conn.execute(
            sa.text(
                "INSERT INTO role_status_default_hours "
                "(config_id, role, jira_status, hours) VALUES "
                "(:cid, 'developer_lead', 'Код-ревью', 1), "
                "(:cid, 'designer_lead', 'Дизайн-ревью', 1)"
            ),
            {"cid": cfg_id},
        )

    # 5) Уникальный констрейнт team_members нужно переделать:
    # старый — UNIQUE (config_id, jira_account_id)
    # новый — UNIQUE (config_id, jira_account_id, role)
    with op.batch_alter_table("team_members") as b:
        b.drop_constraint("uq_team_config_account", type_="unique")
        b.create_unique_constraint(
            "uq_team_config_account_role",
            ["config_id", "jira_account_id", "role"],
        )

    # 6) Удалить старые таблицы
    op.drop_table("status_buckets")
    op.drop_table("strict_assignee_buckets")
    op.drop_table("bucket_hours_fields")  # тоже не нужна — заменена role_status_default_hours


def downgrade() -> None:
    # Минимальный rollback. Данные не восстанавливаем — для этого нужен бэкап.
    op.create_table(
        "bucket_hours_fields",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("config_id", sa.Integer(),
                  sa.ForeignKey("configs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("bucket", sa.String(50), nullable=False),
        sa.Column("customfield_id", sa.String(50), nullable=False),
        sa.UniqueConstraint("config_id", "bucket", name="uq_buckethours_config_bucket"),
    )
    op.create_table(
        "strict_assignee_buckets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("config_id", sa.Integer(),
                  sa.ForeignKey("configs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("bucket", sa.String(50), nullable=False),
        sa.UniqueConstraint("config_id", "bucket", name="uq_strict_config_bucket"),
    )
    op.create_table(
        "status_buckets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("config_id", sa.Integer(),
                  sa.ForeignKey("configs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("jira_status", sa.String(100), nullable=False),
        sa.Column("bucket", sa.String(50), nullable=False),
        sa.UniqueConstraint("config_id", "jira_status",
                            name="uq_statusbucket_config_status"),
    )

    op.drop_table("pseudo_tasks")
    op.drop_table("role_status_default_hours")
    op.drop_index("ix_rsb_config_role", table_name="role_status_buckets")
    op.drop_table("role_status_buckets")
    op.drop_table("roles")

    with op.batch_alter_table("team_members") as b:
        b.drop_constraint("uq_team_config_account_role", type_="unique")
        b.create_unique_constraint(
            "uq_team_config_account",
            ["config_id", "jira_account_id"],
        )
        b.drop_column("role")

    with op.batch_alter_table("configs") as b:
        b.drop_column("leader_management_enabled")
        b.drop_column("leader_hours")
