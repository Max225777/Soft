from __future__ import annotations

import httpx
import logging

from lemur_shop.config import settings

log = logging.getLogger(__name__)

SMM_API_URL = "https://smmway.ru/api/v2"


# service_id може бути int (числовий ID) або str (slug для окремих реакцій)
SMM_SERVICES: dict[str, dict] = {
    "tg_subscribers": {
        "service_id": 6322,
        "title":      "Підписники Telegram",
        "flag":       "👥",
        "description": "Реальні підписники, гарантія 365 днів",
        "price_per_100_stars": 10,
        "min": 10,
        "max": 10000,
        "step": 1,
        "unit_size": 100,
    },
    "tg_views": {
        "service_id": 6252,
        "title":      "Перегляди Telegram",
        "flag":       "👁️",
        "description": "Перегляди постів Telegram",
        "price_per_100_stars": 1,
        "min": 100,
        "max": 100000,
        "step": 100,
        "unit_size": 1000,
    },
    "tg_reactions_pos": {
        "service_id": 6257,
        "title":      "👍❤️🔥🎉 Реакції",
        "flag":       "👍",
        "description": "Позитивні реакції на пост",
        "price_per_100_stars": 10,
        "min": 15,
        "max": 5000,
        "step": 1,
        "unit_size": 100,
    },
    "tg_reactions_neg": {
        "service_id": 6258,
        "title":      "👎💩😱😢 Реакції",
        "flag":       "👎",
        "description": "Негативні реакції на пост",
        "price_per_100_stars": 10,
        "min": 15,
        "max": 5000,
        "step": 1,
        "unit_size": 100,
    },
    "tg_react_heart": {
        "service_id": "telegram-reaksii-heart",
        "title":      "❤️ Реакція",
        "flag":       "❤️",
        "description": "Реакція ❤️ на пост",
        "price_per_100_stars": 10,
        "min": 15,
        "max": 5000,
        "step": 1,
        "unit_size": 100,
    },
    "tg_react_like": {
        "service_id": "telegram-reaksii-like",
        "title":      "👍 Реакція",
        "flag":       "👍",
        "description": "Реакція 👍 на пост",
        "price_per_100_stars": 10,
        "min": 15,
        "max": 5000,
        "step": 1,
        "unit_size": 100,
    },
    "tg_react_dislike": {
        "service_id": "telegram-reaksii-dislikee",
        "title":      "👎 Реакція",
        "flag":       "👎",
        "description": "Реакція 👎 на пост",
        "price_per_100_stars": 10,
        "min": 15,
        "max": 5000,
        "step": 1,
        "unit_size": 100,
    },
    "tg_react_poop": {
        "service_id": 5450,
        "title":      "💩 Реакція",
        "flag":       "💩",
        "description": "Реакція 💩 на пост",
        "price_per_100_stars": 10,
        "min": 15,
        "max": 5000,
        "step": 1,
        "unit_size": 100,
    },
    "tg_react_clown": {
        "service_id": 5465,
        "title":      "🤡 Реакція",
        "flag":       "🤡",
        "description": "Реакція 🤡 на пост",
        "price_per_100_stars": 10,
        "min": 15,
        "max": 5000,
        "step": 1,
        "unit_size": 100,
    },
}


class SmmApiError(Exception):
    pass


def normalize_tg_link(link: str) -> str:
    """Convert any TG link format to t.me/username (no protocol, per smmway docs)."""
    link = link.strip()
    if link.startswith("@"):
        return f"t.me/{link[1:]}"
    for prefix in ("https://", "http://"):
        if link.startswith(prefix):
            link = link[len(prefix):]
    if not link.startswith("t.me/"):
        link = f"t.me/{link}"
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


async def place_order(service_id: int | str, link: str, quantity: int) -> int:
    link = normalize_tg_link(link)
    log.info("smmway place_order service=%s link=%r qty=%d", service_id, link, quantity)
    result = await smm_request("add", service=service_id, link=link, quantity=quantity)
    return int(result["order"])


async def get_order_status(order_id: int) -> dict:
    return await smm_request("status", order=order_id)


async def get_balance() -> float:
    result = await smm_request("balance")
    return float(result.get("balance", 0))
