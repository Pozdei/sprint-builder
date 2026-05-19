"""people + multi-config per lead

Revision ID: 2026_phase28_people
Revises: 2026_phase27a_users
Create Date: 2026-05-19

Шаги:
1. Создать таблицу people (справочник людей пользователя).
2. На каждый team_member создать или найти person, проставить person_id в team_members.
3. Снять глобальный unique с configs.name, добавить unique (owner_user_id, name).
4. Добавить users.active_config_id.
5. Старые колонки в team_members (jira_account_id, jira_name, file_name)
   ОСТАВЛЯЕМ — на них могут смотреть какие-то снапшоты config_snapshot.
   Они дублируют данные из people; источник правды — теперь people.

Внимание: 2.7b мог быть не применён к БД пользователя. Делаем миграцию
устойчивой к этому — если колонок owner_user_id / config_id ещё нет, не падаем.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "2026_phase28_people"
down_revision: Union[str, None] = "2026_phase27b_owner"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    # ---- 1) Таблица people ----
    op.create_table(
        "people",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("owner_user_id", sa.Integer(),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("jira_account_id", sa.String(100), nullable=False),
        sa.Column("jira_name", sa.String(200), nullable=False),
        sa.Column("file_name", sa.String(100), nullable=False),
        sa.UniqueConstraint("owner_user_id", "jira_account_id",
                            name="uq_people_owner_account"),
    )

    # ---- 2) team_members: добавить person_id ----
    with op.batch_alter_table("team_members") as b:
        b.add_column(sa.Column("person_id", sa.Integer(), nullable=True))

    # Бэкафил: на каждый существующий team_member создаём или находим person
    # по (owner_user_id конфига, jira_account_id team_member-а)
    # Если owner_user_id у конфига NULL (2.7b не накатан) — берём первого admin
    admin_row = conn.execute(
        sa.text("SELECT id FROM users WHERE role = 'admin' ORDER BY id LIMIT 1")
    ).fetchone()
    admin_id = admin_row[0] if admin_row else None

    # Если в configs нет колонки owner_user_id (2.7b не применён) — добавим её здесь
    cols = {r[0] for r in conn.execute(sa.text(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name = 'configs'"
    )).fetchall()}
    if "owner_user_id" not in cols:
        with op.batch_alter_table("configs") as b:
            b.add_column(sa.Column("owner_user_id", sa.Integer(), nullable=True))
            b.create_foreign_key(
                "fk_configs_owner_user", "users", ["owner_user_id"], ["id"],
                ondelete="CASCADE",
            )
        if admin_id:
            conn.execute(
                sa.text("UPDATE configs SET owner_user_id = :uid WHERE owner_user_id IS NULL"),
                {"uid": admin_id},
            )

    # Если в sprints нет config_id — добавим
    cols_sprints = {r[0] for r in conn.execute(sa.text(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name = 'sprints'"
    )).fetchall()}
    if "config_id" not in cols_sprints:
        with op.batch_alter_table("sprints") as b:
            b.add_column(sa.Column("config_id", sa.Integer(), nullable=True))
            b.create_foreign_key(
                "fk_sprints_config", "configs", ["config_id"], ["id"],
                ondelete="CASCADE",
            )
        conn.execute(sa.text(
            "UPDATE sprints SET config_id = (config_snapshot->>'id')::int "
            "WHERE config_id IS NULL"
        ))

    # Теперь — бэкафил people и team_members.person_id
    rows = conn.execute(sa.text(
        "SELECT tm.id, tm.config_id, tm.jira_account_id, tm.jira_name, tm.file_name, "
        "       c.owner_user_id "
        "FROM team_members tm JOIN configs c ON c.id = tm.config_id"
    )).fetchall()
    for tm_id, cfg_id, acc_id, jira_name, file_name, owner in rows:
        owner = owner or admin_id
        if not owner:
            continue
        # Существующий person для этого владельца?
        existing = conn.execute(sa.text(
            "SELECT id FROM people WHERE owner_user_id = :u AND jira_account_id = :a"
        ), {"u": owner, "a": acc_id}).fetchone()
        if existing:
            person_id = existing[0]
        else:
            ins = conn.execute(sa.text(
                "INSERT INTO people (owner_user_id, jira_account_id, jira_name, file_name) "
                "VALUES (:u, :a, :n, :f) RETURNING id"
            ), {"u": owner, "a": acc_id, "n": jira_name, "f": file_name})
            person_id = ins.fetchone()[0]
        conn.execute(
            sa.text("UPDATE team_members SET person_id = :p WHERE id = :tm"),
            {"p": person_id, "tm": tm_id},
        )

    # ---- 3) Unique constraint configs.name → (owner_user_id, name) ----
    # Сначала снимаем глобальный unique. В Postgres он называется configs_name_key
    # по умолчанию (или похоже). Сделаем безопасно — через имя из information_schema.
    constr_rows = conn.execute(sa.text(
        "SELECT constraint_name FROM information_schema.table_constraints "
        "WHERE table_name = 'configs' AND constraint_type = 'UNIQUE'"
    )).fetchall()
    for (cname,) in constr_rows:
        # дропаем все unique на configs — старый name был один, новый добавим следом
        if cname == "uq_config_owner_name":
            continue  # на случай повторного запуска
        conn.execute(sa.text(f'ALTER TABLE configs DROP CONSTRAINT "{cname}"'))

    op.create_unique_constraint(
        "uq_config_owner_name", "configs", ["owner_user_id", "name"]
    )

    # ---- 4) users.active_config_id ----
    user_cols = {r[0] for r in conn.execute(sa.text(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name = 'users'"
    )).fetchall()}
    if "active_config_id" not in user_cols:
        with op.batch_alter_table("users") as b:
            b.add_column(sa.Column("active_config_id", sa.Integer(), nullable=True))
            b.create_foreign_key(
                "fk_users_active_config", "configs", ["active_config_id"], ["id"],
                ondelete="SET NULL",
            )

    # Бэкафил: активный конфиг = первый по owner_user_id
    conn.execute(sa.text("""
        UPDATE users u
        SET active_config_id = (
            SELECT c.id FROM configs c
            WHERE c.owner_user_id = u.id
            ORDER BY c.id LIMIT 1
        )
        WHERE u.active_config_id IS NULL AND u.role = 'lead'
    """))


def downgrade() -> None:
    conn = op.get_bind()

    with op.batch_alter_table("users") as b:
        b.drop_constraint("fk_users_active_config", type_="foreignkey")
        b.drop_column("active_config_id")

    # Восстанавливаем глобальный unique на configs.name — но не падаем, если есть дубликаты
    op.drop_constraint("uq_config_owner_name", "configs", type_="unique")
    try:
        op.create_unique_constraint("uq_config_name", "configs", ["name"])
    except Exception:
        pass

    with op.batch_alter_table("team_members") as b:
        b.drop_column("person_id")
    op.drop_table("people")
