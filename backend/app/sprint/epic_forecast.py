"""Прогноз реализации эпика.

Отличия от sprint planning:
- Задачи берутся из JQL по эпику, а не с досок
- Нет бюджетного ограничения — все оставшиеся шаги расписываются до конца
- Текущий статус задачи определяет, с какого шага pipeline продолжать
- Включаем ВСЕ шаги pipeline, в т.ч. code_review/testing (не «post-alloc»)
- max(end_hours) → предиктная дата завершения
"""

from collections import defaultdict

from app.sprint.config import SprintConfig
from app.sprint.gantt import compute_gantt_schedule
from app.sprint.logic import (
    _WORK_TYPE_INFO,
    _extract_developer_name,
    _extract_owners,
    _extract_role_hours,
    _find_direction,
    _find_lead_owner,
    _find_pipeline_position,
    _has_real_estimate,
    _resolve_developer_for_direction,
    _resolve_owner,
    _team_with_role,
    estimate_hours_for_role,
    extract_max_sprint_number,
)


def _generate_all_remaining_stages(
    issue: dict,
    status_name: str,
    direction: dict,
    labels: list,
    by_key_role: dict,
    cfg: SprintConfig,
    base_url: str,
    sp_field: str | None,
    team_by_role: dict[str, dict[str, dict]],
    current_stage_included: bool,
    counters: dict,
) -> None:
    """Сгенерировать оставшиеся шаги pipeline для задачи эпика.

    current_stage_included=True → текущий шаг уже добавлен через role_status_buckets,
    генерируем начиная со следующего.
    current_stage_included=False → статус не распознан, генерируем всё с начала.
    """
    f = issue["fields"]
    key = issue["key"]
    work_types = direction.get("work_types", [])

    current_pos = _find_pipeline_position(status_name, work_types, cfg)
    # Если current_stage_included=True и current_pos>=0 → начинаем со следующего (pos > current_pos)
    # Если current_stage_included=False или current_pos<0 → начинаем с pos 0 (start_from = -1)
    start_from = current_pos if (current_stage_included and current_pos >= 0) else -1

    assignee_id, reporter_id, responsible_id = _extract_owners(f, cfg)
    sprint_num, sprint_name = extract_max_sprint_number(f.get(cfg.sprint_field))
    h_analyst, h_tester, h_developer, orig_hours = _extract_role_hours(f, cfg)
    dev_lead   = _find_lead_owner(cfg, "developer_lead")
    design_lead = _find_lead_owner(cfg, "designer_lead")

    for pos, wt in enumerate(work_types):
        if pos <= start_from:
            continue

        info = _WORK_TYPE_INFO.get(wt)
        if not info:
            continue

        bucket = info["bucket"]
        role: str
        owner_id: str | None
        role_team: dict[str, dict]

        if wt == "development":
            owner_id, role, role_team = _resolve_developer_for_direction(
                f, direction, cfg, team_by_role, assignee_id,
            )
        elif wt == "testing":
            role = direction.get("tester_role") or "analyst"
            role_team = team_by_role.get(role) or _team_with_role(cfg, role)
            owner_id = _resolve_owner(role, assignee_id, responsible_id, reporter_id, role_team)
        elif wt == "analytics":
            role = direction.get("analyst_role") or "analyst"
            role_team = team_by_role.get(role) or _team_with_role(cfg, role)
            owner_id = _resolve_owner(role, assignee_id, responsible_id, reporter_id, role_team)
        elif wt == "code_review":
            if not dev_lead:
                continue
            dev_lead_id, dev_lead_info = dev_lead
            owner_id, role = dev_lead_id, "developer_lead"
            role_team = {dev_lead_id: dev_lead_info}
        elif wt == "design_review":
            if not design_lead:
                continue
            dl_id, dl_info = design_lead
            owner_id, role = dl_id, "designer_lead"
            role_team = {dl_id: dl_info}
        else:
            role = info["role"]
            role_team = team_by_role.get(role) or _team_with_role(cfg, role)
            owner_id = _resolve_owner(role, assignee_id, responsible_id, reporter_id, role_team)

        if owner_id is None:
            continue

        cand_key = (key, role, bucket)
        if cand_key in by_key_role:
            continue

        hours = estimate_hours_for_role(f, role, bucket, status_name, cfg, sp_field)

        by_key_role[cand_key] = {
            "key": key,
            "url": f"{base_url}/browse/{key}",
            "summary": f.get("summary") or "",
            "status_name": status_name,
            "bucket": bucket,
            "role": role,
            "owner_id": owner_id,
            "owner_file_name": role_team[owner_id]["file_name"],
            "hours": hours,
            "hours_is_default": not _has_real_estimate(f, bucket, cfg, sp_field),
            "board": "[epic]",
            "sprint_num": sprint_num,
            "sprint_name": sprint_name,
            "formal_only": False,
            "is_pseudo": False,
            "hours_analyst": h_analyst,
            "hours_tester": h_tester,
            "hours_developer": h_developer,
            "hours_original": orig_hours,
            "direction": direction["name"],
            "labels": labels,
            "responsible_id": responsible_id,
            "assignee_id": assignee_id,
            "reporter_id": reporter_id,
            "developer_name": _extract_developer_name(f, cfg),
            "priority": pos + 1,   # позиция в pipeline как приоритет
        }
        counters["matched"] += 1


