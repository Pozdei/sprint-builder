"""Прогноз реализации эпика.

Отличия от sprint planning:
- Задачи берутся из JQL по эпику, а не с досок
- Нет бюджетного ограничения — все оставшиеся шаги расписываются до конца
- Текущий статус задачи определяет, с какого шага pipeline продолжать
- Включаем ВСЕ шаги pipeline, в т.ч. code_review/testing (не «post-alloc»)
- max(end_hours) → предиктная дата завершения
"""

from collections import defaultdict
from datetime import date, datetime

from app.sprint.buckets import RELEASE
from app.sprint.config import SprintConfig
from app.sprint.epic_history import build_past_phases, dt_to_work_hours
from app.sprint.gantt import compute_gantt_schedule, work_day_start
from app.sprint.logic import (
    _WORK_TYPE_INFO,
    _extract_developer_name,
    _extract_owners,
    _extract_role_hours,
    _field_account_id,
    _find_direction,
    _find_lead_owner,
    _find_pipeline_position,
    _has_real_estimate,
    _resolve_designer_for_direction,
    _resolve_developer_for_direction,
    _resolve_owner,
    _resolve_release_owner,
    _resolve_tester_for_direction,
    _role_override,
    _safe_content_role,
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
    past_bucket_hours: dict[str, float] | None = None,
) -> None:
    """Сгенерировать оставшиеся шаги pipeline для задачи эпика.

    current_stage_included=True → текущий шаг уже добавлен через role_status_buckets,
    генерируем начиная со следующего.
    current_stage_included=False → статус не распознан, генерируем всё с начала.
    past_bucket_hours — фактическая длительность уже пройденных этапов задачи
    (bucket → часы, из changelog в историчном режиме): повторный проход этапа
    после отката статуса планируем по ней, а не по полной оценке.
    """
    f = issue["fields"]
    key = issue["key"]
    work_types = direction.get("work_types", [])

    current_pos = _find_pipeline_position(status_name, work_types, cfg)
    start_from = current_pos if (current_stage_included and current_pos >= 0) else -1

    assignee_id, reporter_id, responsible_id = _extract_owners(f, cfg)
    sprint_num, sprint_name = extract_max_sprint_number(f.get(cfg.sprint_field))
    h_analyst, h_tester, h_developer, orig_hours = _extract_role_hours(f, cfg)
    dev_lead   = _find_lead_owner(cfg, "developer_lead")
    design_lead = _find_lead_owner(cfg, "designer_lead")

    explicit_tester = bool(_role_override(direction, "testing"))
    for pos, wt in enumerate(work_types):
        if pos < start_from:
            continue
        if pos == start_from:
            # Текущая стадия уже учтена в current-stage — пропускаем. Исключение:
            # тестирование с выделенным тестировщиком (его легаси analyst-кандидат
            # подавлён в collect_epic_remaining_work) — генерируем здесь.
            if not (wt == "testing" and explicit_tester):
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
        elif wt == "design":
            role = "designer"
            owner_id, role_team = _resolve_designer_for_direction(
                f, direction, cfg, team_by_role, assignee_id,
            )
        elif wt == "testing":
            owner_id, role, role_team = _resolve_tester_for_direction(
                issue, direction, cfg, team_by_role,
                assignee_id, responsible_id, reporter_id,
            )
        elif wt == "analytics":
            role = _safe_content_role(_role_override(direction, "analytics") or "analyst", bucket)
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
        elif wt == "release":
            dev_id = _field_account_id(f, cfg.developer_field)
            owner = _resolve_release_owner(dev_id, _extract_developer_name(f, cfg), cfg, dev_lead)
            if owner is None:
                continue
            owner_id, role, owner_name = owner
            role_team = {owner_id: cfg.team[owner_id]} if owner_id in cfg.team else {owner_id: {"file_name": owner_name}}
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
        hours_is_default = not _has_real_estimate(f, bucket, cfg, sp_field)
        if past_bucket_hours and bucket in past_bucket_hours:
            # Этап уже проходили (откат статуса) — повтор планируем по фактической
            # длительности прошлого прохода, а не по полной оценке.
            hours = past_bucket_hours[bucket]
            hours_is_default = False

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
            "hours_is_default": hours_is_default,
            "board": "[epic]",
            "sprint_num": sprint_num,
            "sprint_name": sprint_name,
            "formal_only": False,
            "is_pseudo": False,
            "hours_analyst": h_analyst,
            "hours_tester": h_tester,
            "hours_developer": h_developer,
            "hours_designer": f.get(cfg.role_hours_fields.get("designer", "")) or None,
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
    history_hours: dict[str, dict[str, float]] | None = None,
) -> tuple[list[dict], dict]:
    """Собрать оставшиеся рабочие единицы для задач эпика.

    history_hours — key → {bucket: часы} фактической длительности уже пройденных
    этапов (историчный режим): повторные проходы планируются по ним.
    Возвращает (work_items, diagnostics).
    """
    from app.sprint.logic import (
        _enabled_roles_by_status,
        _process_issue_for_role,
    )

    history_hours = history_hours or {}
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

        if status_name in terminal_set or _is_cancelled(status_name):
            counters["skipped_done"] += 1
            continue

        labels = f.get("labels") or []
        direction = _find_direction(labels, cfg)
        direction_name = direction["name"] if direction else None

        # Текущий шаг (если статус в role_status_buckets)
        role_buckets = status_to_roles.get(status_name, [])
        if direction and direction_name:
            # Для задач направления — фильтруем по роли разработчика направления
            direction_dev_role = _role_override(direction, "development") or "developer"
            # Если у направления явно задан тестировщик — подавляем легаси-кандидата
            # «аналитик тестит» (role_status_buckets мапит analyst→Тестирование почти
            # для всех статусов). Тестирование сгенерирует выделенный тестировщик ниже.
            explicit_tester = bool(_role_override(direction, "testing"))
            for role, bucket in role_buckets:
                if bucket == "Разработка" and role != direction_dev_role:
                    continue
                if bucket == "Тестирование" and explicit_tester:
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
                past_bucket_hours=history_hours.get(issue["key"]),
            )

    return list(by_key_role.values()), counters


