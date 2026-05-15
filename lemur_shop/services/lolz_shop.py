from __future__ import annotations

import httpx
import logging

from lemur_shop.api.lolz import LolzApiError, lolz

log = logging.getLogger(__name__)

# Конфіг категорій: country code, назва, прапор, ЦІНА В МАГАЗИНІ
CATEGORIES: dict[str, dict] = {
    "us": {"country": "US", "title": "USA",       "flag": "🇺🇸", "price_usd": 1.50},
    # Додавати нові країни тут:
    # "ru": {"country": "RU", "title": "Россия",   "flag": "🇷🇺", "price_usd": 0.80},
    # "ua": {"country": "UA", "title": "Україна",  "flag": "🇺🇦", "price_usd": 0.80},
    # "kz": {"country": "KZ", "title": "Казахстан","flag": "🇰🇿", "price_usd": 0.80},
}

MAX_LOLZ_PRICE_USD = 1.40  # максимум, який платимо Lolz за один акаунт


async def search_accounts(category: str, limit: int = 8) -> list[dict]:
    cat = CATEGORIES.get(category)
    country = cat["country"] if cat else category.upper()
    try:
        return await lolz.search_telegram(country=country, pmax=MAX_LOLZ_PRICE_USD, count=limit)
    except LolzApiError:
        return []


def extract_credentials(item: dict) -> tuple[str, str] | None:
    log.info("Item keys: %s", list(item.keys()))
    log.info("Item data: %s", {k: v for k, v in item.items() if k not in ("description",)})

    # Шукаємо у всіх можливих полях + вкладених словниках
    def _search(d: dict, *keys):
        for k in keys:
            v = d.get(k)
            if v:
                return str(v).strip()
        return ""

    phone = _search(item,
        "login", "phone", "account_phone", "account_login",
        "phoneNumber", "phone_number",
    )
    code = _search(item,
        "password", "sms_code", "two_fa", "account_password",
        "twofa", "2fa", "code", "auth_code",
    )

    # Іноді дані в item["data"] або item["item"]
    for nested_key in ("data", "item", "account", "account_data"):
        nested = item.get(nested_key)
        if isinstance(nested, dict):
            if not phone:
                phone = _search(nested,
                    "login", "phone", "account_phone", "account_login",
                    "phoneNumber", "phone_number",
                )
            if not code:
                code = _search(nested,
                    "password", "sms_code", "two_fa", "account_password",
                    "twofa", "2fa", "code", "auth_code",
                )

    log.info("Extracted phone=%r code=%r", phone, code)
    if phone and code:
        return phone, code
    return None


async def auto_buy(item_id: int, price: float) -> tuple[str, str]:
    try:
        item = await lolz.fast_buy(item_id, price)
        log.info("fast_buy response for #%s: %s", item_id, item)
    except httpx.ReadTimeout:
        log.warning("fast_buy timeout for #%s, trying get_item", item_id)
        item = await lolz.get_item(item_id)
    creds = extract_credentials(item)
    if creds:
        return creds
    log.info("Retrying get_item for #%s", item_id)
    item = await lolz.get_item(item_id)
    creds = extract_credentials(item)
    if creds:
        return creds
    raise ValueError(f"Credentials not found in item #{item_id}. Keys: {list(item.keys())}")


async def auto_buy_category(category: str) -> tuple[str, str]:
    """Шукає найдешевший акаунт у категорії та купує його."""
    items = await search_accounts(category, limit=10)
    if not items:
        raise LolzApiError("No accounts available in this category")
    items_sorted = sorted(items, key=lambda x: float(x.get("price") or x.get("price_usd") or 999))
    item = items_sorted[0]
    item_id = item.get("item_id") or item.get("id")
    lolz_price = float(item.get("price") or item.get("price_usd") or 0)
    return await auto_buy(int(item_id), lolz_price)
