from __future__ import annotations

from decimal import Decimal

import httpx

from bot.db.models import Currency, ExchangeRate

# Символи валют
CURRENCY_SYMBOLS: dict[str, str] = {
    Currency.USD: "$",
    Currency.UAH: "₴",
    Currency.RUB: "₽",
    Currency.KZT: "₸",
}

# Дефолтні курси (1 USD = N одиниць) — fallback якщо API недоступне
_FALLBACK_RATES: dict[str, Decimal] = {
    Currency.UAH: Decimal("41.5"),
    Currency.RUB: Decimal("92.0"),
    Currency.KZT: Decimal("470.0"),
}

# Кеш в пам'яті (оновлюється з БД / API)
_rates: dict[str, Decimal] = dict(_FALLBACK_RATES)


def set_rates(rates: dict[str, Decimal]) -> None:
    _rates.update(rates)


def usd_to(amount_usd: Decimal, currency: str) -> Decimal:
    if currency == Currency.USD:
        return amount_usd
    rate = _rates.get(currency, _FALLBACK_RATES.get(currency, Decimal("1")))
    return (amount_usd * rate).quantize(Decimal("0.01"))


def format_amount(amount_usd: Decimal, currency: str) -> str:
    converted = usd_to(amount_usd, currency)
    symbol = CURRENCY_SYMBOLS.get(currency, currency)
    if currency == Currency.USD:
        return f"{symbol}{converted:,.2f}"
    return f"{converted:,.0f} {symbol}"


async def fetch_rates() -> dict[str, Decimal]:
    """Отримує курси з Binance P2P або ЦБ РФ. Fallback на кеш."""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            # USD/UAH, USD/RUB, USD/KZT через Binance
            results: dict[str, Decimal] = {}
            pairs = {
                Currency.UAH: "USDTAH",   # Binance не має прямого, беремо з крос-курсу
                Currency.RUB: "USDTRUB",
                Currency.KZT: "USDTKZT",
            }
            for currency, symbol in pairs.items():
                try:
                    r = await client.get(
                        "https://api.binance.com/api/v3/ticker/price",
                        params={"symbol": symbol},
                    )
                    if r.status_code == 200:
                        price = Decimal(r.json()["price"])
                        results[currency] = price
                except Exception:
                    results[currency] = _FALLBACK_RATES[currency]
            return results
    except Exception:
        return dict(_FALLBACK_RATES)
