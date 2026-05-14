"""Сборка xlsx-файла из готового списка задач (фаза 2).

Изменения относительно фазы 1:
- Колонка "Роль" между "Консультант" и "Фаза".
- Псевдо-задачи (is_pseudo=True): отображаются без гиперссылки,
  ключ помечается как "(псевдо)".
- Бакет может быть новый: "Дизайн", "Дизайн-ревью", "Разработка", "Код-ревью",
  "Руководство", "Отсутствие". Раскрашиваем их.
"""

from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter


def _style_header(cell):
    cell.font = Font(bold=True, color="FFFFFF")
    cell.fill = PatternFill("solid", fgColor="4472C4")
    cell.alignment = Alignment(horizontal="center", vertical="center")


_BUCKET_COLORS = {
    "Тестирование":   "DEEBF7",  # светло-голубой
    "Анализ":         "FFF2CC",  # светло-жёлтый
    "Дизайн":         "F4CCCC",  # розоватый
    "Дизайн-ревью":   "E06666",  # тёмно-розовый
    "Разработка":     "D9EAD3",  # светло-зелёный
    "Код-ревью":      "B6D7A8",  # зеленее
    "Руководство":    "EAD1DC",  # сиреневый
    "Отсутствие":     "CCCCCC",  # серый
}


def _bucket_fill(bucket: str) -> PatternFill | None:
    color = _BUCKET_COLORS.get(bucket)
    return PatternFill("solid", fgColor=color) if color else None


