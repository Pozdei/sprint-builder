"""Клиент Jira: тонкая обёртка над requests с обработкой прокси/VPN/SSL.

Никакой бизнес-логики — только HTTP. Бизнес сидит в app/sprint/.
"""

from base64 import b64encode

import requests

from app.core.config import settings


class JiraError(Exception):
    """Любая проблема с Jira (auth, network, HTTP-ошибка)."""


class JiraClient:
    def __init__(self):
        self.base_url = settings.jira_base_url.rstrip("/")
        auth = b64encode(f"{settings.jira_email}:{settings.jira_api_token}".encode()).decode()
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


# Один общий клиент на приложение — переиспользуется в эндпоинтах
client = JiraClient()
