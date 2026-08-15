from __future__ import annotations

"""Ціноутворення продажу Telegram Stars / Premium через Fragment.

Мета маржі:
  • Stars   — щонайменше +20% прибутку (плюс фікс. збір на газ TON).
  • Premium — чистими близько +$2 з кожної покупки.

Всі пороги — з config (env), тут лише формули + конвертація у балансні ⭐ і ₽.
"""

from lemur_shop.config import settings

# 1 балансна ⭐ магазину коштує стільки $ (курс поповнення балансу).
SHOP_STAR_USD = settings.STAR_DISPLAY_USD


def star_cost_usd(qty: int) -> float:
    """Собівартість qty реальних Telegram Stars у Fragment, $."""
    return qty * settings.FRAGMENT_STAR_COST_USD


def stars_sell_usd(qty: int) -> float:
    """Ціна продажу qty зірок покупцю, $ (≥20% маржі + збір на газ)."""
    cost = star_cost_usd(qty)
    return round(cost * (1 + settings.FRAGMENT_STARS_MARGIN_PCT / 100) + settings.FRAGMENT_STARS_FEE_USD, 2)


PREMIUM_COST_MAP = {
    3: "FRAGMENT_PREMIUM_3M_COST_USD",
    6: "FRAGMENT_PREMIUM_6M_COST_USD",
    12: "FRAGMENT_PREMIUM_12M_COST_USD",
}


def premium_cost_usd(months: int) -> float:
    attr = PREMIUM_COST_MAP.get(months)
    if not attr:
        raise ValueError("Premium доступний на 3, 6 або 12 місяців")
    return float(getattr(settings, attr))


def premium_sell_usd(months: int) -> float:
    """Ціна продажу Premium покупцю, $ (собівартість + чистими ~$2)."""
    return round(premium_cost_usd(months) + settings.FRAGMENT_PREMIUM_MARKUP_USD, 2)


def usd_to_shop_stars(usd: float) -> int:
    """$ → балансні ⭐ магазину (те, чим платить покупець)."""
    return round(usd / SHOP_STAR_USD) if SHOP_STAR_USD else 0


def usd_to_rub(usd: float, rate_rub: float) -> int:
    return round(usd * rate_rub)


def quote_stars(qty: int, rate_rub: float = 0.0) -> dict:
    """Повний розрахунок по зірках: собівартість, ціна, прибуток, маржа."""
    cost = star_cost_usd(qty)
    sell = stars_sell_usd(qty)
    profit = round(sell - cost, 2)
    return {
        "qty": qty,
        "cost_usd": round(cost, 2),
        "sell_usd": sell,
        "profit_usd": profit,
        "margin_pct": round(profit / cost * 100, 1) if cost else 0.0,
        "sell_shop_stars": usd_to_shop_stars(sell),
        "sell_rub": usd_to_rub(sell, rate_rub) if rate_rub else None,
    }


def quote_premium(months: int, rate_rub: float = 0.0) -> dict:
    cost = premium_cost_usd(months)
    sell = premium_sell_usd(months)
    profit = round(sell - cost, 2)
    return {
        "months": months,
        "cost_usd": round(cost, 2),
        "sell_usd": sell,
        "profit_usd": profit,
        "margin_pct": round(profit / cost * 100, 1) if cost else 0.0,
        "sell_shop_stars": usd_to_shop_stars(sell),
        "sell_rub": usd_to_rub(sell, rate_rub) if rate_rub else None,
    }
