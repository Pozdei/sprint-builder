"""Seed: при первом старте бэкенда создаём дефолтный конфиг.

Идемпотентно — если is_default уже есть, не трогаем.
Фаза 2: создаются 5 ролей, маппинг статусов на бакеты привязан к роли analyst,
дефолтные часы для лидов на ревью = 1.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import models
from app.db.repository import (
    upsert_boards, upsert_components, upsert_role_hours_fields,
    upsert_role_status_buckets, upsert_role_status_default_hours, upsert_roles,
    upsert_status_priorities, upsert_team_members, upsert_terminal_statuses,
)


# Дефолтные значения
_DEFAULT_TEAM = [
    ("712020:4eef6bdf-ac1f-4ef0-821d-836758c09514", "Aida Badamova", "Бадамова А", "analyst"),
    ("712020:abca6d44-4a90-4a35-951b-fa9bf2811287", "Aleksey Strazdin", "Страздин А.", "analyst"),
    ("712020:ab0ca3ac-138c-4f14-b983-6211fc0bb850", "Aleksey Batrakov", "Батраков А.", "analyst"),
    ("712020:02f9154d-d25a-4a6b-9226-4d092c3970c7", "Ruslan Amanov", "Аманов Р.", "analyst"),
]

_DEFAULT_BOARDS = [
    ("Serial", 1665),
    ("Purchase Order Management", 1896),
    ("Retail Wms", 1995),
    ("Space", 3296),
    ("Wfm", 1764),
]

_DEFAULT_ROLES = [
    # (name, display_name, enabled, is_lead, sort_order)
    ("analyst",        "Аналитик",       True,  False, 0),
    ("designer",       "Дизайнер",       False, False, 1),
    ("designer_lead",  "Лид дизайна",    False, True,  2),
    ("developer",      "Разработчик",    False, False, 3),
    ("developer_lead", "Лид разработки", False, True,  4),
]

# Маппинг (роль, статус) → бакет.
# Аналитик — как раньше (бывший глобальный status_bucket).
# Дизайнер/разраб — новые статусы.
_DEFAULT_ROLE_STATUS_BUCKETS = [
    # ---- analyst ----
    ("analyst", "Создана", "Анализ"),
    ("analyst", "Новый", "Анализ"),
    ("analyst", "Анализ", "Анализ"),
    ("analyst", "В работе", "Анализ"),
    ("analyst", "Готов к разработке", "Тестирование"),
    ("analyst", "К разработке", "Тестирование"),
    ("analyst", "В разработке", "Тестирование"),
    ("analyst", "Код-ревью", "Тестирование"),
    ("analyst", "К тестированию", "Тестирование"),
    ("analyst", "Тестирование", "Тестирование"),
    # ---- designer ----
    ("designer", "К дизайну", "Дизайн"),
    ("designer", "Дизайн", "Дизайн"),
    # ---- designer_lead ----
    ("designer_lead", "К дизайну", "Дизайн"),
    ("designer_lead", "Дизайн", "Дизайн"),
    ("designer_lead", "Дизайн-ревью", "Дизайн-ревью"),
    # ---- developer ----
    ("developer", "Готов к разработке", "Разработка"),
    ("developer", "К разработке", "Разработка"),
    ("developer", "В разработке", "Разработка"),
    # ---- developer_lead ----
    ("developer_lead", "Готов к разработке", "Разработка"),
    ("developer_lead", "К разработке", "Разработка"),
    ("developer_lead", "В разработке", "Разработка"),
    ("developer_lead", "Код-ревью", "Код-ревью"),
]

_DEFAULT_STATUS_PRIORITY = {
    "К тестированию": 0, "Тестирование": 0,
    "Код-ревью": 1, "В разработке": 1, "Готов к разработке": 1, "К разработке": 1,
    "Дизайн-ревью": 1,
    "Анализ": 2, "В работе": 2, "Дизайн": 2,
    "Создана": 3, "Новый": 3, "К дизайну": 3,
}

_DEFAULT_ROLE_HOURS_FIELDS = {
    "analyst":   "customfield_10235",
    "tester":    "customfield_11406",
    "developer": "customfield_10234",
}

# Дефолтные часы лида на ревью
_DEFAULT_ROLE_STATUS_HOURS = [
    ("developer_lead", "Код-ревью", 1),
    ("designer_lead", "Дизайн-ревью", 1),
]

# Терминальные статусы — задача в этих статусах считается выполненной
_DEFAULT_TERMINAL_STATUSES = [
    "Выполнено", "Завершено", "Перенесено на Prod", "Отменено",
]


def seed_default_config(db: Session) -> None:
    existing = db.scalar(select(models.Config).where(models.Config.is_default == True))  # noqa: E712
    if existing:
        return

    config = models.Config(
        name="Default",
        is_default=True,
        project_key="SHN",
        sprint_field="customfield_10018",
        responsible_field="customfield_10105",
        hours_per_person=80.0,
        default_task_hours=12.0,
        leader_hours=20.0,
        leader_management_enabled=True,
    )
    db.add(config)
    db.flush()

    upsert_team_members(db, config, [
        {"jira_account_id": acc, "jira_name": jn, "file_name": fn, "role": role,
         "sort_order": i}
        for i, (acc, jn, fn, role) in enumerate(_DEFAULT_TEAM)
    ])
    upsert_boards(db, config, [
        {"name": name, "jira_board_id": bid}
        for name, bid in _DEFAULT_BOARDS
    ])
    upsert_components(db, config, ["3PL integration hub"])
    upsert_status_priorities(db, config, _DEFAULT_STATUS_PRIORITY)
    upsert_role_hours_fields(db, config, _DEFAULT_ROLE_HOURS_FIELDS)

    upsert_roles(db, config, [
        {"name": name, "display_name": display, "enabled": enabled,
         "is_lead": is_lead, "sort_order": order}
        for name, display, enabled, is_lead, order in _DEFAULT_ROLES
    ])
    upsert_role_status_buckets(db, config, [
        {"role": r, "jira_status": s, "bucket": b}
        for r, s, b in _DEFAULT_ROLE_STATUS_BUCKETS
    ])
    upsert_role_status_default_hours(db, config, [
        {"role": r, "jira_status": s, "hours": h}
        for r, s, h in _DEFAULT_ROLE_STATUS_HOURS
    ])
    upsert_terminal_statuses(db, config, _DEFAULT_TERMINAL_STATUSES)

    db.commit()
    print(f"[seed] Создан дефолтный конфиг id={config.id}")
