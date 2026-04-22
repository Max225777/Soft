"""Работа с нишами: CRUD и сопоставление аккаунтов правилам."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Iterable

from sqlalchemy import select

from app.db.models import Account, Niche
from app.db.session import get_session


@dataclass
class NicheFilters:
    category: str = ""
    country: str = ""
    price_min: float | None = None
    price_max: float | None = None
    keywords: str = ""

    def matches(self, account: Account) -> bool:
        if self.category and account.category and account.category.lower() != self.category.lower():
            return False
        if self.country and account.country and account.country.lower() != self.country.lower():
            return False
        if self.price_min is not None and account.price < self.price_min:
            return False
        if self.price_max is not None and account.price > self.price_max:
            return False
        if self.keywords:
            words = [w.strip().lower() for w in self.keywords.split(",") if w.strip()]
            title = (account.title or "").lower()
            if not any(w in title for w in words):
                return False
        return True


def create_niche(**fields) -> Niche:
    with get_session() as s:
        niche = Niche(**fields)
        s.add(niche)
        s.commit()
        s.refresh(niche)
        return niche


def update_niche(niche_id: int, **fields) -> Niche | None:
    with get_session() as s:
        niche = s.get(Niche, niche_id)
        if niche is None:
            return None
        for k, v in fields.items():
            if hasattr(niche, k):
                setattr(niche, k, v)
        s.commit()
        s.refresh(niche)
        return niche


def delete_niche(niche_id: int) -> bool:
    with get_session() as s:
        niche = s.get(Niche, niche_id)
        if niche is None:
            return False
        s.delete(niche)
        s.commit()
        return True


def list_niches() -> list[Niche]:
    with get_session() as s:
        return list(s.execute(select(Niche).order_by(Niche.name)).scalars())


def reclassify_accounts() -> dict[int, int]:
    """Пересчитывает привязку аккаунтов к нишам по текущим правилам.

    Возвращает словарь {niche_id: count_of_accounts}.
    """
    with get_session() as s:
        niches = list(s.execute(select(Niche)).scalars())
        accounts = list(s.execute(select(Account)).scalars())
        counts: dict[int, int] = {n.id: 0 for n in niches}

        for acc in accounts:
            best: Niche | None = None
            for n in niches:
                filters = NicheFilters(
                    category=n.category,
                    country=n.country,
                    price_min=n.price_min,
                    price_max=n.price_max,
                    keywords=n.keywords,
                )
                if filters.matches(acc):
                    best = n
                    break
            acc.niche_id = best.id if best else None
            if best:
                counts[best.id] += 1
                if (acc.cost or 0) == 0 and best.default_cost:
                    acc.cost = best.default_cost
        s.commit()
        return counts


def niche_summary(niche: Niche, sales_period_days: int = 30) -> dict:
    """Сводка по нише: активные, средние цены, продажи за период, остатки bump/stick."""
    from datetime import datetime, timedelta, timezone

    from app.db.models import Sale

    since = datetime.now(timezone.utc) - timedelta(days=sales_period_days)
    with get_session() as s:
        accounts = list(
            s.execute(
                select(Account).where(Account.niche_id == niche.id, Account.status == "active")
            ).scalars()
        )
        sales = list(
            s.execute(
                select(Sale).where(Sale.niche_id == niche.id, Sale.sold_at >= since)
            ).scalars()
        )

        total_price = sum(a.price for a in accounts)
        total_cost = sum(a.cost for a in accounts)
        bumps_left = sum(a.bumps_available for a in accounts)
        sticks_left = sum(a.sticks_available for a in accounts)
        return {
            "count": len(accounts),
            "avg_price": (total_price / len(accounts)) if accounts else 0.0,
            "avg_cost": (total_cost / len(accounts)) if accounts else 0.0,
            "expected_profit": total_price - total_cost,
            "sold_count": len(sales),
            "sold_revenue": sum(sale.price for sale in sales),
            "sold_profit": sum(sale.profit for sale in sales),
            "bumps_left": bumps_left,
            "sticks_left": sticks_left,
        }


def dump_filters(n: Niche) -> dict:
    return asdict(
        NicheFilters(
            category=n.category,
            country=n.country,
            price_min=n.price_min,
            price_max=n.price_max,
            keywords=n.keywords,
        )
    )
