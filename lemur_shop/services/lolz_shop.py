from __future__ import annotations

import httpx
import logging

from lemur_shop.api.lolz import LolzApiError, lolz

log = logging.getLogger(__name__)

# Конфіг категорій: country code, назва, прапор, ЦІНА В МАГАЗИНІ
CATEGORIES: dict[str, dict] = {
    "us": {"country": "US", "title": "USA",        "flag": "🇺🇸", "price_usd": 1.50, "pmax_tiers": [1.40]},
    "ua": {"country": "UA", "title": "Ukraine",    "flag": "🇺🇦", "price_usd": 3.00, "pmax_tiers": [2.50]},
    "kz": {"country": "KZ", "title": "Kazakhstan", "flag": "🇰🇿", "price_usd": 3.00, "pmax_tiers": [1.30, 1.70, 2.40]},
}


async def _search_with_pmax(country: str, pmax: float, limit: int = 10) -> list[dict]:
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
    """Шукає акаунт по тирам pmax, купує перший знайдений."""
    cat = CATEGORIES.get(category)
    if not cat:
        raise LolzApiError("Unknown category")
    country = cat["country"]
    tiers: list[float] = cat.get("pmax_tiers", [2.50])

    items: list[dict] = []
    for pmax in tiers:
        items = await _search_with_pmax(country, pmax)
        if items:
            log.info("Found %d accounts for %s at pmax=%.2f", len(items), category, pmax)
            break
        log.info("No accounts for %s at pmax=%.2f, trying next tier", category, pmax)

    if not items:
        raise LolzApiError("No accounts available in this category")

    items_sorted = sorted(items, key=lambda x: float(x.get("price") or x.get("price_usd") or 999))
    item = items_sorted[0]
    item_id = int(item.get("item_id") or item.get("id"))
    lolz_price = float(item.get("price") or item.get("price_usd") or 0)
    phone = await auto_buy(item_id, lolz_price)
    return phone, item_id, lolz_price
