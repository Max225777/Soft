from __future__ import annotations

import httpx
import logging

from lemur_shop.api.lolz import LolzApiError, lolz

log = logging.getLogger(__name__)

# Конфіг категорій: country code, назва, прапор, ЦІНА В МАГАЗИНІ
CATEGORIES: dict[str, dict] = {
    "us": {"country": "US", "title": "USA",        "flag": "🇺🇸", "price_usd": 1.30, "discount_stars": 25,  "pmax_tiers": [0.50]},
    "ua": {"country": "UA", "title": "Ukraine",    "flag": "🇺🇦", "price_usd": 3.25, "discount_stars": 150, "pmax_tiers": [2.50]},
    "kz": {"country": "KZ", "title": "Kazakhstan", "flag": "🇰🇿", "price_usd": 3.25, "discount_stars": 150, "pmax_tiers": [1.50, 2.00]},
}


async def _search_with_pmax(country: str, pmax: float, limit: int = 10) -> list[dict]:
    try:
        return await lolz.search_telegram(country=country, pmax=pmax, count=limit)
    except LolzApiError:
        return []


async def search_accounts(category: str, limit: int = 8) -> list[dict]:
    """Шукає акаунти по тирах pmax, повертає перший непустий результат."""
    cat = CATEGORIES.get(category)
    if not cat:
        return []
    country = cat["country"]
    for pmax in cat.get("pmax_tiers", [2.50]):
        items = await _search_with_pmax(country, pmax, limit)
        if items:
            return items
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
    shop_price: float = cat.get("price_usd", 9999)

    items: list[dict] = []
    for pmax in tiers:
        items = await _search_with_pmax(country, pmax, limit=50)
        if items:
            log.info("Found %d accounts for %s at pmax=%.2f", len(items), category, pmax)
            break
        log.info("No accounts for %s at pmax=%.2f, trying next tier", category, pmax)

    if not items:
        raise LolzApiError("No accounts available in this category")

    items_sorted = sorted(items, key=lambda x: float(x.get("price") or x.get("price_usd") or 999))

    prices = [float(i.get("price") or i.get("price_usd") or 0) for i in items_sorted[:5]]
    log.info("Price range for %s: top5=%s, shop_price=%.2f", category, prices, shop_price)

    SKIP_ERRORS = (
        "user_inactive", "already_sold", "item_sold", "not_found", "forbidden",
        "invalid_account", "account_not_valid", "verification", "check_failed",
        "account_invalid", "phone_banned", "banned", "spam", "deactivated",
    )

    attempts = 0
    MAX_ATTEMPTS = 5

    for item in items_sorted:
        if attempts >= MAX_ATTEMPTS:
            log.warning("Reached max %d attempts for category %s", MAX_ATTEMPTS, category)
            break

        item_id = int(item.get("item_id") or item.get("id"))
        lolz_price = float(item.get("price") or item.get("price_usd") or 0)

        max_cost = 0.50 if category == "us" else shop_price
        if lolz_price > max_cost:
            raise LolzApiError(
                f"Margin too low: cost ${lolz_price:.2f}, max ${max_cost:.2f}"
            )

        attempts += 1
        try:
            phone = await auto_buy(item_id, lolz_price)
            return phone, item_id, lolz_price
        except (LolzApiError, ValueError) as e:
            err_text = str(e).lower()
            if any(skip in err_text for skip in SKIP_ERRORS):
                log.warning("Item #%s skipped (%s), attempt %d/%d", item_id, e, attempts, MAX_ATTEMPTS)
                continue
            raise

    raise LolzApiError("No purchasable accounts found after trying all candidates")
