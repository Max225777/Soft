from __future__ import annotations

from decimal import Decimal

import httpx

from bot.config import settings

# Офіційний курс Telegram: 50 Stars = $1 (може змінитись)
_DEFAULT_STARS_PER_USD = Decimal("50")

# Кешований курс (оновлюється при старті і раз на годину)
_cached_rate: Decimal = _DEFAULT_STARS_PER_USD


def set_rate(stars_per_usd: Decimal) -> None:
    global _cached_rate
    _cached_rate = stars_per_usd


def get_rate() -> Decimal:
    return _cached_rate


def stars_to_usd(stars: int) -> Decimal:
    """Конвертує кількість зірок у USD."""
    return (Decimal(stars) / _cached_rate).quantize(Decimal("0.000001"))


def usd_to_stars(usd: Decimal) -> int:
    """Скільки зірок потрібно щоб покрити суму в USD (округлення вгору)."""
    import math
    return math.ceil(float(usd * _cached_rate))


async def fetch_stars_rate() -> Decimal:
    """
    Отримує актуальний курс зірок.
    Telegram офіційно: 1 USD = 50 Stars (Fragment курс).
    При появі публічного API — замінити логіку тут.
    """
    # TODO: замінити на реальний API Fragment коли з'явиться
    return _DEFAULT_STARS_PER_USD
