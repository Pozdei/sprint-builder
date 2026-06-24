"""Алгоритм планирования задач спринта на временну́ю шкалу (Гант).

Два прохода:
1. Event-driven scheduling для реальных задач — учитывает занятость исполнителя,
   pipeline-зависимости (шаг B по ключу K начинается не раньше шага A) и
   кросс-задачные FS-зависимости (задача B стартует после окончания всех этапов A).
2. Псевдо-задачи (Руководство, Отсутствие, ...) заполняют пробелы в расписании.
   Отпуска исполнителей исключаются из пробелов и отображаются отдельными барами.
"""

import heapq
from collections import defaultdict
from datetime import date, datetime, timedelta

_WORK_TYPE_TO_BUCKET = {
    "analytics":     "Анализ",
    "development":   "Разработка",
    "testing":       "Тестирование",
    "design":        "Дизайн",
    "code_review":   "Код-ревью",
    "design_review": "Дизайн-ревью",
    "release":       "Релиз",
}

_DEFAULT_BUCKET_PIPELINE = [
    "Анализ", "Дизайн", "Разработка", "Код-ревью", "Дизайн-ревью", "Тестирование", "Релиз",
]

WORK_START_HOUR = 9


# -------------------- Временны́е утилиты --------------------

def _working_hours_to_dt(sprint_start: date, hours: float, hours_per_day: float) -> datetime:
    """Рабочие часы от старта спринта → datetime (с учётом выходных)."""
    remaining = float(hours)
    current = datetime.combine(sprint_start, datetime.min.time()).replace(hour=WORK_START_HOUR)
    while remaining > 1e-9:
        if current.weekday() >= 5:
            current = (current + timedelta(days=1)).replace(
                hour=WORK_START_HOUR, minute=0, second=0, microsecond=0)
            continue
        elapsed_today = current.hour - WORK_START_HOUR + current.minute / 60.0
        available_today = hours_per_day - elapsed_today
        if remaining <= available_today + 1e-9:
            current += timedelta(hours=remaining)
            remaining = 0
        else:
            remaining -= available_today
            current = (current + timedelta(days=1)).replace(
                hour=WORK_START_HOUR, minute=0, second=0, microsecond=0)
    return current


def _date_to_work_hour(d: date, sprint_start: date, hours_per_day: float) -> float | None:
    """Календарная дата → рабочий час относительно старта спринта.

    Возвращает None, если дата является выходным.
    """
    if d.weekday() >= 5:
        return None
    work_day = 0
    cur = sprint_start
    while cur < d:
        if cur.weekday() < 5:
            work_day += 1
        cur += timedelta(days=1)
    return work_day * hours_per_day


def _compute_vacation_blocks(
    vacations: list[dict],
    sprint_start: date,
    hours_per_day: float,
) -> dict[str, list[tuple[float, float]]]:
    """Отпуска → заблокированные рабочие часы на человека.

    vacations: список dict с полями owner_id, start_date, end_date (YYYY-MM-DD).
    Возвращает: owner_id → отсортированный список (start_h, end_h).
    """
    raw: dict[str, list[tuple[float, float]]] = defaultdict(list)
    for vac in vacations:
        owner_id = vac["owner_id"]
        start_d = date.fromisoformat(vac["start_date"])
        end_d = date.fromisoformat(vac["end_date"])
        cur = start_d
        while cur <= end_d:
            h = _date_to_work_hour(cur, sprint_start, hours_per_day)
            if h is not None:
                raw[owner_id].append((h, h + hours_per_day))
            cur += timedelta(days=1)

    result: dict[str, list[tuple[float, float]]] = {}
    for pid, blocks in raw.items():
        blocks.sort()
        merged: list[list[float]] = []
        for s, e in blocks:
            if merged and s <= merged[-1][1]:
                merged[-1][1] = max(merged[-1][1], e)
            else:
                merged.append([s, e])
        result[pid] = [(s, e) for s, e in merged]
    return result


def _skip_blocks(h: float, blocks: list[tuple[float, float]]) -> float:
    """Сдвинуть h вперёд за все перекрывающиеся блоки отпуска."""
    changed = True
    while changed:
        changed = False
        for s, e in blocks:
            if s <= h < e:
                h = e
                changed = True
    return h


