from __future__ import annotations

import asyncio
import httpx
import logging

from lemur_shop.api.lolz import LolzApiError, lolz

log = logging.getLogger(__name__)

# Конфіг категорій: country code, назва, прапор, ЦІНА В МАГАЗИНІ
CATEGORIES: dict[str, dict] = {
    "us": {"country": "US", "title": "USA",        "flag": "🇺🇸", "price_usd": 0.65, "discount_stars": 25,  "pmax_tiers": [0.50]},
    "de": {"country": "DE", "title": "Germany",    "flag": "🇩🇪", "price_usd": 1.95, "discount_stars": 115, "pmax_tiers": [1.50]},
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


SKIP_ERRORS = (
    "user_inactive", "already_sold", "item_sold", "not_found", "forbidden",
    "invalid_account", "account_not_valid", "verification", "check_failed",
    "account_invalid", "phone_banned", "banned", "spam", "deactivated",
    "проверк",       # "проверки аккаунта" — verification errors in Russian
    "ошибок во",     # "ошибок во время проверки"
    "более 20",      # "более 20 ошибок"
)

USA_PMAX = 0.50
USA_MACRO_STEPS = 8
USA_MICRO_ATTEMPTS = 15


async def _try_buy_batch(items: list[dict], max_cost: float, micro_limit: int) -> tuple[str, int, float] | None:
    """Пробує купити з батчу акаунтів, повертає (phone, item_id, price) або None."""
    micro = 0
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
            return phone, item_id, lolz_price
        except (LolzApiError, ValueError) as e:
            err_text = str(e).lower()
            # 403 від fast-buy = проблема з акаунтом (перевірка/заблоковано), не з API-ключем
            is_skip = any(skip in err_text for skip in SKIP_ERRORS) or (
                isinstance(e, LolzApiError) and e.status == 403
            )
            if is_skip:
                log.warning("Item #%s skipped (%s), micro %d/%d", item_id, e, micro, micro_limit)
                continue
            raise
    return None


async def auto_buy_category(category: str) -> tuple[str, int, float]:
    """Шукає акаунт по тирам pmax, купує перший знайдений."""
    cat = CATEGORIES.get(category)
    if not cat:
        raise LolzApiError("Unknown category")
    country = cat["country"]
    shop_price: float = cat.get("price_usd", 9999)

    # ── USA: макро-цикл з покроковим підвищенням ціни ──────────────────────────
    if category == "us":
        pmin: float | None = None
        for macro in range(USA_MACRO_STEPS):
            # Retry пошуку: 403 від Lolz може бути тимчасовий rate-limit
            items = []
            for attempt in range(3):
                try:
                    items = await lolz.search_telegram(
                        country=country, pmax=USA_PMAX, pmin=pmin, count=50,
                        spam="no", password=None,
                    )
                    break  # успішно — виходимо з retry
                except LolzApiError as e:
                    log.warning("USA macro %d search attempt %d failed: %s", macro, attempt + 1, e)
                    if attempt < 2:
                        await asyncio.sleep(2)  # чекаємо перед retry

            if not items:
                log.info("USA macro %d: no items at pmin=%s pmax=%.2f", macro, pmin, USA_PMAX)
                break

            items_sorted = sorted(items, key=lambda x: float(x.get("price") or x.get("price_usd") or 999))
            log.info("USA macro %d: %d items, cheapest=%.2f", macro, len(items_sorted),
                     float(items_sorted[0].get("price") or items_sorted[0].get("price_usd") or 0))

            result = await _try_buy_batch(items_sorted, max_cost=USA_PMAX, micro_limit=USA_MICRO_ATTEMPTS)
            if result:
                return result

            # усі мікро провалились — підвищуємо pmin на $0.01 від найдорожчого з батчу
            last_price = float(items_sorted[-1].get("price") or items_sorted[-1].get("price_usd") or 0)
            pmin = round(last_price + 0.01, 2)
            log.info("USA macro %d exhausted, bumping pmin to %.2f", macro, pmin)

        raise LolzApiError("No purchasable accounts found after trying all candidates")

    # ── Інші категорії: тири pmax ───────────────────────────────────────────────
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

    result = await _try_buy_batch(items_sorted, max_cost=shop_price, micro_limit=5)
    if result:
        return result

    raise LolzApiError("No purchasable accounts found after trying all candidates")
