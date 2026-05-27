from __future__ import annotations

import re
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
        "min": 10,
        "max": 10000,
        "step": 1,
    },
}


class SmmApiError(Exception):
    pass


def normalize_tg_link(link: str) -> str:
    """Convert https://t.me/username → https://t.me/username (keep as-is).
    Most SMM panels accept full t.me URLs, but some need @username.
    We send the full URL and also log what we sent.
    """
    link = link.strip()
    # If user entered @username, convert to full URL
    if link.startswith("@"):
        link = f"https://t.me/{link[1:]}"
    # If user entered just username (no @ or https)
    if not link.startswith("http") and not link.startswith("t.me"):
        link = f"https://t.me/{link}"
    return link


async def smm_request(action: str, **params) -> dict:
    query = {"key": settings.SMMWAY_API_KEY, "action": action, **params}
    async with httpx.AsyncClient(timeout=20) as c:
        r = await c.get(SMM_API_URL, params=query)
    log.info("smmway %s → status=%d body=%s", action, r.status_code, r.text[:300])
    result = r.json()
    if "error" in result:
        raise SmmApiError(result["error"])
    return result


async def place_order(service_id: int, link: str, quantity: int) -> int:
    link = normalize_tg_link(link)
    log.info("smmway place_order service=%d link=%r qty=%d", service_id, link, quantity)
    result = await smm_request("add", service=service_id, link=link, quantity=quantity)
    return int(result["order"])


async def get_order_status(order_id: int) -> dict:
    return await smm_request("status", order=order_id)


async def get_balance() -> float:
    result = await smm_request("balance")
    return float(result.get("balance", 0))