def collect_epic_remaining_work(
    issues: list[dict],
    cfg: SprintConfig,
    sp_field: str | None,
    base_url: str,
) -> tuple[list[dict], dict]:
    """Собрать оставшиеся рабочие единицы для задач эпика.

    Возвращает (work_items, diagnostics).
    """
    from app.sprint.logic import (
        _enabled_roles_by_status,
        _process_issue_for_role,
    )

    by_key_role: dict[tuple, dict] = {}
    counters: dict = {
        "matched": 0,
        "skipped_done": 0,
        "skipped_epic": 0,
        "unmapped_status": [],
    }

    terminal_set = set(cfg.terminal_statuses)
    status_to_roles = _enabled_roles_by_status(cfg)
    team_by_role: dict[str, dict[str, dict]] = {
        r["name"]: _team_with_role(cfg, r["name"])
        for r in cfg.roles if r["enabled"]
    }

    for issue in issues:
        f = issue["fields"]
        issuetype = (f.get("issuetype") or {}).get("name", "")
        if issuetype.lower() in ("эпик", "epic"):
            counters["skipped_epic"] += 1
            continue

        status_name = f["status"]["name"]

        if status_name in terminal_set:
            counters["skipped_done"] += 1
            continue

        labels = f.get("labels") or []
        direction = _find_direction(labels, cfg)
        direction_name = direction["name"] if direction else None

        # Текущий шаг (если статус в role_status_buckets)
        role_buckets = status_to_roles.get(status_name, [])
        if direction and direction_name:
            # Для задач направления — фильтруем по dev_role
            direction_dev_role = direction.get("dev_role") or "developer"
            for role, bucket in role_buckets:
                if bucket == "Разработка" and role != direction_dev_role:
                    continue
                _process_issue_for_role(
                    issue, role, bucket, team_by_role.get(role, {}),
                    "[epic]", by_key_role, counters, cfg, base_url, sp_field,
                    direction_name=direction_name, labels=labels,
                )
        else:
            for role, bucket in role_buckets:
                _process_issue_for_role(
                    issue, role, bucket, team_by_role.get(role, {}),
                    "[epic]", by_key_role, counters, cfg, base_url, sp_field,
                    direction_name=direction_name, labels=labels,
                )

        current_stage_included = bool(role_buckets)

        if not current_stage_included and not direction:
            counters["unmapped_status"].append(
                f"{issue['key']} [{status_name}]"
            )

        # Будущие шаги pipeline (включая code_review, testing)
        if direction:
            _generate_all_remaining_stages(
                issue, status_name, direction, labels,
                by_key_role, cfg, base_url, sp_field,
                team_by_role, current_stage_included, counters,
            )

    return list(by_key_role.values()), counters


def build_epic_forecast(
    issues: list[dict],
    cfg: SprintConfig,
    sp_field: str | None,
    base_url: str,
    start_date,
    hours_per_day: float = 8.0,
) -> dict:
    """Рассчитать прогноз реализации эпика.

    Возвращает:
    {
      "gantt_items": [...],          # расписание (как в sprint Gantt)
      "completion_date": "ISO date", # предиктная дата завершения
      "stats": {...},                # сводка
      "warnings": [...],             # задачи с неизвестными статусами
    }
    """
    config_snapshot = {
        "hours_per_person": 999_999.0,   # нет ограничения для эпика
        "directions": [
            {
                "name": d.get("name"),
                "labels": d.get("labels", []),
                "work_types": d.get("work_types", []),
                "dev_role": d.get("dev_role", ""),
            }
            for d in cfg.directions
        ],
    }

    work_items, counters = collect_epic_remaining_work(
        issues, cfg, sp_field, base_url,
    )

    if not work_items:
        return {
            "gantt_items": [],
            "completion_date": None,
            "stats": {
                "total_issues": len(issues),
                "done_issues": counters["skipped_done"],
                "remaining_work_items": 0,
                "total_planned_hours": 0,
                "default_hours_count": 0,
            },
            "warnings": counters.get("unmapped_status", []),
        }

    gantt_items = compute_gantt_schedule(
        work_items, config_snapshot, start_date, hours_per_day,
    )

    # Предиктная дата = максимальный end из всех элементов
    completion_date: str | None = None
    if gantt_items:
        last = max(gantt_items, key=lambda x: x["end_hours"])
        completion_date = last["end"][:10]  # только дата

    total_hours = sum(w.get("hours", 0) for w in work_items)
    default_count = sum(1 for w in work_items if w.get("hours_is_default"))

    return {
        "gantt_items": gantt_items,
        "completion_date": completion_date,
        "stats": {
            "total_issues": len(issues),
            "done_issues": counters["skipped_done"],
            "remaining_work_items": len(work_items),
            "total_planned_hours": round(total_hours, 1),
            "default_hours_count": default_count,
        },
        "warnings": counters.get("unmapped_status", []),
    }
