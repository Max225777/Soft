from __future__ import annotations

import httpx
import logging

from lemur_shop.api.lolz import LolzApiError, lolz

log = logging.getLogger(__name__)

# Конфіг категорій: country code, назва, прапор, ЦІНА В МАГАЗИНІ
CATEGORIES: dict[str, dict] = {
    "us": {"country": "US", "title": "USA",       "flag": "🇺🇸", "price_usd": 1.50, "max_lolz_usd": 1.40},
    "ua": {"country": "UA", "title": "Ukraine",   "flag": "🇺🇦", "price_usd": 3.00, "max_lolz_usd": 2.50},
    "kz": {"country": "KZ", "title": "Kazakhstan","flag": "🇰🇿", "price_usd": 3.00, "max_lolz_usd": 2.50},
}


async def search_accounts(category: str, limit: int = 8) -> list[dict]:
    cat = CATEGORIES.get(category)
    country = cat["country"] if cat else category.upper()
    pmax = cat["max_lolz_usd"] if cat else 1.40
    try:
        return await lolz.search_telegram(country=country, pmax=pmax, count=limit)
    except LolzApiError:
        return []


async def auto_buy(item_id: int, price: float) -> str:
    """Купує акаунт і повертає телефон."""
    try:
        item = await lolz.fast_buy(item_id, price)
    except httpx.ReadTimeout:
        log.warning("fast_buy timeout for #%s, trying get_item", item_id)
        item = await lolz.get_item(item_id)

    phone = str(item.get("telegram_phone") or "").strip()
    if phone and not phone.startswith("+"):
        phone = "+" + phone

    if not phone:
        item = await lolz.get_item(item_id)
        phone = str(item.get("telegram_phone") or "").strip()
        if phone and not phone.startswith("+"):
            phone = "+" + phone

    if not phone:
        raise ValueError(f"Phone not found in item #{item_id}. Keys: {list(item.keys())}")

    log.info("Bought item #%s, phone=%r", item_id, phone)
    return phone


async def auto_buy_category(category: str) -> tuple[str, int, float]:
    """Шукає найдешевший акаунт у категорії, купує і повертає (phone, lolz_item_id, lolz_price_paid)."""
    items = await search_accounts(category, limit=10)
    if not items:
        raise LolzApiError("No accounts available in this category")
    items_sorted = sorted(items, key=lambda x: float(x.get("price") or x.get("price_usd") or 999))
    item = items_sorted[0]
    item_id = int(item.get("item_id") or item.get("id"))
    lolz_price = float(item.get("price") or item.get("price_usd") or 0)
    phone = await auto_buy(item_id, lolz_price)
    return phone, item_id, lolz_price
