"""Кеш приватных тегов Lolzteam Market.

Теги получаются из двух источников (в порядке убывания приоритета):
1. API: client.list_my_tags() — если эндпоинт доступен
2. Локально: агрегация по полю Account.tags (всё что мы видели в items)
"""

from __future__ import annotations

from loguru import logger
from sqlalchemy import select

from app.api.client import LolzMarketClient
from app.db.models import Account
from app.db.session import get_session


def aggregate_tags_from_accounts() -> list[dict]:
    """Достаём уникальные теги из локальных аккаунтов.

    Каждый тег: {"id": int, "title": str, "isDefault": bool}.
    """
    seen: dict[int, dict] = {}
    with get_session() as s:
        for acc in s.execute(select(Account)).scalars():
            for tag in (acc.tags or []):
                if not isinstance(tag, dict):
                    continue
                tid = tag.get("id")
                if tid is None:
                    continue
                tid = int(tid)
                title = tag.get("title") or ""
                is_default = bool(tag.get("isDefault"))
                if tid not in seen or (title and not seen[tid].get("title")):
                    seen[tid] = {"id": tid, "title": title, "isDefault": is_default}
                elif is_default and not seen[tid].get("isDefault"):
                    seen[tid]["isDefault"] = True
    return list(seen.values())


def fetch_tags(client: LolzMarketClient | None) -> list[dict]:
    """Швидко: спочатку беремо з локальної БД (Account.tags), і ТІЛЬКИ
    якщо локально пусто — звертаємось до API (повільно, ~25 сек)."""
    local_tags = aggregate_tags_from_accounts()
    if local_tags:
        logger.info("fetch_tags: знайдено {} тегів локально (без API запиту)", len(local_tags))
        return local_tags

    logger.info("fetch_tags: локально пусто, тягну з API…")
    if client and client.token:
        try:
            api_tags = client.list_my_tags()
            logger.info("fetch_tags: з API отримано {} тегів", len(api_tags))
            return api_tags
        except Exception as exc:  # noqa: BLE001
            logger.warning("fetch_tags: помилка API: {}", exc)
    return []
