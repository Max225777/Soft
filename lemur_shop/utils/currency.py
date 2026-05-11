from __future__ import annotations

import time
from decimal import Decimal

import httpx

_cache: dict[str, tuple[float, float]] = {}
_TTL = 600  # 10 хвилин
_FALLBACK = {"UAH": 41.5, "RUB": 91.0}


async def _fetch_uah() -> float:
    """Monobank API — оновлюється кожні ~5 хвилин."""
    async with httpx.AsyncClient(timeout=5) as client:
        r = await client.get("https://api.monobank.ua/bank/currency")
        pairs = r.json()
    # currencyCodeA=840 (USD), currencyCodeB=980 (UAH)
    for pair in pairs:
        if pair.get("currencyCodeA") == 840 and pair.get("currencyCodeB") == 980:
            return float(pair["rateSell"])  # курс продажу долара
    raise ValueError("USD/UAH pair not found")


async def _fetch_rub() -> float:
    """ЦБ РФ JSON — офіційний курс, оновлюється щодня."""
    async with httpx.AsyncClient(timeout=5) as client:
        r = await client.get("https://www.cbr-xml-daily.ru/daily_json.js")
        data = r.json()
    return float(data["Valute"]["USD"]["Value"])


_FETCHERS = {"UAH": _fetch_uah, "RUB": _fetch_rub}


async def get_rate(currency: str) -> float:
    code = currency.upper()
    cached = _cache.get(code)
    if cached and time.time() < cached[1]:
        return cached[0]

    try:
        rate = await _FETCHERS[code]()
    except Exception:
        rate = _FALLBACK.get(code, 1.0)

    _cache[code] = (rate, time.time() + _TTL)
    return rate


CURRENCY_META = {"ua": ("UAH", "₴"), "ru": ("RUB", "₽")}


async def format_balance(usd: Decimal, lang: str) -> str:
    code, symbol = CURRENCY_META.get(lang, ("USD", "$"))
    rate = await get_rate(code)
    local = float(usd) * rate
    return f"<b>${float(usd):.2f}</b>  (~{local:.0f} {symbol})"
