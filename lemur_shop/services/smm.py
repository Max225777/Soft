from __future__ import annotations

import httpx
import logging

from lemur_shop.config import settings

log = logging.getLogger(__name__)

SMM_API_URL = "https://smmway.ru/api/v2"

# Курс RUB→USD для розрахунку собівартості
RUB_PER_USD = 90.0


def rub_to_usd(rub: float) -> float:
    return round(rub / RUB_PER_USD, 6)


# cost_rub_per_1000 — собівартість за 1000 одиниць в рублях
SMM_SERVICES: dict[str, dict] = {
    "tg_subscribers": {
        "service_id": 6322,
        "title":      "Підписники Telegram",
        "flag":       "\U0001f465",
        "description": "Реальні підписники, гарантія 365 днів",
        "price_per_100_stars": 10,
        "min": 10,
        "max": 10000,
        "step": 1,
        "unit_size": 100,
        "cost_rub_per_1000": 41.0,
    },
    "tg_views": {
        "service_id": 6216,
        "title":      "Перегляди Telegram",
        "flag":       "\U0001f441️",
        "description": "Перегляди постів Telegram",
        "price_per_100_stars": 1.5,
        "min": 100,
        "max": 100000,
        "step": 100,
        "unit_size": 1000,
        "cost_rub_per_1000": 8.8,
    },
    "tg_reactions": {
        "service_id": 6257,
        "title":      "Реакції Telegram",
        "flag":       "\U0001f4a9",
        "description": "Реакція на пост",
        "price_per_100_stars": 3.34,
        "min": 15,
        "max": 5000,
        "step": 1,
        "unit_size": 100,
        "cost_rub_per_1000": 1.0,
    },
    "tg_react_poop": {
        "service_id": 5450,
        "title":      "\U0001f4a9 Реакція",
        "flag":       "\U0001f4a9",
        "description": "Реакція \U0001f4a9 на пост",
        "price_per_100_stars": 3.34,
        "min": 15,
        "max": 5000,
        "step": 1,
        "unit_size": 100,
        "cost_rub_per_1000": 1.0,
    },
    "tg_react_clown": {
        "service_id": 5465,
        "title":      "\U0001f921 Реакція",
        "flag":       "\U0001f921",
        "description": "Реакція \U0001f921 на пост",
        "price_per_100_stars": 3.34,
        "min": 15,
        "max": 5000,
        "step": 1,
        "unit_size": 100,
        "cost_rub_per_1000": 1.0,
    },
    "tg_react_middlefinger": {
        "service_id": 5437,
        "title":      "\U0001f595 Реакція",
        "flag":       "\U0001f595",
        "description": "Реакція \U0001f595 на пост",
        "price_per_100_stars": 3.34,
        "min": 15,
        "max": 5000,
        "step": 1,
        "unit_size": 100,
        "cost_rub_per_1000": 1.0,
    },
    "tg_react_vomit": {
        "service_id": 5452,
        "title":      "\U0001f92e Реакція",
        "flag":       "\U0001f92e",
        "description": "Реакція \U0001f92e на пост",
        "price_per_100_stars": 3.34,
        "min": 15,
        "max": 5000,
        "step": 1,
        "unit_size": 100,
        "cost_rub_per_1000": 1.0,
    },
    "tg_react_heart": {
        "service_id": 6077,
        "title":      "❤️ Реакція",
        "flag":       "❤️",
        "description": "Реакція ❤️ на пост",
        "price_per_100_stars": 3.34,
        "min": 15,
        "max": 5000,
        "step": 1,
        "unit_size": 100,
        "cost_rub_per_1000": 0.98,
        "api_type": "posts",
    },
    "tg_react_fire": {
        "service_id": 6078,
        "title":      "\U0001f525 Реакція",
        "flag":       "\U0001f525",
        "description": "Реакція \U0001f525 на пост",
        "price_per_100_stars": 3.34,
        "min": 15,
        "max": 5000,
        "step": 1,
        "unit_size": 100,
        "cost_rub_per_1000": 0.98,
        "api_type": "posts",
    },
    "tg_react_mix_pos": {
        "service_id": 6255,
        "title":      "\U0001f44d❤️\U0001f525\U0001f389 Міксові реакції",
        "flag":       "\U0001f44d",
        "description": "Мікс позитивних реакцій \U0001f44d❤️\U0001f525\U0001f389 на пост",
        "price_per_100_stars": 3.34,
        "min": 15,
        "max": 5000,
        "step": 1,
        "unit_size": 100,
        "cost_rub_per_1000": 0.98,
        "api_type": "posts",
    },
    "tg_react_mix_neg": {
        "service_id": 6256,
        "title":      "\U0001f44e\U0001f4a9\U0001f631\U0001f62d Міксові реакції",
        "flag":       "\U0001f44e",
        "description": "Мікс негативних реакцій \U0001f44e\U0001f4a9\U0001f631\U0001f62d на пост",
        "price_per_100_stars": 3.34,
        "min": 15,
        "max": 5000,
        "step": 1,
        "unit_size": 100,
        "cost_rub_per_1000": 0.98,
        "api_type": "posts",
    },
}


def smm_cost_usd(service_key: str, quantity: int) -> float:
    """Розраховує собівартість SMM замовлення в USD."""
    svc = SMM_SERVICES.get(service_key, {})
    cost_rub = svc.get("cost_rub_per_1000", 0) * quantity / 1000
    return rub_to_usd(cost_rub)


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


async def place_order(service_id: int | str, link: str, quantity: int, api_type: str = "link") -> int:
    link = normalize_tg_link(link)
    log.info("smmway place_order service=%s link=%r qty=%d api_type=%s", service_id, link, quantity, api_type)
    if api_type == "posts":
        # smmway reaction services: posts=count, link=url, min/max range (max must be > min)
        result = await smm_request("add", service=service_id, posts=1, link=link, min=quantity, max=quantity + 1)
    else:
        result = await smm_request("add", service=service_id, link=link, quantity=quantity)
    return int(result["order"])


async def get_order_status(order_id: int) -> dict:
    return await smm_request("status", order=order_id)


async def get_balance() -> float:
    result = await smm_request("balance")
    return float(result.get("balance", 0))