def build_sprint_xlsx(allocated: list[dict], owner_stats: list[dict],
                      max_sprint_num: int | None,
                      closed_tasks: list[dict | None] | None = None,
                      terminal_statuses: list[str] | None = None) -> bytes:
    """Сборка xlsx спринта. Для closed-спринтов передаём closed_tasks и terminal_statuses,
    тогда добавятся вкладки "Закрытие" и "Статистика закрытия".
    """
    wb = Workbook()
    ws = wb.active
    ws.title = "Спринт"

    headers = [
        "№", "Задача", "Название", "Консультант", "Роль",
        "Фаза", "Статус Jira", "Оценка, ч",
        "Спринт", "Источник", "Комментарий",
    ]
    for col_idx, h in enumerate(headers, start=1):
        _style_header(ws.cell(row=1, column=col_idx, value=h))
    ws.freeze_panes = "A2"

    for row_idx, task in enumerate(allocated, start=2):
        ws.cell(row=row_idx, column=1, value=task.get("priority"))

        # B — задача
        is_pseudo = task.get("is_pseudo", False)
        if is_pseudo:
            cell_key = ws.cell(row=row_idx, column=2, value="(псевдо)")
            cell_key.font = Font(color="888888", italic=True)
        else:
            cell_key = ws.cell(row=row_idx, column=2, value=task["key"])
            if task.get("url"):
                cell_key.hyperlink = task["url"]
                cell_key.font = Font(color="0563C1", underline="single")

        ws.cell(row=row_idx, column=3, value=task["summary"])
        ws.cell(row=row_idx, column=4, value=task["owner_file_name"])
        ws.cell(row=row_idx, column=5, value=task.get("role", "")
                if not is_pseudo else "—")

        # F — фаза с заливкой
        bucket = task["bucket"]
        cell_bucket = ws.cell(row=row_idx, column=6, value=bucket)
        fill = _bucket_fill(bucket)
        if fill:
            cell_bucket.fill = fill

        ws.cell(row=row_idx, column=7, value=task["status_name"] or ("" if is_pseudo else ""))
        ws.cell(row=row_idx, column=8, value=task["hours"])
        ws.cell(row=row_idx, column=9, value=task.get("sprint_name") or "")
        ws.cell(row=row_idx, column=10, value=task["board"])

        # Комментарий
        notes = []
        if task.get("partial_from"):
            notes.append(
                f"переходящая, всего {task['partial_from']}ч, "
                f"в этом спринте {task['hours']}ч"
            )
        if notes:
            ws.cell(row=row_idx, column=11, value="; ".join(notes))

    widths = {1: 5, 2: 12, 3: 60, 4: 16, 5: 14, 6: 14, 7: 18, 8: 9, 9: 18, 10: 24, 11: 40}
    for idx, w in widths.items():
        ws.column_dimensions[get_column_letter(idx)].width = w

    # Сводка
    ws_sum = wb.create_sheet("Сводка")
    if max_sprint_num is not None:
        ws_sum.cell(row=1, column=1, value=f"Спринт SHN Sprint {max_sprint_num}").font = Font(
            bold=True, size=14
        )

    sum_row = 3
    headers2 = ["Аналитик", "Занято, ч", "Бюджет, ч", "Доля"]
    for col_idx, h in enumerate(headers2, start=1):
        _style_header(ws_sum.cell(row=sum_row, column=col_idx, value=h))

    for i, st in enumerate(owner_stats, start=sum_row + 1):
        ws_sum.cell(row=i, column=1, value=st["file_name"])
        ws_sum.cell(row=i, column=2, value=st["used_hours"])
        ws_sum.cell(row=i, column=3, value=st["budget"])
        ws_sum.cell(row=i, column=4, value=f"=B{i}/C{i}")
        ws_sum.cell(row=i, column=4).number_format = "0%"

    for idx, w in {1: 18, 2: 12, 3: 12, 4: 8}.items():
        ws_sum.column_dimensions[get_column_letter(idx)].width = w

    # Вкладки закрытия (только если переданы closed_tasks)
    if closed_tasks is not None:
        _add_closure_sheets(wb, allocated, closed_tasks, terminal_statuses or [])

    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _add_closure_sheets(wb, allocated: list[dict],
                         closed_tasks: list[dict | None],
                         terminal_statuses: list[str]) -> None:
    """Добавить вкладки 'Закрытие' и 'Статистика закрытия' в книгу."""
    terminal_set = set(terminal_statuses)

    def is_done(task: dict, closed: dict | None) -> bool:
        if task.get("is_pseudo"):
            return True
        if not closed:
            return False
        return closed.get("status_name") in terminal_set

    # Вкладка "Закрытие"
    ws = wb.create_sheet("Закрытие")
    headers = [
        "✓?", "Задача", "Название", "Консультант", "Роль",
        "Было: статус", "Стало: статус", "Часы",
    ]
    for col_idx, h in enumerate(headers, start=1):
        _style_header(ws.cell(row=1, column=col_idx, value=h))
    ws.freeze_panes = "A2"

    for row_idx, (task, closed) in enumerate(zip(allocated, closed_tasks), start=2):
        done = is_done(task, closed)
        ws.cell(row=row_idx, column=1, value="✓" if done else "✗")
        # Цвет фона строки — зелёный/красный
        from openpyxl.styles import PatternFill
        fill = PatternFill("solid", fgColor="D9EAD3" if done else "F4CCCC")
        for col in range(1, 9):
            ws.cell(row=row_idx, column=col).fill = fill

        is_pseudo = task.get("is_pseudo", False)
        if is_pseudo:
            cell_key = ws.cell(row=row_idx, column=2, value="(псевдо)")
            cell_key.font = Font(color="888888", italic=True)
        else:
            cell_key = ws.cell(row=row_idx, column=2, value=task["key"])
            if task.get("url"):
                cell_key.hyperlink = task["url"]
                cell_key.font = Font(color="0563C1", underline="single")

        ws.cell(row=row_idx, column=3, value=task["summary"])
        ws.cell(row=row_idx, column=4, value=task["owner_file_name"])
        ws.cell(row=row_idx, column=5, value="—" if is_pseudo else task.get("role", ""))
        ws.cell(row=row_idx, column=6, value="—" if is_pseudo else task["status_name"])
        ws.cell(row=row_idx, column=7,
                value="—" if is_pseudo
                else (closed.get("status_name") if closed else "(нет данных)"))
        ws.cell(row=row_idx, column=8, value=task["hours"])

    widths = {1: 5, 2: 12, 3: 50, 4: 16, 5: 14, 6: 18, 7: 18, 8: 9}
    for idx, w in widths.items():
        ws.column_dimensions[get_column_letter(idx)].width = w

    # Вкладка "Статистика закрытия"
    ws_stat = wb.create_sheet("Статистика закрытия")

    total = len(allocated)
    done_count = sum(1 for t, c in zip(allocated, closed_tasks) if is_done(t, c))
    total_hours = sum(t["hours"] for t in allocated)
    done_hours = sum(t["hours"] for t, c in zip(allocated, closed_tasks) if is_done(t, c))

    ws_stat.cell(row=1, column=1, value="Общие метрики").font = Font(bold=True, size=14)
    ws_stat.cell(row=2, column=1, value="Задач выполнено")
    ws_stat.cell(row=2, column=2, value=f"{done_count} из {total}")
    ws_stat.cell(row=2, column=3, value=done_count / total if total else 0)
    ws_stat.cell(row=2, column=3).number_format = "0%"
    ws_stat.cell(row=3, column=1, value="Часов выполнено")
    ws_stat.cell(row=3, column=2, value=f"{round(done_hours, 1)} из {round(total_hours, 1)} ч")
    ws_stat.cell(row=3, column=3, value=done_hours / total_hours if total_hours else 0)
    ws_stat.cell(row=3, column=3).number_format = "0%"

    # По людям
    ws_stat.cell(row=5, column=1, value="По людям").font = Font(bold=True, size=12)

    by_owner: dict[str, dict] = {}
    for t, c in zip(allocated, closed_tasks):
        acc = t["owner_id"]
        if acc not in by_owner:
            by_owner[acc] = {"file_name": t["owner_file_name"],
                              "total": 0, "done": 0, "hours": 0.0, "done_hours": 0.0}
        s = by_owner[acc]
        s["total"] += 1
        s["hours"] += t["hours"]
        if is_done(t, c):
            s["done"] += 1
            s["done_hours"] += t["hours"]

    headers = ["Консультант", "Задач", "Часы", "% задач", "% часов"]
    for col_idx, h in enumerate(headers, start=1):
        _style_header(ws_stat.cell(row=6, column=col_idx, value=h))

    for i, s in enumerate(by_owner.values(), start=7):
        ws_stat.cell(row=i, column=1, value=s["file_name"])
        ws_stat.cell(row=i, column=2, value=f"{s['done']} / {s['total']}")
        ws_stat.cell(row=i, column=3,
                     value=f"{round(s['done_hours'], 1)} / {round(s['hours'], 1)}")
        ws_stat.cell(row=i, column=4,
                     value=s["done"] / s["total"] if s["total"] else 0)
        ws_stat.cell(row=i, column=4).number_format = "0%"
        ws_stat.cell(row=i, column=5,
                     value=s["done_hours"] / s["hours"] if s["hours"] else 0)
        ws_stat.cell(row=i, column=5).number_format = "0%"

    for idx, w in {1: 22, 2: 14, 3: 18, 4: 10, 5: 10}.items():
        ws_stat.column_dimensions[get_column_letter(idx)].width = w


