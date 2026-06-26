"""Минимальный клиент Telegram Bot API — отправка сообщений в чат.

Токен передаётся явно (резолвится вызывающим: токен конфига → .env). Прокси/SSL
берём из тех же настроек, что и Jira-клиент, — окружение обычно за VPN/прокси.
"""

from __future__ import annotations

import requests

from app.core.config import settings


class TelegramError(Exception):
    """Ошибка отправки в Telegram (нет токена, API вернул не ok, сеть)."""


def _proxies() -> dict[str, str]:
    proxies: dict[str, str] = {}
    if settings.http_proxy:
        proxies["http"] = settings.http_proxy
    if settings.https_proxy:
        proxies["https"] = settings.https_proxy
    return proxies


def send_message(chat_id: str, text: str, *, token: str = "", parse_mode: str = "HTML") -> None:
    """Отправить сообщение. token пуст → пробуем глобальный .env. Бросает TelegramError."""
    token = token or settings.telegram_bot_token
    if not token:
        raise TelegramError("Telegram-бот не настроен: нет токена ни на конфиге, ни в .env")
    if not chat_id:
        raise TelegramError("Не указан chat_id")

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        r = requests.post(
            url,
            json={
                "chat_id": chat_id,
                "text": text,
                "parse_mode": parse_mode,
                "disable_web_page_preview": True,
            },
            proxies=_proxies() or None,
            verify=settings.requests_ca_bundle or settings.verify_ssl,
            timeout=30,
        )
    except requests.RequestException as e:
        raise TelegramError(f"Сеть: {e}") from e

    if r.status_code != 200:
        raise TelegramError(f"Telegram API {r.status_code}: {r.text[:300]}")
    body = r.json()
    if not body.get("ok"):
        raise TelegramError(f"Telegram API: {body.get('description', 'unknown error')}")
