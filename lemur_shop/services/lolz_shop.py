from __future__ import annotations

from lemur_shop.api.lolz import LolzApiError, lolz

# Маппінг категорій бота → код країни Lolz
CATEGORY_COUNTRY: dict[str, str] = {
    "ua": "UA",
    "kz": "KZ",
    "ru": "RU",
}

MAX_PRICE_USD = 2.0  # максимальна ціна пошуку


async def search_accounts(category: str, limit: int = 8) -> list[dict]:
    """Повертає список доступних акаунтів з Lolz для категорії."""
    country = CATEGORY_COUNTRY.get(category, category.upper())
    try:
        return await lolz.search_telegram(country=country, pmax=MAX_PRICE_USD, count=limit)
    except LolzApiError:
        return []


def extract_credentials(item: dict) -> tuple[str, str] | None:
    """Витягує (phone, code) з об'єкту item після покупки."""
    # Різні поля залежно від типу акаунту
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
    """
    Купує акаунт на Lolz і повертає (phone, code).
    Кидає LolzApiError або ValueError якщо дані не знайдено.
    """
    item = await lolz.fast_buy(item_id, price)
    creds = extract_credentials(item)
    if creds:
        return creds

    # Іноді дані приходять в окремому запиті після купівлі
    item = await lolz.get_item(item_id)
    creds = extract_credentials(item)
    if creds:
        return creds

    raise ValueError(f"Credentials not found in item #{item_id}")
