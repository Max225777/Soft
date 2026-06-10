from __future__ import annotations

import asyncio
import httpx
import logging

from lemur_shop.api.lolz import LolzApiError, lolz

log = logging.getLogger(__name__)

# Конфіг категорій
# macro=True  → USA-style: ітеративний pmin-bump при чорному списку
#   pmax        — максимальна ціна покупки на lolz
#   pmin_start  — стартовий pmin (None = без обмеження знизу)
#   macro_steps — кількість макро-ітерацій
#   micro_attempts — спроб купівлі за ітерацію
# pmax_tiers  → стандартний режим: перебираємо тири pmax
CATEGORIES: dict[str, dict] = {
    "us": {
        "country": "US", "title": "USA", "title_ru": "США", "title_ua": "США",
        "flag": "🇺🇸", "phone_prefix": "+1",
        "price_usd": 0.65, "discount_stars": 25,
        "macro": True, "pmax": 0.50, "pmin_start": None,
        "macro_steps": 8, "micro_attempts": 15,
    },
    "mm": {
        "country": "MM", "title": "Myanmar", "title_ru": "Мьянма", "title_ua": "М'янма",
        "flag": "🇲🇲", "phone_prefix": "+95",
        "price_usd": 0.65, "discount_stars": 25,
        "macro": True, "pmax": 0.40, "pmin_start": 0.20,
        "macro_steps": 8, "micro_attempts": 15,
    },
    "co": {
        "country": "CO", "title": "Colombia", "title_ru": "Колумбия", "title_ua": "Колумбія",
        "flag": "🇨🇴", "phone_prefix": "+57",
        "price_usd": 0.78, "discount_stars": 45,
        "pmax_tiers": [0.50],
    },
    "de": {
        "country": "DE", "title": "Germany", "title_ru": "Германия", "title_ua": "Німеччина",
        "flag": "🇩🇪", "phone_prefix": "+49",
        "price_usd": 1.95, "discount_stars": 115,
        "pmax_tiers": [1.50],
    },
    "ua": {
        "country": "UA", "title": "Ukraine", "title_ru": "Украина", "title_ua": "Україна",
        "flag": "🇺🇦", "phone_prefix": "+380",
        "price_usd": 3.25, "discount_stars": 150,
        "pmax_tiers": [2.50],
    },
    "kz": {
        "country": "KZ", "title": "Kazakhstan", "title_ru": "Казахстан", "title_ua": "Казахстан",
        "flag": "🇰🇿", "phone_prefix": "+7",
        "price_usd": 3.25, "discount_stars": 150,
        "pmax_tiers": [1.50, 2.00],
    },
}


async def _search_with_pmax(country: str, pmax: float, limit: int = 10) -> list[dict]:
    try:
        return await lolz.search_telegram(country=country, pmax=pmax, count=limit)
    except LolzApiError:
        return []


async def search_accounts(category: str, limit: int = 8) -> list[dict]:
    cat = CATEGORIES.get(category)
    if not cat:
        return []
    country = cat["country"]
    for pmax in cat.get("pmax_tiers", [cat.get("pmax", 2.50)]):
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


SKIP_ERRORS = (
    "user_inactive", "already_sold", "item_sold", "not_found", "forbidden",
    "invalid_account", "account_not_valid", "verification", "check_failed",
    "account_invalid", "phone_banned", "banned", "spam", "deactivated",
    "проверк",
    "ошибок во",
    "более 20",
)

BLACKLIST_MSG = "черный список"


