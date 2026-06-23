"""config_directions: dev_role/tester_role/analyst_role -> role_overrides (JSON)

Revision ID: 2026_phase219_role_overr
Revises: 2026_phase218_gantt_snap
Create Date: 2026-06-23
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "2026_phase219_role_overr"
down_revision: Union[str, None] = "2026_phase218_gantt_snap"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "config_directions",
        sa.Column("role_overrides", sa.JSON, nullable=True),
    )

    directions = sa.table(
        "config_directions",
        sa.column("id", sa.Integer),
        sa.column("dev_role", sa.String),
        sa.column("tester_role", sa.String),
        sa.column("analyst_role", sa.String),
        sa.column("role_overrides", sa.JSON),
    )
    conn = op.get_bind()
    rows = conn.execute(
        sa.select(
            directions.c.id, directions.c.dev_role,
            directions.c.tester_role, directions.c.analyst_role,
        )
    ).fetchall()
    for row in rows:
        overrides = {}
        if row.dev_role:
            overrides["development"] = row.dev_role
        if row.tester_role:
            overrides["testing"] = row.tester_role
        if row.analyst_role:
            overrides["analytics"] = row.analyst_role
        conn.execute(
            directions.update()
            .where(directions.c.id == row.id)
            .values(role_overrides=overrides)
        )

    op.alter_column("config_directions", "role_overrides", nullable=False,
                     server_default=sa.text("'{}'"))
    op.drop_column("config_directions", "dev_role")
    op.drop_column("config_directions", "tester_role")
    op.drop_column("config_directions", "analyst_role")


def downgrade() -> None:
    op.add_column("config_directions", sa.Column("dev_role", sa.String(50), nullable=True))
    op.add_column("config_directions", sa.Column("tester_role", sa.String(50), nullable=True))
    op.add_column("config_directions", sa.Column("analyst_role", sa.String(50), nullable=True))

    directions = sa.table(
        "config_directions",
        sa.column("id", sa.Integer),
        sa.column("role_overrides", sa.JSON),
        sa.column("dev_role", sa.String),
        sa.column("tester_role", sa.String),
        sa.column("analyst_role", sa.String),
    )
    conn = op.get_bind()
    rows = conn.execute(sa.select(directions.c.id, directions.c.role_overrides)).fetchall()
    for row in rows:
        overrides = row.role_overrides or {}
        conn.execute(
            directions.update()
            .where(directions.c.id == row.id)
            .values(
                dev_role=overrides.get("development"),
                tester_role=overrides.get("testing"),
                analyst_role=overrides.get("analytics"),
            )
        )

    op.drop_column("config_directions", "role_overrides")
