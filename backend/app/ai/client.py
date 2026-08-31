"""Минимальный клиент AI-провайдеров (Anthropic Messages API, DeepSeek и "local" —
любой OpenAI-совместимый chat-completions эндпоинт) для генерации текста AI-среза.

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
    "local": settings.ai_local_model,
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


def _generate_openai_style(
    prompt: str, *, url: str, headers: dict[str, str], model: str, max_tokens: int, error_prefix: str,
    extra_body: dict | None = None,
) -> str:
    """Общий вызов для любого chat-completions эндпоинта в формате OpenAI (DeepSeek, local)."""
    try:
        r = requests.post(
            url,
            headers={**headers, "content-type": "application/json"},
            json={
                "model": model,
                "max_tokens": max_tokens,
                "messages": [{"role": "user", "content": prompt}],
                **(extra_body or {}),
            },
            proxies=_proxies() or None,
            verify=settings.requests_ca_bundle or settings.verify_ssl,
            timeout=60,
        )
    except requests.RequestException as e:
        raise AiError(f"Сеть: {e}") from e

    if r.status_code != 200:
        raise AiError(f"{error_prefix} {r.status_code}: {r.text[:300]}")

    body = r.json()
    choices = body.get("choices", [])
    text = (choices[0].get("message", {}).get("content", "") if choices else "").strip()
    if not text:
        raise AiError(f"{error_prefix} вернул пустой ответ")
    return text


def _generate_deepseek(prompt: str, *, api_key: str, model: str, max_tokens: int) -> str:
    return _generate_openai_style(
        prompt,
        url=DEEPSEEK_API_URL,
        headers={"Authorization": f"Bearer {api_key}"},
        model=model,
        max_tokens=max_tokens,
        error_prefix="DeepSeek API",
    )


def _generate_local(prompt: str, *, base_url: str, api_key: str, model: str, max_tokens: int) -> str:
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    return _generate_openai_style(
        prompt,
        url=base_url.rstrip("/") + "/chat/completions",
        headers=headers,
        model=model,
        max_tokens=max_tokens,
        error_prefix="Local LLM API",
        # Локальные reasoning-модели (Qwen3 и т.п.) по умолчанию думают вслух и тратят
        # max_tokens на reasoning_content раньше content — на длинных промптах AI-среза
        # это оставляет пустой content. vLLM/sglang понимают этот флаг для отключения thinking.
        extra_body={"chat_template_kwargs": {"enable_thinking": False}},
    )


def generate_text(
    prompt: str, *, api_key: str, provider: str = "anthropic", model: str | None = None, max_tokens: int = 1500,
) -> str:
    """Сгенерировать текст по промпту. provider: 'anthropic' | 'deepseek' | 'local'.
    Бросает AiError на любую проблему."""
    model = model or DEFAULT_MODELS.get(provider, DEFAULT_MODELS["anthropic"])

    if provider == "local":
        if not settings.ai_local_base_url:
            raise AiError("AI не настроен: не задан AI_LOCAL_BASE_URL в .env")
        return _generate_local(
            prompt, base_url=settings.ai_local_base_url, api_key=api_key, model=model, max_tokens=max_tokens,
        )

    if not api_key:
        raise AiError("AI не настроен: нет ключа ни на конфиге, ни в .env")
    if provider == "deepseek":
        return _generate_deepseek(prompt, api_key=api_key, model=model, max_tokens=max_tokens)
    return _generate_anthropic(prompt, api_key=api_key, model=model, max_tokens=max_tokens)
