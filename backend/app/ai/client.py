"""Минимальный клиент AI-провайдеров (Anthropic Messages API, DeepSeek chat completions)
для генерации текста AI-среза.

Ключ и провайдер передаются явно (резолвятся вызывающим: конфиг → .env). Прокси/SSL
берём из тех же настроек, что и Jira/Telegram-клиенты, — окружение обычно за VPN/прокси.
"""

from __future__ import annotations

import requests

from app.core.config import settings

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"
DEEPSEEK_API_URL = "https://api.deepseek.com/chat/completions"

DEFAULT_MODELS = {
    "anthropic": "claude-sonnet-5",
    "deepseek": "deepseek-chat",
}


class AiError(Exception):
    """Ошибка генерации (нет ключа, API вернул не 2xx, сеть, пустой ответ)."""


def _proxies() -> dict[str, str]:
    proxies: dict[str, str] = {}
    if settings.http_proxy:
        proxies["http"] = settings.http_proxy
    if settings.https_proxy:
        proxies["https"] = settings.https_proxy
    return proxies


def _generate_anthropic(prompt: str, *, api_key: str, model: str, max_tokens: int) -> str:
    try:
        r = requests.post(
            ANTHROPIC_API_URL,
            headers={
                "x-api-key": api_key,
                "anthropic-version": ANTHROPIC_VERSION,
                "content-type": "application/json",
            },
            json={
                "model": model,
                "max_tokens": max_tokens,
                "messages": [{"role": "user", "content": prompt}],
            },
            proxies=_proxies() or None,
            verify=settings.requests_ca_bundle or settings.verify_ssl,
            timeout=60,
        )
    except requests.RequestException as e:
        raise AiError(f"Сеть: {e}") from e

    if r.status_code != 200:
        raise AiError(f"Anthropic API {r.status_code}: {r.text[:300]}")

    body = r.json()
    parts = [block.get("text", "") for block in body.get("content", []) if block.get("type") == "text"]
    text = "".join(parts).strip()
    if not text:
        raise AiError("Anthropic API вернул пустой ответ")
    return text


def _generate_deepseek(prompt: str, *, api_key: str, model: str, max_tokens: int) -> str:
    try:
        r = requests.post(
            DEEPSEEK_API_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "content-type": "application/json",
            },
            json={
                "model": model,
                "max_tokens": max_tokens,
                "messages": [{"role": "user", "content": prompt}],
            },
            proxies=_proxies() or None,
            verify=settings.requests_ca_bundle or settings.verify_ssl,
            timeout=60,
        )
    except requests.RequestException as e:
        raise AiError(f"Сеть: {e}") from e

    if r.status_code != 200:
        raise AiError(f"DeepSeek API {r.status_code}: {r.text[:300]}")

    body = r.json()
    choices = body.get("choices", [])
    text = (choices[0].get("message", {}).get("content", "") if choices else "").strip()
    if not text:
        raise AiError("DeepSeek API вернул пустой ответ")
    return text


def generate_text(
    prompt: str, *, api_key: str, provider: str = "anthropic", model: str | None = None, max_tokens: int = 1500,
) -> str:
    """Сгенерировать текст по промпту. provider: 'anthropic' | 'deepseek'. Бросает AiError на любую проблему."""
    if not api_key:
        raise AiError("AI не настроен: нет ключа ни на конфиге, ни в .env")

    model = model or DEFAULT_MODELS.get(provider, DEFAULT_MODELS["anthropic"])
    if provider == "deepseek":
        return _generate_deepseek(prompt, api_key=api_key, model=model, max_tokens=max_tokens)
    return _generate_anthropic(prompt, api_key=api_key, model=model, max_tokens=max_tokens)
