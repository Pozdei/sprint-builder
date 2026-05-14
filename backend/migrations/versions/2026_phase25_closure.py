"""sprint closure

Revision ID: 2026_phase25_closure
Revises: 2026_phase23_pseudo_target
Create Date: 2026-05-14
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "2026_phase25_closure"
down_revision: Union[str, None] = "2026_phase23_pseudo_target"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # sprints: +closed_at, +jira_completed_at
    with op.batch_alter_table("sprints") as b:
        b.add_column(sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True))
        b.add_column(sa.Column("jira_completed_at", sa.DateTime(timezone=True), nullable=True))

    # sprint_tasks: +closed_task_data (JSON, nullable)
    with op.batch_alter_table("sprint_tasks") as b:
        b.add_column(sa.Column("closed_task_data", sa.JSON(), nullable=True))

    # configs: ничего не меняем в схеме — terminal_statuses будет отдельной таблицей,
    # чтобы хранить список без массива в SQL.
    op.create_table(
        "terminal_statuses",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("config_id", sa.Integer(),
                  sa.ForeignKey("configs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("jira_status", sa.String(100), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.UniqueConstraint("config_id", "jira_status", name="uq_termstatus_config_status"),
    )

    # Seed терминальных статусов для существующих конфигов
    conn = op.get_bind()
    configs = conn.execute(sa.text("SELECT id FROM configs")).fetchall()
    defaults = ["Выполнено", "Завершено", "Перенесено на Prod", "Отменено"]
    for (cfg_id,) in configs:
        for i, status in enumerate(defaults):
            conn.execute(
                sa.text(
                    "INSERT INTO terminal_statuses (config_id, jira_status, sort_order) "
                    "VALUES (:cid, :st, :ord)"
                ),
                {"cid": cfg_id, "st": status, "ord": i},
            )


def downgrade() -> None:
    op.drop_table("terminal_statuses")
    with op.batch_alter_table("sprint_tasks") as b:
        b.drop_column("closed_task_data")
    with op.batch_alter_table("sprints") as b:
        b.drop_column("jira_completed_at")
        b.drop_column("closed_at")
