"""Алгоритм планирования задач спринта на временну́ю шкалу (Гант).

Два прохода:
1. Event-driven scheduling для реальных задач — учитывает занятость исполнителя
   и pipeline-зависимости (шаг B по ключу K начинается не раньше шага A).
2. Псевдо-задачи (Руководство, Отсутствие, ...) заполняют пробелы в расписании.
   Одна псевдо-задача может быть разбита на несколько сегментов между реальными.
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
}

_DEFAULT_BUCKET_PIPELINE = [
    "Анализ", "Дизайн", "Разработка", "Код-ревью", "Дизайн-ревью", "Тестирование",
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
) -> tuple[dict[tuple, tuple[float, float]], dict[str, float]]:
    """Event-driven scheduling для реальных задач.

    Возвращает:
    - scheduled: (key, bucket) → (start_h, end_h)
    - person_cursor: person_id → end_h последней задачи
    """
    dir_pipelines = _build_direction_pipelines(config_snapshot)

    task_by_id: dict[tuple, dict] = {(t["key"], t["bucket"]): t for t in real_tasks}

    def pipeline_for(task: dict) -> list[str]:
        d = task.get("direction")
        return dir_pipelines.get(d, _DEFAULT_BUCKET_PIPELINE) if d else _DEFAULT_BUCKET_PIPELINE

    def predecessor_id(task: dict) -> tuple | None:
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

    deps: dict[tuple, tuple | None] = {
        (t["key"], t["bucket"]): predecessor_id(t) for t in real_tasks
    }
    dependents: dict[tuple, list[tuple]] = defaultdict(list)
    for tid, pred in deps.items():
        if pred:
            dependents[pred].append(tid)

    # Очереди задач по исполнителям (сортировка по приоритету)
    person_tasks: dict[str, list[dict]] = defaultdict(list)
    for t in real_tasks:
        person_tasks[t["owner_id"]].append(t)
    for pid in person_tasks:
        person_tasks[pid].sort(key=lambda x: (x.get("priority") or 9999, x.get("key", "")))

    scheduled: dict[tuple, tuple[float, float]] = {}
    finish_times: dict[tuple, float] = {}
    person_cursor: dict[str, float] = defaultdict(float)

    event_q: list = []

    def enqueue_next(person_id: str, after_h: float) -> None:
        for t in person_tasks[person_id]:
            tid = (t["key"], t["bucket"])
            if tid in scheduled:
                continue
            pred = deps.get(tid)
            if pred and pred not in finish_times:
                continue  # заблокирована — ищем следующую незаблокированную
            dep_end = finish_times.get(pred, 0.0) if pred else 0.0
            earliest = max(after_h, dep_end)
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

    while event_q:
        earliest, _prio, _key, _bucket, person_id, tid = heapq.heappop(event_q)
        if tid in scheduled:
            continue
        t = task_by_id.get(tid)
        if not t:
            continue
        pred = deps.get(tid)
        if pred and pred not in finish_times:
            continue

        dep_end = finish_times.get(pred, 0.0) if pred else 0.0
        start_h = max(person_cursor[person_id], dep_end)
        end_h = start_h + max(t.get("hours") or 0.0, 0.0)

        scheduled[tid] = (start_h, end_h)
        finish_times[tid] = end_h
        person_cursor[person_id] = end_h

        enqueue_next(person_id, end_h)

        for dep_tid in dependents.get(tid, []):
            dep_t = task_by_id.get(dep_tid)
            if dep_t and dep_tid not in scheduled:
                other = dep_t["owner_id"]
                heapq.heappush(event_q, (
                    max(person_cursor[other], end_h),
                    dep_t.get("priority") or 9999,
                    dep_t.get("key", ""),
                    dep_t["bucket"],
                    other,
                    dep_tid,
                ))

    return scheduled, dict(person_cursor)


def _fill_pseudo_gaps(
    pseudo_tasks: list[dict],
    real_items: list[dict],           # уже расписанные реальные задачи с start/end_hours
    budget_hours: float,
) -> list[dict]:
    """Заполнить пробелы псевдо-задачами.

    Каждая псевдо-задача может быть разбита на несколько сегментов.
    Возвращает список сегментов (каждый — копия исходной задачи с новыми start/end_hours).
    """
    # Реальные задачи по исполнителям
    real_by_person: dict[str, list[tuple[float, float]]] = defaultdict(list)
    for item in real_items:
        real_by_person[item["owner_id"]].append(
            (item["start_hours"], item["end_hours"])
        )
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

        # Вычисляем список пробелов: [(gap_start, gap_end), ...]
        # Пробел = промежуток между реальными задачами + остаток до budget
        gaps: list[tuple[float, float]] = []
        prev_end = 0.0
        for start, end in person_real:
            if start > prev_end + 1e-9:
                gaps.append((prev_end, start))
            prev_end = max(prev_end, end)
        # Хвостовой пробел до бюджета
        if prev_end < budget_hours - 1e-9:
            gaps.append((prev_end, budget_hours))

        # Заполняем пробелы псевдо-задачами по очереди
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


# -------------------- Главная функция --------------------

def compute_gantt_schedule(
    tasks: list[dict],
    config_snapshot: dict,
    sprint_start: date,
    hours_per_day: float = 8.0,
) -> list[dict]:
    """Рассчитать расписание Ганта с разбивкой псевдо-задач по пробелам.

    Каждый элемент результата:
      start / end — ISO datetime
      start_hours / end_hours — рабочие часы от начала спринта
    """
    real_tasks = [t for t in tasks if not t.get("is_pseudo")]
    pseudo_tasks = [t for t in tasks if t.get("is_pseudo")]

    budget = float(config_snapshot.get("hours_per_person", hours_per_day * 10))

    # Шаг 1: расставляем реальные задачи
    scheduled, person_cursor = _schedule_real_tasks(real_tasks, config_snapshot, hours_per_day)

    task_by_id = {(t["key"], t["bucket"]): t for t in real_tasks}

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

    # Шаг 2: заполняем пробелы псевдо-задачами
    pseudo_items = _fill_pseudo_gaps(pseudo_tasks, real_items, budget)
    for seg in pseudo_items:
        seg["start"] = _working_hours_to_dt(sprint_start, seg["start_hours"], hours_per_day).isoformat()
        seg["end"] = _working_hours_to_dt(sprint_start, seg["end_hours"], hours_per_day).isoformat()

    all_items = real_items + pseudo_items
    all_items.sort(key=lambda x: (x["start_hours"], x.get("owner_file_name", "")))
    return all_items
