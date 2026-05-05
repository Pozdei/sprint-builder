"""Сборка xlsx-файла из готового списка задач.

Не содержит логики формирования спринта — только превращение списков в Excel.
В отличие от старого build_sprint.py, не использует внешний шаблон —
все стили и формулы создаются с нуля. Это надёжнее для веб-приложения:
один файл меньше, нет привязки к диску.
"""

from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter


def _style_header(cell):
    cell.font = Font(bold=True, color="FFFFFF")
    cell.fill = PatternFill("solid", fgColor="4472C4")
    cell.alignment = Alignment(horizontal="center", vertical="center")


def _bucket_fill(bucket: str) -> PatternFill | None:
    if bucket == "Тестирование":
        return PatternFill("solid", fgColor="DEEBF7")  # светло-голубой
    if bucket == "Анализ":
        return PatternFill("solid", fgColor="FFF2CC")  # светло-жёлтый
    return None


def build_sprint_xlsx(allocated: list[dict], owner_stats: list[dict],
                      max_sprint_num: int | None) -> bytes:
    """Формирует xlsx-файл со спринтом.

    allocated:    список задач из allocate()
    owner_stats:  список dict {file_name, used_hours, budget}
    max_sprint_num: номер для подписи в шапке
    """
    wb = Workbook()
    ws_sprint = wb.active
    ws_sprint.title = "Спринт"

    # ---------- Заголовок (строка 1) ----------
    headers = [
        "№",            # priority
        "Задача",       # ссылка
        "Название",
        "Консультант",
        "Фаза",         # бакет (Анализ/Тестирование)
        "Статус Jira",
        "Оценка, ч",
        "Спринт",
        "Источник",
        "Комментарий",
    ]
    for col_idx, h in enumerate(headers, start=1):
        cell = ws_sprint.cell(row=1, column=col_idx, value=h)
        _style_header(cell)
    ws_sprint.freeze_panes = "A2"

    # ---------- Данные ----------
    # allocated приходит уже в нужном порядке (по людям → приоритет)
    for row_idx, task in enumerate(allocated, start=2):
        # Колонка A — номер приоритета
        ws_sprint.cell(row=row_idx, column=1, value=task.get("priority"))

        # Колонка B — ключ задачи как гиперссылка
        cell_key = ws_sprint.cell(row=row_idx, column=2, value=task["key"])
        cell_key.hyperlink = task["url"]
        cell_key.font = Font(color="0563C1", underline="single")

        ws_sprint.cell(row=row_idx, column=3, value=task["summary"])
        ws_sprint.cell(row=row_idx, column=4, value=task["owner_file_name"])

        # Колонка E — фаза с цветной заливкой
        bucket = task["bucket"]
        cell_bucket = ws_sprint.cell(row=row_idx, column=5, value=bucket)
        fill = _bucket_fill(bucket)
        if fill:
            cell_bucket.fill = fill

        ws_sprint.cell(row=row_idx, column=6, value=task["status_name"])
        ws_sprint.cell(row=row_idx, column=7, value=task["hours"])
        ws_sprint.cell(row=row_idx, column=8, value=task.get("sprint_name") or "")
        ws_sprint.cell(row=row_idx, column=9, value=task["board"])

        # Колонка J — комментарий: пометки про переходящие задачи
        notes = []
        if task.get("partial_from"):
            notes.append(
                f"переходящая, всего {task['partial_from']}ч, "
                f"в этом спринте {task['hours']}ч"
            )
        if notes:
            ws_sprint.cell(row=row_idx, column=10, value="; ".join(notes))

    # ---------- Ширины колонок ----------
    widths = {1: 5, 2: 12, 3: 60, 4: 16, 5: 14, 6: 18, 7: 9, 8: 18, 9: 24, 10: 40}
    for idx, w in widths.items():
        ws_sprint.column_dimensions[get_column_letter(idx)].width = w

    # ---------- Лист "Сводка" ----------
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
        # Excel посчитает сам через формулу, чтобы пользователь мог менять часы
        ws_sum.cell(row=i, column=4, value=f"=B{i}/C{i}")
        ws_sum.cell(row=i, column=4).number_format = "0%"

    for idx, w in {1: 18, 2: 12, 3: 12, 4: 8}.items():
        ws_sum.column_dimensions[get_column_letter(idx)].width = w

    # ---------- Сохранение в память ----------
    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()


def build_candidates_xlsx(candidates: list[dict]) -> bytes:
    """xlsx со всеми кандидатами (включая formal_only)."""
    wb = Workbook()
    ws = wb.active
    ws.title = "Кандидаты"

    headers = [
        "№", "В спринт", "Задача", "Название", "Консультант",
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
        cell_key = ws.cell(row=row_idx, column=3, value=t["key"])
        cell_key.hyperlink = t["url"]
        cell_key.font = Font(color="0563C1", underline="single")
        ws.cell(row=row_idx, column=4, value=t["summary"])
        ws.cell(row=row_idx, column=5, value=t["owner_file_name"])
        ws.cell(row=row_idx, column=6, value=t["status_name"])

        cell_bucket = ws.cell(row=row_idx, column=7, value=t["bucket"])
        fill = _bucket_fill(t["bucket"])
        if fill:
            cell_bucket.fill = fill

        ws.cell(row=row_idx, column=8, value=t["hours"])
        ws.cell(row=row_idx, column=9, value=t.get("hours_analyst"))
        ws.cell(row=row_idx, column=10, value=t.get("hours_tester"))
        ws.cell(row=row_idx, column=11, value=t.get("hours_developer"))
        ws.cell(row=row_idx, column=12, value=t.get("hours_original"))
        ws.cell(row=row_idx, column=13, value=t.get("sprint_name") or "")
        ws.cell(row=row_idx, column=14, value=t["board"])

    widths = {1: 5, 2: 11, 3: 12, 4: 60, 5: 16, 6: 18, 7: 14, 8: 9,
              9: 14, 10: 16, 11: 16, 12: 14, 13: 18, 14: 24}
    for idx, w in widths.items():
        ws.column_dimensions[get_column_letter(idx)].width = w

    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()