def _work_end(start: float, duration: float, blocks: list[tuple[float, float]]) -> float:
    """Вычислить end_h задачи с учётом блоков отпуска внутри интервала работы."""
    remaining = duration
    cur = start
    for s, e in sorted(blocks):
        if e <= cur:
            continue
        if s >= cur + remaining:
            break
        if s > cur:
            consumed = s - cur
            if consumed >= remaining:
                return cur + remaining
            remaining -= consumed
        cur = e
    return cur + remaining


# -------------------- Pipeline --------------------

def _build_direction_pipelines(config_snapshot: dict) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for d in config_snapshot.get("directions", []):
        buckets = [
            _WORK_TYPE_TO_BUCKET[wt]
            for wt in d.get("work_types", [])
            if wt in _WORK_TYPE_TO_BUCKET
        ]
        result[d["name"]] = buckets
    return result


# -------------------- Шаг 1: реальные задачи --------------------

def _schedule_real_tasks(
    real_tasks: list[dict],
    config_snapshot: dict,
    hours_per_day: float,
    cross_task_deps: list[dict] | None = None,
    vacation_blocks: dict[str, list[tuple[float, float]]] | None = None,
    root_tasks: dict[str, str] | None = None,
) -> tuple[dict[tuple, tuple[float, float]], dict[str, float]]:
    """Event-driven scheduling для реальных задач.

    cross_task_deps: список {from_key, to_key, from_bucket?, to_bucket?} — FS-зависимости
    между задачами. from_bucket/to_bucket пусты — зависимость на уровне всей задачи
    (последний этап A -> первый этап B); заданы — зависимость на конкретном этапе.
    vacation_blocks: owner_id → [(start_h, end_h), ...] — заблокированное время.
    root_tasks: owner_id → task_key — стартовая (корневая) задача исполнителя:
    встаёт первой в его очереди (Start-Start), не нарушая pipeline-зависимости —
    если она ещё не готова к старту, очередь продолжает работу по приоритету.

    Возвращает:
    - scheduled: (key, bucket) → (start_h, end_h)
    - person_cursor: person_id → end_h последней задачи
    """
    dir_pipelines = _build_direction_pipelines(config_snapshot)
    cross_deps = cross_task_deps or []
    vac = vacation_blocks or {}
    roots = root_tasks or {}

    task_by_id: dict[tuple, dict] = {(t["key"], t["bucket"]): t for t in real_tasks}

    def pipeline_for(task: dict) -> list[str]:
        d = task.get("direction")
        return dir_pipelines.get(d, _DEFAULT_BUCKET_PIPELINE) if d else _DEFAULT_BUCKET_PIPELINE

    def pipeline_predecessor(task: dict) -> tuple | None:
        pl = pipeline_for(task)
        bucket = task["bucket"]
        if bucket not in pl:
            return None
        idx = pl.index(bucket)
        if idx == 0:
            return None
        pred_bucket = pl[idx - 1]
        pred = (task["key"], pred_bucket)
        return pred if pred in task_by_id else None

    def key_pipeline(key: str, task: dict) -> list[str]:
        return pipeline_for(task)

    def last_stage_of_key(key: str) -> tuple | None:
        """Последний РАБОЧИЙ bucket ключа key в его pipeline (для кросс-задачных
        FS-зависимостей). Веха «Релиз» всегда стоит последней в pipeline, но это
        не работа, а сигнал готовности — её время не должно блокировать старт
        зависимых задач (зависимый может стартовать сразу по готовности
        реального этапа, не дожидаясь формального релиза предшественника)."""
        stages = [(k, b) for k, b in task_by_id if k == key]
        if not stages:
            return None
        sample_task = task_by_id[stages[0]]
        pl = pipeline_for(sample_task)
        for bucket in reversed(pl):
            if bucket == "Релиз":
                continue
            if (key, bucket) in task_by_id:
                return (key, bucket)
        return stages[-1]

    def first_stage_of_key(key: str) -> tuple | None:
        """Первый bucket ключа key в его pipeline."""
        stages = [(k, b) for k, b in task_by_id if k == key]
        if not stages:
            return None
        sample_task = task_by_id[stages[0]]
        pl = pipeline_for(sample_task)
        for bucket in pl:
            if (key, bucket) in task_by_id:
                return (key, bucket)
        return stages[0]

    # Строим all_preds: каждая задача → список всех её predecessors
    all_preds: dict[tuple, list[tuple]] = defaultdict(list)
    for t in real_tasks:
        tid = (t["key"], t["bucket"])
        pred = pipeline_predecessor(t)
        if pred:
            all_preds[tid].append(pred)

    # Добавляем кросс-задачные FS-зависимости. Этап не указан — поведение «по
    # умолчанию» (последний этап A -> первый этап B); указан — зависимость именно
    # на этом этапе («колбаске»), остальные этапы A/B зависимостью не связаны.
    for dep in cross_deps:
        from_key = dep.get("from_key", "")
        to_key = dep.get("to_key", "")
        if not from_key or not to_key or from_key == to_key:
            continue
        from_bucket = dep.get("from_bucket")
        to_bucket = dep.get("to_bucket")
        from_tid = (from_key, from_bucket) if from_bucket else last_stage_of_key(from_key)
        to_tid = (to_key, to_bucket) if to_bucket else first_stage_of_key(to_key)
        if not from_tid or from_tid not in task_by_id:
            continue
        if not to_tid or to_tid not in task_by_id:
            continue
        if from_tid not in all_preds[to_tid]:
            all_preds[to_tid].append(from_tid)

    # Обратная карта: задача → кто на неё ждёт
    dependents: dict[tuple, list[tuple]] = defaultdict(list)
    for tid, preds in all_preds.items():
        for pred in preds:
            if tid not in dependents[pred]:
                dependents[pred].append(tid)

    def all_preds_done(tid: tuple) -> bool:
        return all(p in finish_times for p in all_preds.get(tid, []))

    def dep_end_h(tid: tuple) -> float:
        preds = all_preds.get(tid, [])
        if not preds:
            return 0.0
        return max(finish_times.get(p, 0.0) for p in preds)

    # Очереди задач по исполнителям (сортировка по приоритету).
    # Веха «Релиз» — не работа, которая встаёт в очередь и занимает время
    # исполнителя, а сигнал готовности: катить можно сразу, как только готов
    # предшествующий этап (обычно — Тестирование), независимо от того, чем
    # человек занят параллельно. Поэтому она не участвует в очереди/курсоре
    # владельца — планируется отдельно, сразу по готовности зависимостей.
    person_tasks: dict[str, list[dict]] = defaultdict(list)
    for t in real_tasks:
        if t["bucket"] == "Релиз":
            continue
        person_tasks[t["owner_id"]].append(t)
    for pid in person_tasks:
        person_tasks[pid].sort(key=lambda x: (x.get("priority") or 9999, x.get("key", "")))
        root_key = roots.get(pid)
        if root_key:
            person_tasks[pid].sort(key=lambda x: x.get("key") != root_key)

    scheduled: dict[tuple, tuple[float, float]] = {}
    finish_times: dict[tuple, float] = {}
    person_cursor: dict[str, float] = defaultdict(float)

    event_q: list = []

    def enqueue_next(person_id: str, after_h: float) -> None:
        person_vac = vac.get(person_id, [])
        for t in person_tasks[person_id]:
            tid = (t["key"], t["bucket"])
            if tid in scheduled:
                continue
            if not all_preds_done(tid):
                continue
            de = dep_end_h(tid)
            earliest = _skip_blocks(max(after_h, de), person_vac)
            heapq.heappush(event_q, (
                earliest,
                t.get("priority") or 9999,
                t.get("key", ""),
                t["bucket"],
                person_id,
                tid,
            ))
            break

    for person_id in person_tasks:
        enqueue_next(person_id, 0.0)

    # Вехи «Релиз», которым уже ничего не мешает (предшественник не входит в
    # этот батч — например, уже отыграл своё в прошлом) — сразу в очередь.
    for t in real_tasks:
        if t["bucket"] != "Релиз":
            continue
        tid = (t["key"], t["bucket"])
        if all_preds_done(tid):
            heapq.heappush(event_q, (
                dep_end_h(tid),
                t.get("priority") or 9999,
                t.get("key", ""),
                t["bucket"],
                t["owner_id"],
                tid,
            ))

    while event_q:
        earliest, _prio, _key, _bucket, person_id, tid = heapq.heappop(event_q)
        if tid in scheduled:
            continue
        t = task_by_id.get(tid)
        if not t:
            continue
        if not all_preds_done(tid):
            continue

        is_release = t["bucket"] == "Релиз"
        person_vac = vac.get(person_id, [])
        de = dep_end_h(tid)
        start_h = _skip_blocks(de if is_release else max(person_cursor[person_id], de), person_vac)
        hours = max(t.get("hours") or 0.0, 0.0)
        end_h = _work_end(start_h, hours, person_vac)

        scheduled[tid] = (start_h, end_h)
        finish_times[tid] = end_h
        if not is_release:
            person_cursor[person_id] = end_h
            enqueue_next(person_id, end_h)

        for dep_tid in dependents.get(tid, []):
            dep_t = task_by_id.get(dep_tid)
            if dep_t and dep_tid not in scheduled:
                if not all_preds_done(dep_tid):
                    continue
                other = dep_t["owner_id"]
                other_vac = vac.get(other, [])
                other_de = dep_end_h(dep_tid)
                dep_is_release = dep_t["bucket"] == "Релиз"
                other_base = other_de if dep_is_release else max(person_cursor[other], other_de)
                other_start = _skip_blocks(other_base, other_vac)
                heapq.heappush(event_q, (
                    other_start,
                    dep_t.get("priority") or 9999,
                    dep_t.get("key", ""),
                    dep_t["bucket"],
                    other,
                    dep_tid,
                ))

    return scheduled, dict(person_cursor)