_CANCELLED_STATUSES: frozenset[str] = frozenset({
    "отменено", "cancelled", "rejected", "won't do", "wont do", "отклонено",
})


def _is_cancelled(status_name: str) -> bool:
    return status_name.lower() in _CANCELLED_STATUSES


def _annotate_phase_costs(gantt_items: list[dict], cfg: SprintConfig) -> None:
    """Добавляет phase_cost к каждому элементу Ганта на основе оклада исполнителя.

    Псевдо-задачи (отпуск/отсутствие/руководство) — не проектная работа: их
    стоимость = 0, чтобы разбивка по задачам/людям сходилась с итоговым
    total_cost (он считается только по реальным задачам, см. _compute_cost)."""
    for item in gantt_items:
        if item.get("is_pseudo"):
            item["phase_cost"] = 0.0
            continue
        oid = item.get("owner_id") or ""
        member = cfg.team.get(oid) or {}
        salary = member.get("salary") or 0
        item["phase_cost"] = round(item["hours"] * salary / 160.0, 0) if salary > 0 else 0.0


def _compute_cost(items: list[dict], cfg: SprintConfig) -> tuple[float, dict[str, dict]]:
    """Стоимость по списку рабочих единиц: оклад / 160 ч/мес * часы.

    Возвращает (total_cost, breakdown) где breakdown: owner_id → {name,hours,salary,cost}.
    """
    total_cost = 0.0
    breakdown: dict[str, dict] = {}
    for w in items:
        if w.get("is_pseudo"):
            continue  # псевдо-задачи (отпуск/отсутствие/руководство) — не проектная стоимость
        oid = w.get("owner_id") or ""
        member = cfg.team.get(oid) or {}
        salary = member.get("salary") or 0
        hours = w.get("hours", 0)
        cost = hours * salary / 160.0 if salary > 0 else 0.0
        total_cost += cost
        if oid not in breakdown:
            breakdown[oid] = {
                "name": w.get("owner_file_name") or oid,
                "hours": 0.0, "salary": salary, "cost": 0.0,
            }
        breakdown[oid]["hours"] += hours
        breakdown[oid]["cost"] += cost
    return total_cost, breakdown


def _breakdown_to_list(breakdown: dict[str, dict]) -> list[dict]:
    return [
        {
            "name": v["name"],
            "hours": round(v["hours"], 1),
            "salary": v["salary"],
            "cost": round(v["cost"], 0),
        }
        for v in sorted(breakdown.values(), key=lambda x: -x["cost"])
    ]


