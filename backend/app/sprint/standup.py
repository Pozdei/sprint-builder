"""Логика формирования данных для стендапа.

По гант-расписанию определяем задачи, которые должны были быть начаты
к указанной дате стендапа (включительно), и группируем по исполнителям.
"""

from collections import defaultdict
from datetime import date, timedelta

from app.sprint.gantt import compute_gantt_schedule


def _working_hours_by_eod(sprint_start: date, target_date: date,
                           hours_per_day: float) -> float:
    """Рабочие часы от старта спринта до конца target_date включительно."""
    if target_date < sprint_start:
        return 0.0
    hours = 0.0
    d = sprint_start
    while d <= target_date:
        if d.weekday() < 5:
            hours += hours_per_day
        d += timedelta(days=1)
    return hours


def build_standup(
    tasks: list[dict],
    config_snapshot: dict,
    sprint_start: date,
    standup_date: date,
    hours_per_day: float,
    role_filter: set[str] | None,
) -> list[dict]:
    """Собрать данные для стендапа.

    Возвращает список исполнителей с задачами, которые по плану уже должны
    были начаться к standup_date.

    Структура:
    [
      {
        "owner_id": "...",
        "owner_file_name": "Самарин",
        "role": "developer",
        "tasks": [
          {
            "key": "SHN-100",
            "summary": "...",
            "url": "...",
            "bucket": "Разработка",
            "planned_start": "2025-01-20T09:00:00",
            "planned_end": "2025-01-20T17:00:00",
            "planned_hours": 8.0,
            "is_overdue": True  # по плану уже должна была закончиться
          }
        ]
      }
    ]
    """
    gantt = compute_gantt_schedule(tasks, config_snapshot, sprint_start, hours_per_day)

    # Порог: сколько рабочих часов прошло к концу standup_date
    hours_threshold = _working_hours_by_eod(sprint_start, standup_date, hours_per_day)

    # Берём только реальные (не псевдо) задачи, начавшиеся к standup_date
    relevant = [
        item for item in gantt
        if not item.get("is_pseudo")
        and item["start_hours"] < hours_threshold  # start < EOD сегодня
    ]

    # Фильтрация по ролям
    if role_filter:
        relevant = [item for item in relevant if item.get("role") in role_filter]

    if not relevant:
        return []

    # Группируем по исполнителю, дедуплицируем (key, bucket)
    by_owner: dict[str, dict] = {}
    for item in relevant:
        oid = item["owner_id"]
        if oid not in by_owner:
            by_owner[oid] = {
                "owner_id": oid,
                "owner_file_name": item.get("owner_file_name", ""),
                "role": item.get("role", ""),
                "tasks": [],
                "_seen": set(),
            }
        tid = (item["key"], item["bucket"])
        if tid in by_owner[oid]["_seen"]:
            continue
        by_owner[oid]["_seen"].add(tid)
        by_owner[oid]["tasks"].append({
            "key": item["key"],
            "summary": item.get("summary", ""),
            "url": item.get("url", ""),
            "bucket": item["bucket"],
            "planned_start": item["start"],
            "planned_end": item["end"],
            "planned_hours": item["hours"],
            "is_overdue": item["end_hours"] <= hours_threshold,
        })

    result = []
    for entry in by_owner.values():
        entry.pop("_seen")
        result.append(entry)

    # Сортируем: сначала по роли, потом по имени
    result.sort(key=lambda x: (x["role"], x["owner_file_name"]))
    return result