def _fill_pseudo_gaps(
    pseudo_tasks: list[dict],
    real_items: list[dict],
    budget_hours: float,
    vacation_blocks: dict[str, list[tuple[float, float]]] | None = None,
) -> list[dict]:
    """Заполнить пробелы псевдо-задачами.

    Отпуска (vacation_blocks) исключаются из пробелов — они отображаются отдельно.
    Каждая псевдо-задача может быть разбита на несколько сегментов.
    """
    vac = vacation_blocks or {}

    # Реальные задачи по исполнителям
    real_by_person: dict[str, list[tuple[float, float]]] = defaultdict(list)
    for item in real_items:
        real_by_person[item["owner_id"]].append(
            (item["start_hours"], item["end_hours"])
        )

    # Добавляем блоки отпуска в «занятое» время
    for pid, blocks in vac.items():
        for s, e in blocks:
            if s < budget_hours:
                real_by_person[pid].append((s, min(e, budget_hours)))

    for pid in real_by_person:
        real_by_person[pid].sort()

    # Псевдо-задачи по исполнителям
    pseudo_by_person: dict[str, list[dict]] = defaultdict(list)
    for t in pseudo_tasks:
        pseudo_by_person[t["owner_id"]].append(t)

    result: list[dict] = []

    all_persons = set(pseudo_by_person.keys())

    for person_id in all_persons:
        person_pseudo = pseudo_by_person[person_id]
        person_real = real_by_person.get(person_id, [])

        gaps: list[tuple[float, float]] = []
        prev_end = 0.0
        for start, end in person_real:
            if start > prev_end + 1e-9:
                gaps.append((prev_end, start))
            prev_end = max(prev_end, end)
        if prev_end < budget_hours - 1e-9:
            gaps.append((prev_end, budget_hours))

        gap_iter = iter(gaps)
        current_gap = next(gap_iter, None)
        gap_remaining = (current_gap[1] - current_gap[0]) if current_gap else 0.0

        for pseudo in person_pseudo:
            task_remaining = pseudo.get("hours") or 0.0
            seg_idx = 0

            while task_remaining > 1e-9 and current_gap is not None:
                if gap_remaining < 1e-9:
                    current_gap = next(gap_iter, None)
                    gap_remaining = (current_gap[1] - current_gap[0]) if current_gap else 0.0
                    if current_gap is None:
                        break

                take = min(task_remaining, gap_remaining)
                seg_start = current_gap[1] - gap_remaining
                seg_end = seg_start + take

                seg = pseudo.copy()
                seg["start_hours"] = round(seg_start, 3)
                seg["end_hours"] = round(seg_end, 3)
                seg["hours"] = round(take, 3)
                seg["_seg_idx"] = seg_idx
                result.append(seg)

                task_remaining -= take
                gap_remaining -= take
                seg_idx += 1

    return result


