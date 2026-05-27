from __future__ import annotations

import httpx
import logging

from lemur_shop.config import settings

log = logging.getLogger(__name__)

SMM_API_URL = "https://smmway.ru/api/v2"

# Каталог SMM послуг
SMM_SERVICES: dict[str, dict] = {
    "tg_subscribers": {
        "service_id": 6322,
        "title":      "Підписники Telegram",
        "flag":       "📱",
        "description": "Реальні підписники, гарантія 365 днів",
        "price_per_100_stars": 10,
        "min": 100,
        "max": 10000,
        "step": 100,
    },
}


class SmmApiError(Exception):
    pass


async def smm_request(action: str, **params) -> dict:
    data = {"key": settings.SMMWAY_API_KEY, "action": action, **params}
    async with httpx.AsyncClient(timeout=20) as c:
        r = await c.post(SMM_API_URL, data=data)
    result = r.json()
    if "error" in result:
        raise SmmApiError(result["error"])
    return result


async def place_order(service_id: int, link: str, quantity: int) -> int:
    result = await smm_request("add", service=service_id, link=link, quantity=quantity)
    return int(result["order"])


async def get_order_status(order_id: int) -> dict:
    return await smm_request("status", order=order_id)


async def get_balance() -> float:
    result = await smm_request("balance")
    return float(result.get("balance", 0))
