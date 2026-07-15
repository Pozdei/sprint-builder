"""AI-срез (Спринт/Прогноз) — связный текст на естественном языке о том, что
происходит и что ожидаем к концу спринта / завершению эпика.

Бэкенд не пересчитывает Гант/аллокацию — на вход приходит уже готовый
результат со страницы (SprintBuildResponse / EpicForecastResponse), здесь он
только форматируется в промпт и передаётся LLM.
"""

from __future__ import annotations

from collections import OrderedDict
from datetime import date, datetime, timezone

from app.ai import client as ai
from app.core.config import settings
from app.core.security import decrypt_secret
from app.db import models

NO_DIRECTION_LABEL = "Без направления"
NO_BOARD_LABEL = "Без доски"

_NO_NAME_RULE = (
    "Пиши без обращения по имени — не выдумывай имя получателя и не начинай "
    "текст с приветствия."
)


class AiSummaryError(Exception):
    """AI-срез недоступен (нет ключа, ошибка генерации)."""


def resolve_provider_and_key(config: models.Config) -> tuple[str, str]:
    """Провайдер конфига + эффективный ключ: ключ конфига (расшифрованный) → глобальный .env."""
    provider = config.ai_provider or "anthropic"
    if provider == "deepseek":
        key = decrypt_secret(config.deepseek_api_key_enc) if config.deepseek_api_key_enc else settings.deepseek_api_key
        return provider, key
    key = decrypt_secret(config.anthropic_api_key_enc) if config.anthropic_api_key_enc else settings.anthropic_api_key
    return provider, key


def _group_by(items: list[dict], label_fn) -> "OrderedDict[str, list[dict]]":
    groups: "OrderedDict[str, list[dict]]" = OrderedDict()
    for it in items:
        groups.setdefault(label_fn(it), []).append(it)
    return groups


def _board_label(it: dict) -> str:
    """«Проект» для Спринта/Истории — доска Jira, из которой набрана задача."""
    return it.get("board") or NO_BOARD_LABEL


def _epic_or_story_label(it: dict) -> str:
    """«Проект» для Прогноза — история (наиболее конкретный уровень), затем эпик,
    затем направление, если задача вне иерархии эпик/история."""
    if it.get("story_key"):
        return f"{it['story_key']} «{it.get('story_summary') or ''}»".strip()
    if it.get("epic_key"):
        return f"{it['epic_key']} «{it.get('epic_summary') or ''}»".strip()
    return it.get("direction") or NO_DIRECTION_LABEL


def _build_sprint_prompt(payload: dict) -> str:
    allocated = [t for t in payload.get("allocated", []) if not t.get("is_pseudo")]
    overflow = payload.get("overflow", [])
    owner_stats = payload.get("owner_stats", [])

    lines = ["Данные текущего черновика спринта:", ""]

    lines.append(f"Задач в составе: {len(allocated)}, не влезло в бюджет (overflow): {len(overflow)}")
    lines.append("")

    lines.append("Состав по проектам (доскам) и этапам:")
    for board, items in _group_by(allocated, _board_label).items():
        lines.append(f"- {board}:")
        for it in items:
            lines.append(
                f"  - {it['key']} «{it['summary']}» — направление {it.get('direction') or '—'}, "
                f"этап {it['bucket']}, исполнитель {it['owner_file_name']}, {it['hours']:.1f} ч"
            )
    lines.append("")

    if overflow:
        lines.append("Не поместилось в бюджет спринта (overflow):")
        for it in overflow:
            lines.append(f"- {it['key']} «{it['summary']}» — {it['hours']:.1f} ч, причина: {it.get('overflow_reason') or 'нет бюджета'}")
        lines.append("")

    lines.append("Загрузка людей (использовано часов / бюджет):")
    for s in owner_stats:
        overbudget = " — ПЕРЕГРУЗ" if s["used_hours"] > s["budget"] else ""
        lines.append(f"- {s['file_name']}: {s['used_hours']:.1f} / {s['budget']:.1f} ч{overbudget}")
    lines.append("")

    lines.append(
        "На основе этих данных напиши короткий связный текст на русском языке "
        f"(без markdown-разметки, простыми абзацами) для лида команды. {_NO_NAME_RULE} "
        "Опирайся в первую очередь на проекты (доски) как основную структуру "
        "рассказа; спускайся до конкретных задач по ключу только там, где это "
        "действительно важно (риски, перегруз, крупные или не поместившиеся "
        "задачи) — не обязательно перечислять каждую задачу. Расскажи, что "
        "сейчас в работе по проектам, какие есть риски (перегруз/недогруз "
        "людей, задачи, не поместившиеся в спринт), и что реалистично ожидать "
        "к концу спринта. Будь конкретен, опирайся только на приведённые данные."
    )
    return "\n".join(lines)


