"""Локализация сообщений backend (ошибки/валидация) — ru/en.

Язык запроса резолвится из заголовка Accept-Language (его шлёт фронт на
основе текущего выбора в переключателе). По умолчанию — ru, как и было
до введения переключателя языка.

Сообщения хранятся не централизованно, а по модулям: каждый роутер/сервис
заводит свой `_MSG: dict[str, dict[str, str]]` и получает `t = make_translator(_MSG)`.
Так правки разных роутеров не задевают один общий файл.
"""

from fastapi import Request

SUPPORTED_LANGS = ("ru", "en")
DEFAULT_LANG = "ru"


def get_lang(request: Request) -> str:
    """FastAPI-зависимость: язык текущего запроса по заголовку Accept-Language."""
    raw = (request.headers.get("accept-language") or "").lower()
    for lang in SUPPORTED_LANGS:
        if raw.startswith(lang):
            return lang
    return DEFAULT_LANG


def make_translator(messages: dict[str, dict[str, str]]):
    """Возвращает t(key, lang, **kwargs) — перевод по локальному словарю модуля."""

    def t(key: str, lang: str, **kwargs) -> str:
        entry = messages.get(key)
        if not entry:
            return key
        template = entry.get(lang) or entry.get(DEFAULT_LANG) or key
        return template.format(**kwargs) if kwargs else template

    return t