def _build_with_history(
    issues: list[dict],
    cfg: SprintConfig,
    sp_field: str | None,
    base_url: str,
    start_date: date,
    hours_per_day: float,
    dependencies: list[dict] | None,
    vacations: list[dict] | None,
    config_snapshot: dict,
    root_tasks: dict[str, str] | None = None,
) -> dict:
    """Историчный режим: прошлые фазы из changelog + прогноз остатка на одной шкале."""
    now_dt = datetime.now()
    today = date.today()
    # Остаток планируем от выбранной даты начала, но не раньше сегодня:
    # прошлое на шкале уже занято фактическими фазами из changelog.
    forecast_start = start_date if start_date > today else today
    terminal_set = set(cfg.terminal_statuses)

    # 1. Прошлые фазы для всех задач (включая закрытые — у них есть прошлое)
    past_phases: list[dict] = []
    done_count = 0
    for issue in issues:
        f = issue["fields"]
        issuetype = (f.get("issuetype") or {}).get("name", "")
        if issuetype.lower() in ("эпик", "epic"):
            continue
        status_name = f["status"]["name"]
        if _is_cancelled(status_name):
            continue
        if status_name in terminal_set:
            done_count += 1
        past_phases.extend(build_past_phases(issue, cfg, sp_field, base_url, now_dt))

    # 2. Начало шкалы = самая ранняя дата фазы (или сегодня)
    origin = today
    for p in past_phases:
        d = p["_start_dt"].date()
        if d < origin:
            origin = d
    today_offset = dt_to_work_hours(work_day_start(today), origin, hours_per_day)
    forecast_offset = dt_to_work_hours(work_day_start(forecast_start), origin, hours_per_day)

    # 3. Координаты фаз на шкале (один раз — используются и здесь, и для баров)
    #    и фактическая длительность завершённых прошлых фаз: key → {bucket: часы}.
    #    По ней планируются повторные проходы этапов после отката статуса
    #    (перетест/пере-ревью занимает столько, сколько занял в прошлый раз;
    #    при нескольких прошлых проходах берём последний).
    history_hours: dict[str, dict[str, float]] = {}
    for p in past_phases:
        p["_sh"] = dt_to_work_hours(p["_start_dt"], origin, hours_per_day)
        p["_eh"] = dt_to_work_hours(p["_end_dt"], origin, hours_per_day, end=True)
        if p["_is_current_open"] or p["bucket"] == RELEASE:
            continue
        history_hours.setdefault(p["key"], {})[p["bucket"]] = max(
            round(p["_eh"] - p["_sh"], 1), 0.5,
        )

    # 4. Будущее (остаток) — только для незакрытых задач
    work_items, counters = collect_epic_remaining_work(
        issues, cfg, sp_field, base_url, history_hours=history_hours,
    )

    # 5. Прогноз от даты начала (≥ сегодня) + сдвиг в координаты шкалы
    forecast_items = compute_gantt_schedule(
        work_items, config_snapshot, forecast_start, hours_per_day,
        dependencies=dependencies or [], vacations=vacations or [],
        root_tasks=root_tasks,
    )
    for it in forecast_items:
        it["start_hours"] = round(it["start_hours"] + forecast_offset, 3)
        it["end_hours"] = round(it["end_hours"] + forecast_offset, 3)
        it["is_historical"] = False

    # 6. Прошлые фазы → элементы Ганта (реальные даты + часы от origin).
    #    Дедуп часов повторных проходов уже сделан в build_past_phases.
    min_width = hours_per_day * 0.2
    past_items: list[dict] = []
    for p in past_phases:
        sd = p.pop("_start_dt")
        ed = p.pop("_end_dt")
        is_current_open = p.pop("_is_current_open", False)
        sh = p.pop("_sh")
        eh = p.pop("_eh")
        if eh - sh < min_width:
            eh = sh + min_width
        p["start_hours"] = round(sh, 3)
        p["end_hours"] = round(eh, 3)
        p["start"] = sd.isoformat()
        p["end"] = ed.isoformat()
        if is_current_open:
            # Текущий статус ещё не завершён — этот же этап уже сидит в work_items
            # как будущая работа (с полной оценкой часов). Бар оставляем для
            # наглядности «висит в статусе с такой-то даты», но без часов/стоимости,
            # чтобы не задваивать с прогнозом остатка.
            p["hours"] = 0.0
        past_items.append(p)

    gantt_items = past_items + forecast_items
    gantt_items.sort(key=lambda x: (x["start_hours"], x.get("owner_file_name", "")))
    _annotate_phase_costs(gantt_items, cfg)

    # 7. Дата завершения = максимальный end среди будущих (иначе — конец прошлого)
    completion_date: str | None = None
    if forecast_items:
        completion_date = max(forecast_items, key=lambda x: x["end_hours"])["end"][:10]
    elif past_items:
        completion_date = max(p["end"] for p in past_items)[:10]

    # 8. Суммы: потрачено (прошлое) vs осталось (будущее)
    spent_hours = sum(p.get("hours", 0) for p in past_items)
    remaining_hours = sum(w.get("hours", 0) for w in work_items)
    spent_cost, _ = _compute_cost(past_items, cfg)
    remaining_cost, _ = _compute_cost(work_items, cfg)
    total_cost, breakdown = _compute_cost(past_items + work_items, cfg)

    return {
        "gantt_items": gantt_items,
        "completion_date": completion_date,
        "stats": {
            "total_issues": len(issues),
            "done_issues": done_count,
            "remaining_work_items": len(work_items),
            "total_planned_hours": round(spent_hours + remaining_hours, 1),
            "default_hours_count": sum(1 for w in work_items if w.get("hours_is_default")),
            "total_cost": round(total_cost, 0),
            "spent_hours": round(spent_hours, 1),
            "spent_cost": round(spent_cost, 0),
            "remaining_hours": round(remaining_hours, 1),
            "remaining_cost": round(remaining_cost, 0),
        },
        "cost_breakdown": _breakdown_to_list(breakdown),
        "warnings": counters.get("unmapped_status", []),
        "gantt_start": origin.isoformat(),
        "today_hours": round(today_offset, 3),
    }