def _build_forecast_prompt(payload: dict) -> str:
    gantt_items = [it for it in payload.get("gantt_items", []) if not it.get("is_pseudo")]
    stats = payload.get("stats", {})
    warnings = payload.get("warnings", [])
    missing_assignees = payload.get("missing_assignees", [])
    completion_date = payload.get("completion_date")
    epic_key = payload.get("epic_key", "")
    epic_summary = payload.get("epic_summary", "")
    today = date.today().isoformat()

    lines = [f"Прогноз реализации «{epic_key} {epic_summary}» на {today}:", ""]

    if stats:
        lines.append(
            f"Всего задач: {stats.get('total_issues', '?')}, "
            f"готово: {stats.get('done_issues', '?')}, "
            f"осталось этапов: {stats.get('remaining_work_items', '?')}"
        )
    if completion_date:
        lines.append(f"Прогнозная дата завершения: {completion_date}")
    lines.append("")

    lines.append("Оставшиеся этапы по проектам (эпикам/историям):")
    for project, items in _group_by(gantt_items, _epic_or_story_label).items():
        lines.append(f"- {project}:")
        for it in items:
            status = " (историческая фаза, уже пройдена)" if it.get("is_historical") else ""
            lines.append(
                f"  - {it['key']} «{it['summary']}» — направление {it.get('direction') or '—'}, "
                f"этап {it['bucket']}, исполнитель {it['owner_file_name']}, до {it['end'][:10]}{status}"
            )
    lines.append("")

    if warnings:
        lines.append("Предупреждения:")
        for w in warnings:
            lines.append(f"- {w}")
        lines.append("")

    if missing_assignees:
        lines.append(f"Задачи без назначенных исполнителей: {len(missing_assignees)}")
        for m in missing_assignees[:20]:
            lines.append(f"- {m.get('key')} «{m.get('summary')}» — не хватает: {', '.join(m.get('missing', []))}")
        lines.append("")

    lines.append(
        "На основе этих данных напиши короткий связный текст на русском языке "
        f"(без markdown-разметки, простыми абзацами) для лида команды. {_NO_NAME_RULE} "
        "Опирайся в первую очередь на проекты (эпики/истории) как основную "
        "структуру рассказа; спускайся до конкретных задач по ключу только там, "
        "где это действительно важно (риски, узкие места, просроченные "
        "исполнители) — не обязательно перечислять каждую задачу. Расскажи "
        "текущий прогресс по проектам, узкие места/риски (просроченные "
        "исполнители, предупреждения), и что реалистично ожидать по срокам "
        "завершения. Будь конкретен, опирайся только на приведённые данные."
    )
    return "\n".join(lines)


def generate_summary(config: models.Config, mode: str, payload: dict) -> str:
    """mode: 'sprint' | 'forecast'. Бросает AiSummaryError, если ключ не настроен."""
    provider, api_key = resolve_provider_and_key(config)
    if not api_key:
        raise AiSummaryError(f"AI не настроен: нет ключа {provider} ни на конфиге, ни в .env")

    prompt = _build_sprint_prompt(payload) if mode == "sprint" else _build_forecast_prompt(payload)

    try:
        return ai.generate_text(prompt, api_key=api_key, provider=provider)
    except ai.AiError as e:
        raise AiSummaryError(str(e)) from e


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