def _make_vacation_items(
    vacations: list[dict],
    vacation_blocks: dict[str, list[tuple[float, float]]],
    budget_hours: float,
    sprint_start: date,
    hours_per_day: float,
) -> list[dict]:
    """Создать GanttItem'ы для периодов отпуска."""
    # Собираем display_name по owner_id из vacations
    display_by_owner: dict[str, str] = {}
    for v in vacations:
        display_by_owner[v["owner_id"]] = v.get("display_name", v["owner_id"])

    items: list[dict] = []
    for owner_id, blocks in vacation_blocks.items():
        display = display_by_owner.get(owner_id, owner_id)
        for s, e in blocks:
            # Показываем только в пределах бюджета спринта
            seg_s = s
            seg_e = min(e, budget_hours + hours_per_day * 5)  # небольшой запас за бюджет
            if seg_s >= seg_e:
                continue
            items.append({
                "key": f"__vacation__{owner_id}",
                "summary": "Отпуск",
                "bucket": "Отпуск",
                "role": "",
                "owner_id": owner_id,
                "owner_file_name": display,
                "hours": round(seg_e - seg_s, 3),
                "is_pseudo": True,
                "url": "",
                "direction": None,
                "start_hours": round(seg_s, 3),
                "end_hours": round(seg_e, 3),
                "hours_is_default": False,
                "start": _working_hours_to_dt(sprint_start, seg_s, hours_per_day).isoformat(),
                "end": _working_hours_to_dt(sprint_start, seg_e, hours_per_day).isoformat(),
            })
    return items


