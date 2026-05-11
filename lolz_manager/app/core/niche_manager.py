"""Робота з нішею: створення/оновлення Default-ніші + класифікація акк за тегом."""

from __future__ import annotations

from dataclasses import dataclass

from loguru import logger
from sqlalchemy import select

from app.db.models import Account, Niche
from app.db.session import get_session


@dataclass
class NicheFilters:
    """Єдиний критерій ніші — приватний тег Lolzteam."""

    tag_id: int | None = None

    def matches(self, account: Account) -> bool:
        if self.tag_id is None:
            return False
        tag_ids = {
            int(t.get("id"))
            for t in (account.tags or [])
            if isinstance(t, dict) and t.get("id")
        }
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
        # Захист від асинхронного бага UI: не перетираємо існуючий tag_id на None
        if "tag_id" in fields and fields["tag_id"] is None and niche.tag_id is not None:
            logger.warning(
                "update_niche: ігнорую спробу перетерти tag_id={} на None у ніші '{}'",
                niche.tag_id, niche.name,
            )
            fields.pop("tag_id", None)
            fields.pop("tag_name", None)
        for k, v in fields.items():
            if hasattr(niche, k):
                setattr(niche, k, v)
        s.commit()
        s.refresh(niche)
        return niche


def reclassify_accounts() -> dict[int, int]:
    """Перерахує niche_id для всіх акк за тегом ніш. Повертає {niche_id: count}."""
    with get_session() as s:
        niches = list(s.execute(select(Niche)).scalars())
        accounts = list(s.execute(select(Account)).scalars())
        counts: dict[int, int] = {n.id: 0 for n in niches}
        ordered = [n for n in niches if n.tag_id]

        for acc in accounts:
            best: Niche | None = None
            for n in ordered:
                if NicheFilters(tag_id=n.tag_id).matches(acc):
                    best = n
                    break
            acc.niche_id = best.id if best else None
            if best:
                counts[best.id] += 1
        s.commit()

        active = sum(1 for a in accounts if a.status == "active")
        logger.info(
            "reclassify: {} акк, {} активних, класифіковано {}",
            len(accounts), active, sum(counts.values()),
        )
        for n in niches:
            logger.info(
                "  '{}' → {} акк (tag={})",
                n.name, counts[n.id], f"#{n.tag_id} {n.tag_name}" if n.tag_id else "—",
            )
        return counts


# ---- агрегати для UI/прогресу ----

def global_bumps_today(stuck: bool | None = None) -> int:
    """Скільки успішних bump-дій сьогодні (опційно фільтр по is_stuck акк)."""
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
            stmt = stmt.join(Account, Account.item_id == ActionLog.item_id).where(
                Account.is_stuck.is_(stuck)
            )
        return s.execute(stmt).scalar_one() or 0


def total_stuck_count() -> int:
    """Скільки акк зараз закріплені (active)."""
    from sqlalchemy import func

    with get_session() as s:
        return (
            s.execute(
                select(func.count(Account.id)).where(
                    Account.is_stuck.is_(True), Account.status == "active"
                )
            ).scalar_one()
            or 0
        )
