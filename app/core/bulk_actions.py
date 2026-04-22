"""Массовые действия над аккаунтами."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable

from loguru import logger
from sqlalchemy import select

from app.api.client import ApiError, LolzMarketClient
from app.db.models import Account, ActionLog
from app.db.session import get_session


def _log(session, action: str, item_id: int | None, message: str, level: str = "INFO", details: dict | None = None) -> None:
    session.add(
        ActionLog(
            action=action,
            item_id=item_id,
            message=message,
            level=level,
            details=details or {},
        )
    )


def bump_items(client: LolzMarketClient, item_ids: Iterable[int]) -> dict[int, str]:
    results: dict[int, str] = {}
    now = datetime.now(timezone.utc)
    with get_session() as s:
        for item_id in item_ids:
            acc = s.execute(select(Account).where(Account.item_id == item_id)).scalar_one_or_none()
            if acc and acc.bumps_available <= 0:
                results[item_id] = "skipped: no bumps left"
                _log(s, "bump", item_id, "Пропущено: лимит поднятий исчерпан", level="WARNING")
                continue
            try:
                client.bump_item(item_id)
                if acc:
                    acc.bumps_available = max(0, acc.bumps_available - 1)
                    acc.last_bumped_at = now
                results[item_id] = "ok"
                _log(s, "bump", item_id, "Поднятие выполнено")
            except ApiError as exc:
                results[item_id] = f"error: {exc}"
                _log(s, "bump", item_id, str(exc), level="ERROR")
                logger.error("Ошибка поднятия {}: {}", item_id, exc)
        s.commit()
    return results


def stick_items(client: LolzMarketClient, item_ids: Iterable[int]) -> dict[int, str]:
    results: dict[int, str] = {}
    now = datetime.now(timezone.utc)
    with get_session() as s:
        for item_id in item_ids:
            acc = s.execute(select(Account).where(Account.item_id == item_id)).scalar_one_or_none()
            if acc and acc.sticks_available <= 0:
                results[item_id] = "skipped: no sticks left"
                _log(s, "stick", item_id, "Пропущено: лимит закреплений исчерпан", level="WARNING")
                continue
            try:
                client.stick_item(item_id)
                if acc:
                    acc.sticks_available = max(0, acc.sticks_available - 1)
                    acc.last_stuck_at = now
                results[item_id] = "ok"
                _log(s, "stick", item_id, "Закрепление выполнено")
            except ApiError as exc:
                results[item_id] = f"error: {exc}"
                _log(s, "stick", item_id, str(exc), level="ERROR")
        s.commit()
    return results


def change_prices_by_percent(client: LolzMarketClient, item_ids: Iterable[int], percent: float) -> dict[int, str]:
    results: dict[int, str] = {}
    factor = 1.0 + percent / 100.0
    with get_session() as s:
        for item_id in item_ids:
            acc = s.execute(select(Account).where(Account.item_id == item_id)).scalar_one_or_none()
            if acc is None:
                results[item_id] = "not found"
                continue
            new_price = round(acc.price * factor, 2)
            try:
                client.update_item(item_id, price=new_price)
                acc.price = new_price
                results[item_id] = f"ok ({new_price})"
                _log(s, "price_update", item_id, f"Цена: {acc.price:.2f} → {new_price:.2f}")
            except ApiError as exc:
                results[item_id] = f"error: {exc}"
                _log(s, "price_update", item_id, str(exc), level="ERROR")
        s.commit()
    return results


def apply_markup(client: LolzMarketClient, item_ids: Iterable[int], markup: float) -> dict[int, str]:
    """Наценка в абсолютной сумме: new_price = cost + markup."""
    results: dict[int, str] = {}
    with get_session() as s:
        for item_id in item_ids:
            acc = s.execute(select(Account).where(Account.item_id == item_id)).scalar_one_or_none()
            if acc is None:
                results[item_id] = "not found"
                continue
            if (acc.cost or 0) <= 0:
                results[item_id] = "skipped: no cost"
                _log(s, "markup", item_id, "Нет себестоимости для расчёта наценки", level="WARNING")
                continue
            new_price = round(acc.cost + markup, 2)
            try:
                client.update_item(item_id, price=new_price)
                acc.price = new_price
                results[item_id] = f"ok ({new_price})"
                _log(s, "markup", item_id, f"Применена наценка +{markup:.2f} → {new_price:.2f}")
            except ApiError as exc:
                results[item_id] = f"error: {exc}"
                _log(s, "markup", item_id, str(exc), level="ERROR")
        s.commit()
    return results


def add_public_label(client: LolzMarketClient, item_ids: Iterable[int], label: str) -> dict[int, str]:
    results: dict[int, str] = {}
    with get_session() as s:
        for item_id in item_ids:
            acc = s.execute(select(Account).where(Account.item_id == item_id)).scalar_one_or_none()
            if acc is None:
                results[item_id] = "not found"
                continue
            if label in (acc.title or ""):
                results[item_id] = "skipped: already labeled"
                continue
            new_title = f"{label} {acc.title}".strip()
            try:
                client.update_item(item_id, title=new_title)
                acc.title = new_title
                results[item_id] = "ok"
                _log(s, "label_add", item_id, f"Добавлена метка: {label}")
            except ApiError as exc:
                results[item_id] = f"error: {exc}"
                _log(s, "label_add", item_id, str(exc), level="ERROR")
        s.commit()
    return results


def remove_public_label(client: LolzMarketClient, item_ids: Iterable[int], label: str) -> dict[int, str]:
    results: dict[int, str] = {}
    with get_session() as s:
        for item_id in item_ids:
            acc = s.execute(select(Account).where(Account.item_id == item_id)).scalar_one_or_none()
            if acc is None or label not in (acc.title or ""):
                results[item_id] = "skipped"
                continue
            new_title = (acc.title or "").replace(label, "").strip()
            try:
                client.update_item(item_id, title=new_title)
                acc.title = new_title
                results[item_id] = "ok"
                _log(s, "label_remove", item_id, f"Удалена метка: {label}")
            except ApiError as exc:
                results[item_id] = f"error: {exc}"
                _log(s, "label_remove", item_id, str(exc), level="ERROR")
        s.commit()
    return results


def set_cost(item_ids: Iterable[int], cost: float) -> dict[int, str]:
    results: dict[int, str] = {}
    with get_session() as s:
        for item_id in item_ids:
            acc = s.execute(select(Account).where(Account.item_id == item_id)).scalar_one_or_none()
            if acc is None:
                results[item_id] = "not found"
                continue
            acc.cost = float(cost)
            results[item_id] = "ok"
            _log(s, "cost_update", item_id, f"Себестоимость → {cost:.2f}")
        s.commit()
    return results


def deactivate_items(client: LolzMarketClient, item_ids: Iterable[int]) -> dict[int, str]:
    results: dict[int, str] = {}
    with get_session() as s:
        for item_id in item_ids:
            try:
                client.delete_item(item_id)
                acc = s.execute(select(Account).where(Account.item_id == item_id)).scalar_one_or_none()
                if acc:
                    acc.status = "inactive"
                results[item_id] = "ok"
                _log(s, "deactivate", item_id, "Снят с продажи")
            except ApiError as exc:
                results[item_id] = f"error: {exc}"
                _log(s, "deactivate", item_id, str(exc), level="ERROR")
        s.commit()
    return results


def bind_to_niche(item_ids: Iterable[int], niche_id: int, priority: bool = True) -> dict[int, str]:
    results: dict[int, str] = {}
    with get_session() as s:
        for item_id in item_ids:
            acc = s.execute(select(Account).where(Account.item_id == item_id)).scalar_one_or_none()
            if acc is None:
                results[item_id] = "not found"
                continue
            acc.niche_id = niche_id
            acc.is_priority = priority
            results[item_id] = "ok"
            _log(s, "bind_niche", item_id, f"Привязан к нише #{niche_id}, priority={priority}")
        s.commit()
    return results
