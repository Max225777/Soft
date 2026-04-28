"""Работа с нишами: CRUD и сопоставление аккаунтов правилам."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Iterable

from sqlalchemy import select

from app.db.models import Account, Niche
from app.db.session import get_session


@dataclass
class NicheFilters:
    """Единственный фильтр ниши — приватный тег Lolzteam."""

    tag_id: int | None = None

    def matches(self, account: Account) -> bool:
        if self.tag_id is None:
            return False  # ниша без тега не классифицирует ничего
        tag_ids = {int(t.get("id")) for t in (account.tags or []) if isinstance(t, dict) and t.get("id")}
        return self.tag_id in tag_ids


def create_niche(**fields) -> Niche:
    with get_session() as s:
        niche = Niche(**fields)
        s.add(niche)
        s.commit()
        s.refresh(niche)
        return niche


def update_niche(niche_id: int, **fields) -> Niche | None:
    if niche_id is None:
        return None
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


def apply_niche_default_cost_to_sales(niche_id: int, default_cost: float) -> int:
    """Прописати ціну купівлі ніші у вже зафіксовані продажі цієї ніші
    (для тих де cost ще 0). Повертає скільки записів оновлено.
    """
    if default_cost <= 0:
        return 0
    from app.db.models import Sale
    updated = 0
    with get_session() as s:
        sales = list(
            s.execute(select(Sale).where(Sale.niche_id == niche_id, Sale.cost <= 0)).scalars()
        )
        for sale in sales:
            sale.cost = default_cost
            sale.profit = (sale.price or 0) - default_cost
            updated += 1
        s.commit()
    return updated


def reclassify_accounts() -> dict[int, int]:
    """Пересчитывает привязку аккаунтов к нишам по текущим правилам.

    Возвращает словарь {niche_id: count_of_accounts}.
    """
    from loguru import logger

    with get_session() as s:
        niches = list(s.execute(select(Niche)).scalars())
        accounts = list(s.execute(select(Account)).scalars())
        counts: dict[int, int] = {n.id: 0 for n in niches}

        ordered_niches = [n for n in niches if n.tag_id]
        unclassified = 0
        no_tag_niches = [n for n in niches if not n.tag_id]
        active_acc = 0

        logger.info(
            "reclassify: усього ніш = {}, з тегом = {}, без тега = {}; акаунтів = {}",
            len(niches), len(ordered_niches), len(no_tag_niches), len(accounts),
        )
        if no_tag_niches:
            logger.warning(
                "Ці ніші БЕЗ тега не класифікують нічого: {}",
                [n.name for n in no_tag_niches],
            )

        for acc in accounts:
            if acc.status == "active":
                active_acc += 1
            best: Niche | None = None
            for n in ordered_niches:
                if NicheFilters(tag_id=n.tag_id).matches(acc):
                    best = n
                    break
            acc.niche_id = best.id if best else None
            if best:
                counts[best.id] += 1
                if (acc.cost or 0) == 0 and best.default_cost:
                    acc.cost = best.default_cost
            else:
                unclassified += 1
        s.commit()

        # Підсумки
        logger.info(
            "reclassify результат: класифіковано={}, без класифікації={}, активних={}",
            sum(counts.values()), unclassified, active_acc,
        )
        for n in niches:
            tag_info = f"#{n.tag_id} ({n.tag_name})" if n.tag_id else "БЕЗ ТЕГУ"
            logger.info("  ніша '{}' → {} акк   tag={}", n.name, counts[n.id], tag_info)

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
    return asdict(NicheFilters(tag_id=n.tag_id))


# ---- Агрегаты для прогресс-индикаторов ----

def global_bumps_today(stuck: bool | None = None) -> int:
    """Сколько bump-действий (успешных) уже сделано сегодня по всем нишам."""
    from datetime import datetime, timezone
    from sqlalchemy import func

    from app.db.models import ActionLog

    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    with get_session() as s:
        stmt = (
            select(func.count(ActionLog.id))
            .where(
                ActionLog.action == "bump",
                ActionLog.level == "INFO",
                ActionLog.created_at >= today_start,
            )
        )
        if stuck is not None:
            stmt = stmt.join(Account, Account.item_id == ActionLog.item_id).where(Account.is_stuck.is_(stuck))
        return s.execute(stmt).scalar_one() or 0


def niche_bumps_today(niche_id: int, stuck: bool = False) -> int:
    from datetime import datetime, timezone
    from sqlalchemy import func

    from app.db.models import ActionLog

    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    with get_session() as s:
        stmt = (
            select(func.count(ActionLog.id))
            .join(Account, Account.item_id == ActionLog.item_id)
            .where(
                ActionLog.action == "bump",
                ActionLog.level == "INFO",
                ActionLog.created_at >= today_start,
                Account.niche_id == niche_id,
                Account.is_stuck.is_(stuck),
            )
        )
        return s.execute(stmt).scalar_one() or 0


def total_stuck_count() -> int:
    from sqlalchemy import func
    with get_session() as s:
        return s.execute(
            select(func.count(Account.id)).where(Account.is_stuck.is_(True), Account.status == "active")
        ).scalar_one() or 0