def build_epic_forecast(
    issues: list[dict],
    cfg: SprintConfig,
    sp_field: str | None,
    base_url: str,
    start_date,
    hours_per_day: float = 8.0,
    dependencies: list[dict] | None = None,
    vacations: list[dict] | None = None,
    use_history: bool = False,
    root_tasks: dict[str, str] | None = None,
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
            }
            for d in cfg.directions
        ],
    }

    if use_history:
        return _build_with_history(
            issues, cfg, sp_field, base_url, start_date, hours_per_day,
            dependencies, vacations, config_snapshot,
            root_tasks=root_tasks,
        )

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
                "total_cost": 0,
                "spent_hours": 0, "spent_cost": 0,
                "remaining_hours": 0, "remaining_cost": 0,
            },
            "cost_breakdown": [],
            "warnings": counters.get("unmapped_status", []),
            "gantt_start": start_date.isoformat() if hasattr(start_date, "isoformat") else str(start_date),
            "today_hours": None,
        }

    gantt_items = compute_gantt_schedule(
        work_items, config_snapshot, start_date, hours_per_day,
        dependencies=dependencies or [],
        vacations=vacations or [],
        root_tasks=root_tasks,
    )
    _annotate_phase_costs(gantt_items, cfg)

    # Предиктная дата = максимальный end из всех элементов
    completion_date: str | None = None
    if gantt_items:
        last = max(gantt_items, key=lambda x: x["end_hours"])
        completion_date = last["end"][:10]  # только дата

    total_hours = sum(w.get("hours", 0) for w in work_items)
    default_count = sum(1 for w in work_items if w.get("hours_is_default"))
    total_cost, breakdown = _compute_cost(work_items, cfg)

    return {
        "gantt_items": gantt_items,
        "completion_date": completion_date,
        "stats": {
            "total_issues": len(issues),
            "done_issues": counters["skipped_done"],
            "remaining_work_items": len(work_items),
            "total_planned_hours": round(total_hours, 1),
            "default_hours_count": default_count,
            "total_cost": round(total_cost, 0),
            "spent_hours": 0, "spent_cost": 0,
            "remaining_hours": round(total_hours, 1),
            "remaining_cost": round(total_cost, 0),
        },
        "cost_breakdown": _breakdown_to_list(breakdown),
        "warnings": counters.get("unmapped_status", []),
        "gantt_start": start_date.isoformat() if hasattr(start_date, "isoformat") else str(start_date),
        "today_hours": None,
    }
