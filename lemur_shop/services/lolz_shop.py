from __future__ import annotations

from lemur_shop.api.lolz import LolzApiError, lolz

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
    phone = (
        item.get("login")
        or item.get("phone")
        or item.get("account_phone")
        or ""
    )
    code = (
        item.get("password")
        or item.get("sms_code")
        or item.get("two_fa")
        or item.get("account_password")
        or ""
    )
    if phone and code:
        return str(phone).strip(), str(code).strip()
    return None


async def auto_buy(item_id: int, price: float) -> tuple[str, str]:
    item = await lolz.fast_buy(item_id, price)
    creds = extract_credentials(item)
    if creds:
        return creds
    item = await lolz.get_item(item_id)
    creds = extract_credentials(item)
    if creds:
        return creds
    raise ValueError(f"Credentials not found in item #{item_id}")


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
