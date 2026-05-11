from __future__ import annotations

import time
from decimal import Decimal

import httpx

_cache: dict[str, tuple[float, float]] = {}  # code -> (rate, expires_at)
_TTL = 3600  # 1 година


async def get_rate(currency: str) -> float:
    """Повертає курс USD → currency (наприклад UAH, RUB)."""
    code = currency.upper()
    cached = _cache.get(code)
    if cached and time.time() < cached[1]:
        return cached[0]

    try:
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.get(
                "https://cdn.jsdelivr.net/npm/@fawazahmed0/currency-api@latest/v1/currencies/usd.json"
            )
            data = r.json()
        rate = float(data["usd"][code.lower()])
    except Exception:
        # fallback: орієнтовні курси якщо API недоступне
        rate = {"UAH": 41.5, "RUB": 91.0}.get(code, 1.0)

    _cache[code] = (rate, time.time() + _TTL)
    return rate


CURRENCY_SYMBOL = {"ua": ("UAH", "₴"), "ru": ("RUB", "₽")}


async def format_balance(usd: Decimal, lang: str) -> str:
    """Форматує баланс: $1.23 → '1.23 $ / 50.87 ₴'"""
    code, symbol = CURRENCY_SYMBOL.get(lang, ("USD", "$"))
    rate = await get_rate(code)
    local = float(usd) * rate
    return f"<b>${float(usd):.2f}</b>  (~{local:.0f} {symbol})"
