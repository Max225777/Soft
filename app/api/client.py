"""Клиент Lolzteam Market API.

Оборачивает httpx-запросы и отправляет их через `RequestQueue`, соблюдая rate-limits.
Повторяет запросы с экспоненциальной задержкой при 429/5xx (до `max_retries` попыток).
"""

from __future__ import annotations

import time
from concurrent.futures import Future
from typing import Any

import httpx
import json
from loguru import logger

from app.api.queue import PRIORITY_HIGH, PRIORITY_LOW, PRIORITY_MEDIUM, RequestQueue


class ApiError(Exception):
    def __init__(self, status: int, message: str, payload: Any = None):
        super().__init__(f"{status}: {message}")
        self.status = status
        self.message = message
        self.payload = payload


class LolzMarketClient:
    def __init__(
        self,
        token: str,
        base_url: str = "https://prod-api.lzt.market/",
        lang: str = "ru",
        timeout: float = 30.0,
        queue: RequestQueue | None = None,
        max_retries: int = 3,
    ) -> None:
        self.token = token
        self.base_url = base_url.rstrip("/") + "/"
        self.lang = lang
        self.max_retries = max_retries
        self.queue = queue or RequestQueue()
        self._client = httpx.Client(
            base_url=self.base_url,
            timeout=timeout,
            headers=self._default_headers(),
        )
        self._me_cache: dict[str, Any] | None = None

    def close(self) -> None:
        self._client.close()

    def update_token(self, token: str) -> None:
        self.token = token
        self._client.headers["Authorization"] = f"Bearer {token}"
        self._me_cache = None

    # ---------- helpers ----------
    def _default_headers(self) -> dict[str, str]:
        headers = {"Accept": "application/json", "Accept-Language": self.lang}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        url = path if path.startswith("http") else path.lstrip("/")
        attempt = 0
        while True:
            attempt += 1
            try:
                resp = self._client.request(method, url, **kwargs)
            except httpx.RequestError as exc:
                logger.warning("HTTP ошибка ({}): {}", method, exc)
                if attempt > self.max_retries:
                    raise ApiError(0, str(exc)) from exc
                time.sleep(2 ** attempt)
                continue

            if resp.status_code == 429:
                wait = _retry_after(resp) or (2 ** attempt)
                logger.warning("429 Too Many Requests — пауза {:.1f}s", wait)
                if attempt > self.max_retries:
                    raise ApiError(429, "rate limit exceeded", _safe_json(resp))
                time.sleep(wait)
                continue

            if 500 <= resp.status_code < 600:
                if attempt > self.max_retries:
                    raise ApiError(resp.status_code, "server error", _safe_json(resp))
                time.sleep(2 ** attempt)
                continue

            if resp.status_code >= 400:
                raise ApiError(resp.status_code, resp.text[:200], _safe_json(resp))

            return _safe_json(resp) or {}

    def _submit(
        self,
        method: str,
        path: str,
        *,
        priority: int = PRIORITY_MEDIUM,
        is_search: bool = False,
        **kwargs: Any,
    ) -> Future:
        return self.queue.submit(
            lambda: self._request(method, path, **kwargs),
            priority=priority,
            is_search=is_search,
        )

    # ---------- API methods ----------
    def get_me(self) -> dict[str, Any]:
        if self._me_cache is None:
            self._me_cache = self._submit("GET", "me", priority=PRIORITY_HIGH).result()
        return self._me_cache

    def list_my_items(self, page: int = 1, tag_id: int | None = None, **params: Any) -> dict[str, Any]:
        user = self.get_me().get("user") or self.get_me()
        user_id = user.get("user_id") or user.get("id")
        if not user_id:
            raise ApiError(0, "Не удалось определить user_id из /me")
        params.setdefault("page", page)
        if tag_id is not None:
            # Lolzteam ожидает tag_id[] — массив. httpx сам сериализует list в query.
            params["tag_id[]"] = [int(tag_id)]
        return self._submit("GET", f"user/{user_id}/items", priority=PRIORITY_HIGH, params=params).result()

    def list_my_tags(self) -> list[dict[str, Any]]:
        """Возвращает приватные теги текущего пользователя (с lzt.market).

        Перебирает несколько кандидатных эндпоинтов — в разных версиях API
        ответ может приходить с разных URL. Возвращает [{id, title}, …] или [].
        """
        candidates = ("me/tags", "managing/tags", "tag/list", "user/tags", "tags")
        for path in candidates:
            try:
                logger.info("GET тегов: пробую {}", path)
                resp = self._submit("GET", path, priority=PRIORITY_LOW).result()
                if isinstance(resp, dict):
                    keys = list(resp.keys())[:10]
                    logger.info("  ответ от {}: keys={}", path, keys)
                else:
                    logger.info("  ответ от {}: type={}, len={}", path, type(resp).__name__, len(resp) if hasattr(resp, "__len__") else "?")
                tags = _parse_tags(resp)
                if tags:
                    logger.info("✓ Получено тегов через {}: {}", path, len(tags))
                    return tags
                logger.info("  {} вернул 0 тегов после парсинга", path)
            except ApiError as exc:
                logger.info("  {} → {}", path, exc)
                continue
        logger.warning(
            "Ни один из эндпоинтов тегов не сработал. Теги будем брать из item.tags локально."
        )
        return []

    def get_item(self, item_id: int) -> dict[str, Any]:
        return self._submit("GET", f"{item_id}", priority=PRIORITY_MEDIUM).result()

    def bump_item(self, item_id: int) -> dict[str, Any]:
        return self._submit("POST", f"{item_id}/bump", priority=PRIORITY_MEDIUM).result()

    def stick_item(self, item_id: int) -> dict[str, Any]:
        return self._submit("POST", f"{item_id}/stick", priority=PRIORITY_MEDIUM).result()

    def update_item(self, item_id: int, **fields: Any) -> dict[str, Any]:
        return self._submit("PUT", f"{item_id}", priority=PRIORITY_MEDIUM, json=fields).result()

    def delete_item(self, item_id: int, reason: str | None = None) -> dict[str, Any]:
        params = {"reason": reason} if reason else None
        return self._submit("DELETE", f"{item_id}", priority=PRIORITY_MEDIUM, params=params).result()

    def list_categories(self) -> dict[str, Any]:
        return self._submit("GET", "categories", priority=PRIORITY_LOW).result()

    def search(self, category: str, **params: Any) -> dict[str, Any]:
        # Поисковые эндпоинты — отдельный лимит 20/мин
        return self._submit("GET", f"{category}", priority=PRIORITY_LOW, is_search=True, params=params).result()


def _safe_json(resp: httpx.Response) -> dict[str, Any] | None:
    try:
        return resp.json()
    except ValueError:
        return None


def _retry_after(resp: httpx.Response) -> float | None:
    header = resp.headers.get("Retry-After")
    if not header:
        return None
    try:
        return float(header)
    except ValueError:
        return None


def _parse_tags(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, dict):
        for key in ("tags", "data", "items"):
            v = payload.get(key)
            if isinstance(v, list):
                payload = v
                break
        else:
            return []
    if not isinstance(payload, list):
        return []
    out: list[dict[str, Any]] = []
    for t in payload:
        if isinstance(t, dict):
            tid = t.get("tag_id") or t.get("id")
            title = t.get("title") or t.get("name") or t.get("tag") or ""
            if tid:
                out.append({"id": int(tid), "title": str(title)})
    return out
