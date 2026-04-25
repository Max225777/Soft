"""Кеш приватных тегов Lolzteam Market.

Теги получаются из двух источников (в порядке убывания приоритета):
1. API: client.list_my_tags() — если эндпоинт доступен
2. Локально: агрегация по полю Account.tags (всё что мы видели в items)
"""

from __future__ import annotations

from sqlalchemy import select

from app.api.client import LolzMarketClient
from app.db.models import Account
from app.db.session import get_session


def aggregate_tags_from_accounts() -> list[dict]:
    """Достаём уникальные теги из локальных аккаунтов."""
    seen: dict[int, str] = {}
    with get_session() as s:
        for acc in s.execute(select(Account)).scalars():
            for tag in (acc.tags or []):
                if isinstance(tag, dict):
                    tid = tag.get("id")
                    title = tag.get("title") or ""
                    if tid is not None:
                        # сохраняем непустое название
                        if not seen.get(int(tid)) or title:
                            seen[int(tid)] = title
    return [{"id": tid, "title": t} for tid, t in sorted(seen.items())]


def fetch_tags(client: LolzMarketClient | None) -> list[dict]:
    """Сначала пробуем API, затем агрегируем из локальной БД."""
    api_tags: list[dict] = []
    if client and client.token:
        try:
            api_tags = client.list_my_tags()
        except Exception:  # noqa: BLE001
            api_tags = []

    local_tags = aggregate_tags_from_accounts()

    # Сливаем по id
    merged: dict[int, str] = {t["id"]: t["title"] for t in local_tags}
    for t in api_tags:
        if t["title"]:
            merged[t["id"]] = t["title"]
        elif t["id"] not in merged:
            merged[t["id"]] = ""
    return [{"id": k, "title": v} for k, v in sorted(merged.items())]
