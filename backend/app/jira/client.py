"""Клиент Jira: тонкая обёртка над requests с обработкой прокси/VPN/SSL.

Никакой бизнес-логики — только HTTP. Бизнес сидит в app/sprint/.

Подключение per-конфиг: у каждого Config может быть свой Jira base_url/email/
api_token (см. db.models.Config), иначе используется .env (app.core.config.settings).
Модуль экспортирует `client` — proxy-объект, который на каждый вызов берёт
реальный JiraClient из contextvar текущего запроса (см. bind_client_for_request).
Так весь существующий код (`from app.jira.client import client; client.get(...)`)
продолжает работать без изменений, но теперь видит креды нужного конфига, а не
один глобальный синглтон на всё приложение.
"""

import contextvars
from base64 import b64encode
from typing import TYPE_CHECKING

import requests

from app.core.config import settings

if TYPE_CHECKING:
    from app.db.models import Config


class JiraError(Exception):
    """Любая проблема с Jira (auth, network, HTTP-ошибка)."""


class JiraClient:
    def __init__(
        self,
        base_url: str | None = None,
        email: str | None = None,
        api_token: str | None = None,
    ):
        self.base_url = (base_url or settings.jira_base_url).rstrip("/")
        auth = b64encode(
            f"{email or settings.jira_email}:{api_token or settings.jira_api_token}".encode()
        ).decode()
        self.headers = {
            "Authorization": f"Basic {auth}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

        self.proxies = {}
        if settings.http_proxy:
            self.proxies["http"] = settings.http_proxy
        if settings.https_proxy:
            self.proxies["https"] = settings.https_proxy

        self.verify = settings.requests_ca_bundle or settings.verify_ssl

    def _request(self, method: str, url: str, **kwargs) -> requests.Response:
        """Единая точка HTTP-запросов с обработкой сетевых ошибок."""
        try:
            return requests.request(
                method, url,
                headers=self.headers,
                proxies=self.proxies or None,
                verify=self.verify,
                timeout=60,
                **kwargs,
            )
        except requests.exceptions.ProxyError as e:
            raise JiraError(f"Прокси не отвечает: {e}") from e
        except requests.exceptions.SSLError as e:
            raise JiraError(f"SSL-ошибка: {e}") from e
        except requests.exceptions.ConnectionError as e:
            raise JiraError(f"Нет связи с Jira (VPN включён?): {e}") from e
        except requests.exceptions.Timeout:
            raise JiraError(f"Таймаут запроса к Jira: {url}")

    def _check(self, r: requests.Response, url: str) -> requests.Response:
        if r.status_code >= 400:
            raise JiraError(f"HTTP {r.status_code} от {url}: {r.text[:300]}")
        return r

    def get(self, path: str, params: dict | None = None) -> dict:
        url = f"{self.base_url}{path}"
        return self._check(self._request("GET", url, params=params), url).json()

    def post(self, path: str, json: dict) -> dict | None:
        url = f"{self.base_url}{path}"
        r = self._check(self._request("POST", url, json=json), url)
        return r.json() if r.content else None

    def put(self, path: str, json: dict) -> dict | None:
        url = f"{self.base_url}{path}"
        r = self._check(self._request("PUT", url, json=json), url)
        return r.json() if r.content else None


# -------------------- Контекст текущего запроса --------------------

_current: contextvars.ContextVar["JiraClient | None"] = contextvars.ContextVar(
    "jira_client", default=None,
)


class _ProxyClient:
    """Делегирует вызовы JiraClient'у, привязанному к текущему запросу."""

    @property
    def _real(self) -> JiraClient:
        c = _current.get()
        if c is None:
            raise JiraError("Jira-клиент не инициализирован для этого запроса")
        return c

    @property
    def base_url(self) -> str:
        return self._real.base_url

    def get(self, *a, **kw):
        return self._real.get(*a, **kw)

    def post(self, *a, **kw):
        return self._real.post(*a, **kw)

    def put(self, *a, **kw):
        return self._real.put(*a, **kw)


client = _ProxyClient()


def client_for_config(cfg: "Config") -> JiraClient:
    """JiraClient с кредами конфига, если все три поля заданы, иначе — из .env."""
    if cfg.jira_base_url and cfg.jira_email and cfg.jira_api_token_enc:
        from app.core.security import decrypt_secret
        token = decrypt_secret(cfg.jira_api_token_enc)
        if token:
            return JiraClient(base_url=cfg.jira_base_url, email=cfg.jira_email, api_token=token)
    return JiraClient()


def bind_client_for_request(cfg: "Config") -> contextvars.Token:
    return _current.set(client_for_config(cfg))


def reset_client(token: contextvars.Token) -> None:
    _current.reset(token)
