from __future__ import annotations

import logging
from typing import Any

import httpx

from lemur_shop.config import settings

log = logging.getLogger(__name__)


class LolzApiError(Exception):
    def __init__(self, status: int, msg: str):
        super().__init__(f"{status}: {msg}")
        self.status = status


class LolzClient:
    """Async-клієнт Lolzteam Market API для бота."""

    def __init__(self) -> None:
        self._base = settings.LOLZ_API_BASE_URL.rstrip("/")
        self._headers = {
            "Authorization": f"Bearer {settings.LOLZ_API_TOKEN}",
            "Accept": "application/json",
        }

    async def _get(self, path: str, params: dict | None = None) -> dict[str, Any]:
        async with httpx.AsyncClient(headers=self._headers, timeout=15) as c:
            r = await c.get(f"{self._base}/{path.lstrip('/')}", params=params)
        if r.status_code >= 400:
            raise LolzApiError(r.status_code, r.text[:200])
        return r.json()

    async def _post(self, path: str, json: dict | None = None, timeout: int = 60) -> dict[str, Any]:
        async with httpx.AsyncClient(headers=self._headers, timeout=timeout) as c:
            r = await c.post(f"{self._base}/{path.lstrip('/')}", json=json or {})
        if r.status_code >= 400:
            raise LolzApiError(r.status_code, r.text[:200])
        return r.json()

    async def search_telegram(self, country: str, pmax: float = 2.0, count: int = 10) -> list[dict]:
        """Пошук TG-акаунтів за країною. Повертає список item-об'єктів."""
        params: dict[str, Any] = {
            "origin[]":     ["autoreg", "self_registration"],
            "country[]":    [country.upper()],
            "password":     "no",
            "email":        "no",
            "spam":         "no",
            "pmax":         pmax,
            "order_by":     "price_to_up",
            "count":        count,
        }
        data = await self._get("telegram", params)
        return data.get("items") or []

    async def get_item(self, item_id: int) -> dict[str, Any]:
        data = await self._get(str(item_id))
        return data.get("item") or data

    async def fast_buy(self, item_id: int, price: float) -> dict[str, Any]:
        """Купити акаунт. Повертає item з даними після покупки."""
        data = await self._post(f"{item_id}/fast-buy", {"price": price})
        return data.get("item") or data

    async def get_telegram_code(self, item_id: int) -> str:
        """Отримати код для входу в Telegram-акаунт."""
        data = await self._get(f"{item_id}/telegram-login-code")
        log.info("telegram-login-code response for #%s: %s", item_id, data)
        code = (
            data.get("telegramLoginCode")
            or data.get("telegram_login_code")
            or data.get("code")
            or ""
        )
        return str(code).strip()


lolz = LolzClient()