def build_candidates_xlsx(candidates: list[dict]) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "Кандидаты"

    headers = [
        "№", "В спринт", "Задача", "Название", "Консультант", "Роль",
        "Статус", "Фаза", "Часы",
        "Время аналитика", "Время тестировщика", "Время разработчика",
        "Исходная оценка", "Спринт", "Источник",
    ]
    for col_idx, h in enumerate(headers, start=1):
        _style_header(ws.cell(row=1, column=col_idx, value=h))
    ws.freeze_panes = "A2"

    for row_idx, t in enumerate(candidates, start=2):
        ws.cell(row=row_idx, column=1, value=t.get("priority") or "")
        ws.cell(row=row_idx, column=2, value="Формально" if t.get("formal_only") else "Да")

        is_pseudo = t.get("is_pseudo", False)
        if is_pseudo:
            cell_key = ws.cell(row=row_idx, column=3, value="(псевдо)")
            cell_key.font = Font(color="888888", italic=True)
        else:
            cell_key = ws.cell(row=row_idx, column=3, value=t["key"])
            if t.get("url"):
                cell_key.hyperlink = t["url"]
                cell_key.font = Font(color="0563C1", underline="single")

        ws.cell(row=row_idx, column=4, value=t["summary"])
        ws.cell(row=row_idx, column=5, value=t["owner_file_name"])
        ws.cell(row=row_idx, column=6, value=t.get("role", "") if not is_pseudo else "—")
        ws.cell(row=row_idx, column=7, value=t["status_name"])

        cell_bucket = ws.cell(row=row_idx, column=8, value=t["bucket"])
        fill = _bucket_fill(t["bucket"])
        if fill:
            cell_bucket.fill = fill

        ws.cell(row=row_idx, column=9, value=t["hours"])
        ws.cell(row=row_idx, column=10, value=t.get("hours_analyst"))
        ws.cell(row=row_idx, column=11, value=t.get("hours_tester"))
        ws.cell(row=row_idx, column=12, value=t.get("hours_developer"))
        ws.cell(row=row_idx, column=13, value=t.get("hours_original"))
        ws.cell(row=row_idx, column=14, value=t.get("sprint_name") or "")
        ws.cell(row=row_idx, column=15, value=t["board"])

    widths = {1: 5, 2: 11, 3: 12, 4: 60, 5: 16, 6: 14, 7: 18, 8: 14, 9: 9,
              10: 14, 11: 16, 12: 16, 13: 14, 14: 18, 15: 24}
    for idx, w in widths.items():
        ws.column_dimensions[get_column_letter(idx)].width = w

    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()