async def _try_buy_batch(
    items: list[dict], max_cost: float, micro_limit: int
) -> tuple[tuple[str, int, float] | None, float]:
    """Пробує купити з батчу.
    Повертає (result_or_None, max_blacklisted_price).
    """
    micro = 0
    max_bl_price: float = 0.0
    for item in items:
        if micro >= micro_limit:
            break
        item_id = int(item.get("item_id") or item.get("id"))
        lolz_price = float(item.get("price") or item.get("price_usd") or 0)
        if lolz_price > max_cost:
            break
        micro += 1
        try:
            phone = await auto_buy(item_id, lolz_price)
            return (phone, item_id, lolz_price), max_bl_price
        except (LolzApiError, ValueError) as e:
            err_text = str(e).lower()
            is_blacklist = BLACKLIST_MSG in str(e)
            is_skip = any(skip in err_text for skip in SKIP_ERRORS) or (
                isinstance(e, LolzApiError) and e.status == 403
            )
            if is_skip:
                if is_blacklist:
                    max_bl_price = max(max_bl_price, lolz_price)
                log.warning("Item #%s skipped (%s), micro %d/%d", item_id, e, micro, micro_limit)
                continue
            raise
    return None, max_bl_price


async def _macro_buy(cat: dict) -> tuple[str, int, float]:
    """Macro-цикл для категорій з macro=True (USA, Myanmar тощо).
    Ітеративно підвищує pmin при помилках чорного списку.
    """
    country      = cat["country"]
    pmax         = cat["pmax"]
    macro_steps  = cat.get("macro_steps", 8)
    micro_att    = cat.get("micro_attempts", 15)
    pmin: float | None = cat.get("pmin_start")

    for macro in range(macro_steps):
        items = []
        for attempt in range(3):
            try:
                items = await lolz.search_telegram(
                    country=country, pmax=pmax, pmin=pmin, count=50,
                    spam="no", password=None,
                )
                break
            except LolzApiError as e:
                log.warning("%s macro %d search attempt %d failed: %s", country, macro, attempt + 1, e)
                if attempt < 2:
                    await asyncio.sleep(2)

        if not items:
            log.info("%s macro %d: no items at pmin=%s pmax=%.2f", country, macro, pmin, pmax)
            break

        items_sorted = sorted(items, key=lambda x: float(x.get("price") or x.get("price_usd") or 999))
        log.info("%s macro %d: %d items, cheapest=%.2f", country, macro, len(items_sorted),
                 float(items_sorted[0].get("price") or items_sorted[0].get("price_usd") or 0))

        result, max_bl_price = await _try_buy_batch(items_sorted, max_cost=pmax, micro_limit=micro_att)
        if result:
            return result

        if max_bl_price > 0:
            new_pmin = round(max_bl_price + 0.02, 2)
            pmin = max(pmin or 0.0, new_pmin)
            log.info("%s macro %d: blacklisted up to %.2f → pmin=%.2f", country, macro, max_bl_price, pmin)
        else:
            last_price = float(items_sorted[-1].get("price") or items_sorted[-1].get("price_usd") or 0)
            pmin = round(last_price + 0.01, 2)
            log.info("%s macro %d exhausted, bumping pmin to %.2f", country, macro, pmin)

    raise LolzApiError("No purchasable accounts found after trying all candidates")


async def auto_buy_category(category: str) -> tuple[str, int, float]:
    cat = CATEGORIES.get(category)
    if not cat:
        raise LolzApiError("Unknown category")

    if cat.get("macro"):
        return await _macro_buy(cat)

    # ── Стандартний режим: тири pmax ──────────────────────────────────────────
    country    = cat["country"]
    shop_price = cat.get("price_usd", 9999)
    tiers: list[float] = cat.get("pmax_tiers", [2.50])
    items: list[dict] = []
    for pmax in tiers:
        try:
            items = await lolz.search_telegram(country=country, pmax=pmax, count=50)
        except LolzApiError:
            items = []
        if items:
            log.info("Found %d accounts for %s at pmax=%.2f", len(items), category, pmax)
            break
        log.info("No accounts for %s at pmax=%.2f, trying next tier", category, pmax)

    if not items:
        raise LolzApiError("No accounts available in this category")

    items_sorted = sorted(items, key=lambda x: float(x.get("price") or x.get("price_usd") or 999))
    log.info("Price range for %s: top5=%s", category,
             [float(i.get("price") or i.get("price_usd") or 0) for i in items_sorted[:5]])

    result, _ = await _try_buy_batch(items_sorted, max_cost=shop_price, micro_limit=5)
    if result:
        return result

    raise LolzApiError("No purchasable accounts found after trying all candidates")
