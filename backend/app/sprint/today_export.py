"""Выгрузка «задачи на сегодня» по готовому Гант-расписанию.

Порт фронтового TodayExportModal: отбираем бары, активные в указанный день,
группируем по направлению и собираем текст. Используется Telegram-дайджестом.
Логика не зависит от БД/Jira — на вход список GanttItem-словарей.
"""

from __future__ import annotations

from collections import OrderedDict
from datetime import date

NO_DIRECTION_LABEL = "Без направления"


def _is_active_today(item: dict, today: str) -> bool:
    if item.get("is_pseudo"):
        return False
    start_day = (item.get("start") or "")[:10]
    end_day = (item.get("end") or "")[:10]
    return bool(start_day) and start_day <= today <= end_day


def filter_today(items: list[dict], today: date) -> list[dict]:
    """Бары, активные в день today (без псевдо-задач/отпусков)."""
    today_iso = today.isoformat()
    return [it for it in items if _is_active_today(it, today_iso)]


def _group_by_direction(items: list[dict]) -> "OrderedDict[str, list[dict]]":
    groups: "OrderedDict[str, list[dict]]" = OrderedDict()
    for it in items:
        key = it.get("direction") or NO_DIRECTION_LABEL
        groups.setdefault(key, []).append(it)
    return groups


def _date_label(today: date) -> str:
    return f"Задачи на {today.strftime('%d.%m.%Y')}"


def _escape_html(s: str) -> str:
    return (
        (s or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def build_html(items: list[dict], today: date) -> str:
    """HTML для Telegram (parse_mode=HTML): жирные направления + ссылки на задачи.

    Telegram-HTML поддерживает только <b>, <a>, <i> и переносы через \n —
    div/&nbsp; недопустимы, поэтому строим построчно.
    """
    groups = _group_by_direction(items)
    lines = [f"<b>{_escape_html(_date_label(today))}</b>"]
    for direction, group in groups.items():
        lines.append("")
        lines.append(f"<b>{_escape_html(direction)}:</b>")
        for it in group:
            key = _escape_html(it.get("key", ""))
            url = it.get("url") or ""
            summary = _escape_html(it.get("summary", ""))
            owner = _escape_html(it.get("owner_file_name", ""))
            bucket = _escape_html(it.get("bucket", ""))
            link = f'<a href="{_escape_html(url)}">{key}</a>' if url else key
            lines.append(f"• {link} ({summary}) — {owner} — {bucket}")
    return "\n".join(lines)


def build_plain_text(items: list[dict], today: date) -> str:
    groups = _group_by_direction(items)
    lines = [_date_label(today)]
    for direction, group in groups.items():
        lines.append("")
        lines.append(f"{direction}:")
        for it in group:
            lines.append(
                f"- {it.get('key', '')} ({it.get('summary', '')}) — "
                f"{it.get('owner_file_name', '')} — {it.get('bucket', '')}"
            )
    return "\n".join(lines)
