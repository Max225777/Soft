"""Отслеживание продаж: сравнение снимков списка аккаунтов."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable

from loguru import logger
from sqlalchemy import select

from app.api.client import _extract_tags_from_item
from app.db.models import Account, PriceHistory, Sale
from app.db.session import get_session


def sync_accounts_snapshot(items: Iterable[dict]) -> dict:
    """Синхронизирует кеш аккаунтов с актуальным списком из API.

    Возвращает сводку: {added, updated, sold, price_changes}.
    """
    now = datetime.now(timezone.utc)
    added = updated = sold = 0
    price_changes = 0

    items_by_id: dict[int, dict] = {int(it["item_id"]): it for it in items if it.get("item_id")}

    # --- диагностика тегов и лимитов bump/stick ---
    if items_by_id:
        sample = next(iter(items_by_id.values()))
        tag_keys = [k for k in sample.keys() if "tag" in k.lower()]
        bump_keys = [k for k in sample.keys() if "bump" in k.lower()]
        stick_keys = [k for k in sample.keys() if "stick" in k.lower() or "stuck" in k.lower()]
        all_keys = sorted(sample.keys())
        logger.info(
            "Получено items: {}; tag-keys={}; bump-keys={}; stick-keys={}; пример item_id={}",
            len(items_by_id),
            tag_keys,
            bump_keys,
            stick_keys,
            sample.get("item_id"),
        )
        for k in tag_keys + bump_keys + stick_keys:
            val = sample[k]
            logger.info("  {} = {}", k, str(val)[:200])
        if not (tag_keys or bump_keys or stick_keys):
            logger.warning(
                "В ответе API нет полей с tag/bump/stick. Все ключи первого item: {}",
                all_keys,
            )

    with get_session() as s:
        existing = {a.item_id: a for a in s.execute(select(Account)).scalars()}

        # новые и обновлённые
        for item_id, payload in items_by_id.items():
            acc = existing.get(item_id)
            new_price = float(payload.get("price") or 0)
            tags = _extract_tags(payload)
            bumps_left = _parse_bumps_available(payload)
            is_stuck = _parse_is_stuck(payload)
            if acc is None:
                acc = Account(
                    item_id=item_id,
                    title=str(payload.get("title") or ""),
                    category=str(payload.get("category_name") or payload.get("category") or ""),
                    country=str(payload.get("item_origin") or payload.get("country") or ""),
                    price=new_price,
                    amount=int(payload.get("amount") or 1),
                    status=str(payload.get("item_state") or "active"),
                    tags=tags,
                    bumps_available=bumps_left if bumps_left is not None else 3,
                    is_stuck=is_stuck,
                    raw=payload,
                )
                s.add(acc)
                s.flush()
                s.add(PriceHistory(item_id=item_id, price=new_price, changed_at=now))
                added += 1
            else:
                if abs(acc.price - new_price) > 1e-6:
                    price_changes += 1
                    s.add(PriceHistory(item_id=item_id, price=new_price, changed_at=now))
                acc.title = str(payload.get("title") or acc.title)
                acc.category = str(payload.get("category_name") or payload.get("category") or acc.category)
                acc.country = str(payload.get("item_origin") or payload.get("country") or acc.country)
                acc.price = new_price
                acc.amount = int(payload.get("amount") or acc.amount)
                acc.status = str(payload.get("item_state") or acc.status)
                acc.tags = tags
                if bumps_left is not None:
                    acc.bumps_available = bumps_left
                acc.is_stuck = is_stuck
                acc.raw = payload
                updated += 1

        # проданные / пропавшие
        for item_id, acc in list(existing.items()):
            if item_id in items_by_id or acc.status in {"sold", "deleted"}:
                continue
            _register_sale(s, acc, now)
            acc.status = "sold"
            sold += 1

        s.commit()

    summary = {"added": added, "updated": updated, "sold": sold, "price_changes": price_changes}
    logger.info("Синхронизация аккаунтов: {}", summary)
    return summary


def _extract_tags(payload: dict) -> list[dict]:
    """Тонкая обёртка над общим парсером (см. app/api/client._extract_tags_from_item)."""
    return _extract_tags_from_item(payload)


def _parse_bumps_available(payload: dict) -> int | None:
    """Сколько поднятий ещё доступно для аккаунта по данным API.

    Lolzteam в разных полях возвращает информацию: bumpsAvailable / canBump (bool) /
    bumps_left / bumpRemaining. Возвращаем None если не нашли — оставим текущее значение.
    """
    for key in ("bumpsAvailable", "bumps_available", "bumps_left", "bumpRemaining", "bump_remaining"):
        val = payload.get(key)
        if isinstance(val, (int, float)):
            return int(val)
    can_bump = payload.get("canBump") or payload.get("can_bump")
    if isinstance(can_bump, bool):
        return 1 if can_bump else 0
    return None


def _parse_is_stuck(payload: dict) -> bool:
    """Закреплён ли аккаунт сейчас (по данным API)."""
    for key in ("is_sticky", "isSticky", "is_stuck", "sticked", "is_pinned"):
        val = payload.get(key)
        if isinstance(val, bool):
            return val
        if isinstance(val, int):
            return bool(val)
    return False


def _register_sale(session, acc: Account, ts: datetime) -> None:
    sale = Sale(
        item_id=acc.item_id,
        title=acc.title,
        price=acc.price,
        cost=acc.cost,
        profit=(acc.price or 0) - (acc.cost or 0),
        niche_id=acc.niche_id,
        sold_at=ts,
    )
    session.add(sale)


def recent_sales(limit: int = 50) -> list[Sale]:
    with get_session() as s:
        stmt = select(Sale).order_by(Sale.sold_at.desc()).limit(limit)
        return list(s.execute(stmt).scalars())
