"""Async Marzban REST API client.

Документация Marzban: https://github.com/Gozargah/Marzban
Ключевые эндпоинты, которые мы используем:
  POST /api/admin/token       — получить access_token (form-data: username/password)
  POST /api/user              — создать пользователя
  GET  /api/user/{username}   — получить пользователя (там и subscription_url)
  PUT  /api/user/{username}   — обновить
  DELETE /api/user/{username} — удалить
  GET  /api/inbounds          — список inbound'ов
  GET  /api/system            — статус панели

Токен живёт ~24 часа. Кешируем в памяти + перезапрашиваем при 401.
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

import httpx

from app.config import settings

log = logging.getLogger(__name__)


class MarzbanError(RuntimeError):
    """Любая ошибка взаимодействия с Marzban API."""


class MarzbanClient:
    def __init__(
        self,
        base_url: str | None = None,
        username: str | None = None,
        password: str | None = None,
        timeout: float = 15.0,
    ) -> None:
        self._base = (base_url or settings.marzban_api_url).rstrip("/")
        self._user = username or settings.marzban_username
        self._pass = password or settings.marzban_password
        self._timeout = timeout
        self._token: str | None = None
        self._token_expires_at: float = 0.0
        self._lock = asyncio.Lock()

    # ---------- internals ----------

    async def _ensure_token(self, force: bool = False) -> str:
        async with self._lock:
            now = time.time()
            if not force and self._token and now < self._token_expires_at - 30:
                return self._token
            log.info("Marzban: requesting new access token")
            async with httpx.AsyncClient(timeout=self._timeout) as c:
                r = await c.post(
                    f"{self._base}/api/admin/token",
                    data={"username": self._user, "password": self._pass},
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                )
            if r.status_code != 200:
                raise MarzbanError(f"auth failed: {r.status_code} {r.text}")
            payload = r.json()
            self._token = payload["access_token"]
            ttl = settings.marzban_token_ttl_min * 60
            self._token_expires_at = now + ttl
            return self._token

    async def _request(
        self, method: str, path: str, *, retry_auth: bool = True, **kwargs: Any
    ) -> httpx.Response:
        token = await self._ensure_token()
        headers = kwargs.pop("headers", {}) or {}
        headers["Authorization"] = f"Bearer {token}"
        url = f"{self._base}{path}"
        async with httpx.AsyncClient(timeout=self._timeout) as c:
            r = await c.request(method, url, headers=headers, **kwargs)
        if r.status_code == 401 and retry_auth:
            log.warning("Marzban: 401, refreshing token and retrying")
            await self._ensure_token(force=True)
            return await self._request(method, path, retry_auth=False, **kwargs)
        return r

    # ---------- public API ----------

    async def health(self) -> bool:
        try:
            r = await self._request("GET", "/api/system")
            return r.status_code == 200
        except Exception as e:  # noqa: BLE001
            log.warning("Marzban health failed: %s", e)
            return False

    async def get_inbounds(self) -> dict[str, Any]:
        r = await self._request("GET", "/api/inbounds")
        if r.status_code != 200:
            raise MarzbanError(f"get_inbounds: {r.status_code} {r.text}")
        return r.json()

    async def get_user(self, username: str) -> dict[str, Any] | None:
        r = await self._request("GET", f"/api/user/{username}")
        if r.status_code == 404:
            return None
        if r.status_code != 200:
            raise MarzbanError(f"get_user: {r.status_code} {r.text}")
        return r.json()

    async def create_user(
        self,
        username: str,
        *,
        proxies: dict[str, dict[str, Any]] | None = None,
        inbounds: dict[str, list[str]] | None = None,
        expire: int | None = None,
        data_limit: int = 0,
        data_limit_reset_strategy: str = "no_reset",
        status: str = "active",
        note: str = "",
    ) -> dict[str, Any]:
        """Create Marzban user. Returns user payload (incl. subscription_url)."""
        body: dict[str, Any] = {
            "username": username,
            "proxies": proxies or {"vless": {"flow": "xtls-rprx-vision"}},
            "inbounds": inbounds or {"vless": ["VLESS Reality"]},
            "expire": expire,
            "data_limit": data_limit,
            "data_limit_reset_strategy": data_limit_reset_strategy,
            "status": status,
            "note": note,
        }
        r = await self._request("POST", "/api/user", json=body)
        if r.status_code in (200, 201):
            return r.json()
        if r.status_code == 409:
            existing = await self.get_user(username)
            if existing is not None:
                return existing
        raise MarzbanError(f"create_user: {r.status_code} {r.text}")

    async def update_user(self, username: str, patch: dict[str, Any]) -> dict[str, Any]:
        r = await self._request("PUT", f"/api/user/{username}", json=patch)
        if r.status_code != 200:
            raise MarzbanError(f"update_user: {r.status_code} {r.text}")
        return r.json()

    async def set_status(self, username: str, status: str) -> dict[str, Any]:
        return await self.update_user(username, {"status": status})

    async def delete_user(self, username: str) -> bool:
        r = await self._request("DELETE", f"/api/user/{username}")
        if r.status_code in (200, 204):
            return True
        if r.status_code == 404:
            return False
        raise MarzbanError(f"delete_user: {r.status_code} {r.text}")

    # ---------- core (Xray) config ----------

    async def get_core_config(self) -> dict[str, Any]:
        r = await self._request("GET", "/api/core/config")
        if r.status_code != 200:
            raise MarzbanError(f"get_core_config: {r.status_code} {r.text}")
        return r.json()

    async def put_core_config(self, config: dict[str, Any]) -> dict[str, Any]:
        r = await self._request("PUT", "/api/core/config", json=config)
        if r.status_code != 200:
            raise MarzbanError(f"put_core_config: {r.status_code} {r.text}")
        return r.json()

    async def restart_core(self) -> bool:
        r = await self._request("POST", "/api/core/restart")
        if r.status_code in (200, 204):
            return True
        raise MarzbanError(f"restart_core: {r.status_code} {r.text}")


# Singleton — создаём лениво, чтобы тесты могли подменять
_client: MarzbanClient | None = None


def get_marzban() -> MarzbanClient:
    global _client
    if _client is None:
        _client = MarzbanClient()
    return _client