# -------------------- Главная функция --------------------

def compute_gantt_schedule(
    tasks: list[dict],
    config_snapshot: dict,
    sprint_start: date,
    hours_per_day: float = 8.0,
    dependencies: list[dict] | None = None,
    vacations: list[dict] | None = None,
    root_tasks: dict[str, str] | None = None,
) -> list[dict]:
    """Рассчитать расписание Ганта.

    dependencies: список {from_key, to_key, from_bucket?, to_bucket?} — FS-зависимости.
    Этап не указан — зависимость на уровне всей задачи; указан — на конкретном этапе.
    vacations: список {owner_id, start_date, end_date} — отпуска сотрудников.
    root_tasks: owner_id → task_key — стартовая задача исполнителя (Start-Start).

    Каждый элемент результата:
      start / end — ISO datetime
      start_hours / end_hours — рабочие часы от начала спринта
    """
    real_tasks = [t for t in tasks if not t.get("is_pseudo")]
    pseudo_tasks = [t for t in tasks if t.get("is_pseudo")]

    budget = float(config_snapshot.get("hours_per_person", hours_per_day * 10))

    # Блоки отпуска per person
    vac_blocks = _compute_vacation_blocks(
        vacations or [], sprint_start, hours_per_day
    )

    # Шаг 1: расставляем реальные задачи
    scheduled, person_cursor = _schedule_real_tasks(
        real_tasks, config_snapshot, hours_per_day,
        cross_task_deps=dependencies or [],
        vacation_blocks=vac_blocks,
        root_tasks=root_tasks,
    )

    real_items: list[dict] = []
    for t in real_tasks:
        tid = (t["key"], t["bucket"])
        if tid not in scheduled:
            continue
        start_h, end_h = scheduled[tid]
        real_items.append({
            **t,
            "start_hours": round(start_h, 3),
            "end_hours": round(end_h, 3),
            "start": _working_hours_to_dt(sprint_start, start_h, hours_per_day).isoformat(),
            "end": _working_hours_to_dt(sprint_start, end_h, hours_per_day).isoformat(),
        })

    # Шаг 2: заполняем пробелы псевдо-задачами (исключая отпуска)
    pseudo_items = _fill_pseudo_gaps(
        pseudo_tasks, real_items, budget, vacation_blocks=vac_blocks
    )
    for seg in pseudo_items:
        seg["start"] = _working_hours_to_dt(sprint_start, seg["start_hours"], hours_per_day).isoformat()
        seg["end"] = _working_hours_to_dt(sprint_start, seg["end_hours"], hours_per_day).isoformat()

    # Шаг 3: добавляем бары отпусков — только для исполнителей с реальными задачами
    active_owners = {t["owner_id"] for t in real_items}
    active_vac_blocks = {k: v for k, v in vac_blocks.items() if k in active_owners}
    vacation_items = _make_vacation_items(
        [v for v in (vacations or []) if v.get("owner_id") in active_owners],
        active_vac_blocks, budget, sprint_start, hours_per_day
    )

    all_items = real_items + pseudo_items + vacation_items
    all_items.sort(key=lambda x: (x["start_hours"], x.get("owner_file_name", "")))
    return all_items
