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
    """Сначала пробуем API, затем агрегируем из локальной БД."""
    api_tags: list[dict] = []
    if client and client.token:
        try:
            api_tags = client.list_my_tags()
            logger.info("fetch_tags: с API получено {} тегов", len(api_tags))
        except Exception as exc:  # noqa: BLE001
            logger.warning("fetch_tags: ошибка вызова API: {}", exc)
            api_tags = []
    else:
        logger.info("fetch_tags: нет токена, пропускаем API")

    local_tags = aggregate_tags_from_accounts()
    logger.info("fetch_tags: из локальной БД (Account.tags) собрано {} уникальных тегов", len(local_tags))

    merged: dict[int, dict] = {t["id"]: dict(t) for t in local_tags}
    for t in api_tags:
        tid = t["id"]
        existing = merged.get(tid, {"id": tid, "title": "", "isDefault": False})
        if t.get("title"):
            existing["title"] = t["title"]
        if t.get("isDefault"):
            existing["isDefault"] = True
        merged[tid] = existing

    result = sorted(merged.values(), key=lambda x: x["id"])
    logger.info("fetch_tags: итого после слияния — {} тегов", len(result))
    return result
