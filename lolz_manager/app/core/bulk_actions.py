"""Дії над аккаунтами які реально викликає cycle: bump і stick."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable

from loguru import logger
from sqlalchemy import select

from app.api.client import ApiError, LolzMarketClient
from app.db.models import Account, ActionLog
from app.db.session import get_session


def _log(session, action: str, item_id: int | None, message: str, level: str = "INFO") -> None:
    session.add(ActionLog(action=action, item_id=item_id, message=message, level=level))


def bump_items(client: LolzMarketClient, item_ids: Iterable[int]) -> dict[int, str]:
    """Підняти список items. Повертає {item_id: 'ok' | 'error: ...' | 'skipped: ...'}."""
    results: dict[int, str] = {}
    now = datetime.now(timezone.utc)
    with get_session() as s:
        for item_id in item_ids:
            acc = s.execute(select(Account).where(Account.item_id == item_id)).scalar_one_or_none()
            if acc and acc.bumps_available <= 0:
                results[item_id] = "skipped: no bumps left"
                _log(s, "bump", item_id, "Пропущено: ліміт підйомів вичерпано", level="WARNING")
                continue
            try:
                client.bump_item(item_id)
                if acc:
                    acc.bumps_available = max(0, acc.bumps_available - 1)
                    acc.last_bumped_at = now
                results[item_id] = "ok"
                _log(s, "bump", item_id, "Підйом виконаний")
            except ApiError as exc:
                results[item_id] = f"error: {exc}"
                if acc and exc.status in (400, 403, 404):
                    acc.bumps_available = 0
                _log(s, "bump", item_id, str(exc)[:200], level="ERROR")
                logger.error("Помилка підйому {}: {}", item_id, exc)
        s.commit()
    return results


def stick_items(client: LolzMarketClient, item_ids: Iterable[int]) -> dict[int, str]:
    """Закріпити список items."""
    results: dict[int, str] = {}
    now = datetime.now(timezone.utc)
    with get_session() as s:
        for item_id in item_ids:
            acc = s.execute(select(Account).where(Account.item_id == item_id)).scalar_one_or_none()
            if acc and acc.sticks_available <= 0:
                results[item_id] = "skipped: no sticks left"
                _log(s, "stick", item_id, "Пропущено: ліміт закріплень вичерпано", level="WARNING")
                continue
            try:
                client.stick_item(item_id)
                if acc:
                    acc.sticks_available = max(0, acc.sticks_available - 1)
                    acc.last_stuck_at = now
                    acc.is_stuck = True
                results[item_id] = "ok"
                _log(s, "stick", item_id, "Закріплення виконане")
            except ApiError as exc:
                results[item_id] = f"error: {exc}"
                if acc and exc.status in (400, 403, 404):
                    acc.sticks_available = 0
                _log(s, "stick", item_id, str(exc)[:200], level="ERROR")
        s.commit()
    return results
