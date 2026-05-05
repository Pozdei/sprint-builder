"""Seed: при первом старте бэкенда создаём дефолтный конфиг.

Запускается из app/main.py через startup-event. Идемпотентно:
если is_default уже есть — ничего не делает.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import models
from app.db.repository import (
    upsert_boards, upsert_bucket_hours_fields, upsert_components,
    upsert_role_hours_fields, upsert_status_buckets, upsert_status_priorities,
    upsert_strict_assignee_buckets, upsert_team_members,
)


# Дефолтные значения — те же, что были в app/sprint/config.py
_DEFAULT = {
    "name": "Default",
    "project_key": "SHN",
    "sprint_field": "customfield_10018",
    "responsible_field": "customfield_10105",
    "hours_per_person": 80.0,
    "default_task_hours": 12.0,
    "team": {
        "712020:4eef6bdf-ac1f-4ef0-821d-836758c09514": {
            "jira_name": "Aida Badamova", "file_name": "Бадамова А",
        },
        "712020:abca6d44-4a90-4a35-951b-fa9bf2811287": {
            "jira_name": "Aleksey Strazdin", "file_name": "Страздин А.",
        },
        "712020:ab0ca3ac-138c-4f14-b983-6211fc0bb850": {
            "jira_name": "Aleksey Batrakov", "file_name": "Батраков А.",
        },
        "712020:02f9154d-d25a-4a6b-9226-4d092c3970c7": {
            "jira_name": "Ruslan Amanov", "file_name": "Аманов Р.",
        },
    },
    "boards": {
        "Serial": 1665,
        "Purchase Order Management": 1896,
        "Retail Wms": 1995,
        "Space": 3296,
        "Wfm": 1764,
    },
    "extra_components": ["3PL integration hub"],
    "status_bucket": {
        "Создана": "Анализ", "Новый": "Анализ", "Анализ": "Анализ", "В работе": "Анализ",
        "Готов к разработке": "Тестирование", "К разработке": "Тестирование",
        "В разработке": "Тестирование", "Код-ревью": "Тестирование",
        "К тестированию": "Тестирование", "Тестирование": "Тестирование",
    },
    "status_priority": {
        "К тестированию": 0, "Тестирование": 0,
        "Код-ревью": 1, "В разработке": 1, "Готов к разработке": 1, "К разработке": 1,
        "Анализ": 2, "В работе": 2,
        "Создана": 3, "Новый": 3,
    },
    "bucket_hours_field": {
        "Анализ": "customfield_10235",
        "Тестирование": "customfield_11406",
    },
    "role_hours_fields": {
        "analyst": "customfield_10235",
        "tester": "customfield_11406",
        "developer": "customfield_10234",
    },
    "strict_assignee_buckets": [],
}


def seed_default_config(db: Session) -> None:
    existing = db.scalar(select(models.Config).where(models.Config.is_default == True))  # noqa: E712
    if existing:
        return  # уже есть — ничего не делаем

    config = models.Config(
        name=_DEFAULT["name"],
        is_default=True,
        project_key=_DEFAULT["project_key"],
        sprint_field=_DEFAULT["sprint_field"],
        responsible_field=_DEFAULT["responsible_field"],
        hours_per_person=_DEFAULT["hours_per_person"],
        default_task_hours=_DEFAULT["default_task_hours"],
    )
    db.add(config)
    db.flush()  # получим config.id, чтобы привязывать дочерние

    # Заполняем дочерние таблицы через репозиторий
    upsert_team_members(db, config, [
        {"jira_account_id": acc_id, "jira_name": info["jira_name"],
         "file_name": info["file_name"], "sort_order": i}
        for i, (acc_id, info) in enumerate(_DEFAULT["team"].items())
    ])
    upsert_boards(db, config, [
        {"name": name, "jira_board_id": bid}
        for name, bid in _DEFAULT["boards"].items()
    ])
    upsert_components(db, config, _DEFAULT["extra_components"])
    upsert_status_buckets(db, config, _DEFAULT["status_bucket"])
    upsert_status_priorities(db, config, _DEFAULT["status_priority"])
    upsert_bucket_hours_fields(db, config, _DEFAULT["bucket_hours_field"])
    upsert_role_hours_fields(db, config, _DEFAULT["role_hours_fields"])
    upsert_strict_assignee_buckets(db, config, _DEFAULT["strict_assignee_buckets"])

    db.commit()
    print(f"[seed] Создан дефолтный конфиг id={config.id}")
