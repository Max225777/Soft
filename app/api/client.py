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
            try:
                user_obj = self._me_cache.get("user") if isinstance(self._me_cache, dict) else None
                if isinstance(user_obj, dict):
                    bip = user_obj.get("bump_item_period")
                    user_id = user_obj.get("user_id") or user_obj.get("id")
                    logger.info("/me ok: user_id={}, bump_item_period={}", user_id, bip)
            except Exception:  # noqa: BLE001
                pass
        return self._me_cache

    def detect_limits(self) -> dict[str, int | None]:
        """Возвращает информацию о лимитах bump/stick.

        {
          "bumps_per_account": N | None,   # лимит bump-ов на 1 аккаунт в сутки
          "stick_slots_total": N | None,   # макс одновременно закреплённых
          "currently_stuck":   N           # сколько закреплено сейчас (фактически)
        }
        """
        result: dict[str, int | None] = {
            "bumps_per_account": None,
            "stick_slots_total": None,
            "currently_stuck": 0,
        }

        # /me — лимиты пользователя
        try:
            me = self.get_me()
        except ApiError:
            me = {}
        user = (me.get("user") if isinstance(me, dict) else None) or me
        if isinstance(user, dict):
            # bump_item_period (часы) — пауза между bump одного item.
            # 24 → 1 bump/сутки. 8 → 3 bump/сутки.
            bip = user.get("bump_item_period")
            if isinstance(bip, (int, float)) and bip > 0:
                result["bumps_per_account"] = max(1, int(round(24.0 / float(bip))))
                logger.info("/me .user.bump_item_period = {}h → bump/сутки = {}", bip, result["bumps_per_account"])

            for key in (
                "stick_slots", "stickSlots", "max_sticked_items", "maxStickedItems",
                "stickedItemsLimit", "sticky_items_limit", "max_sticky_items",
            ):
                v = user.get(key)
                if isinstance(v, (int, float)):
                    result["stick_slots_total"] = int(v)
                    break

        # /user/:id/items — top-level stickyItems = текущее количество закреплённых
        try:
            resp = self.list_my_items(page=1)
        except ApiError:
            resp = {}

        if isinstance(resp, dict):
            current_stuck = resp.get("stickyItems") or resp.get("sticky_items_count")
            if isinstance(current_stuck, (int, float)):
                result["currently_stuck"] = int(current_stuck)
                logger.info("items.stickyItems = {} (закреплено сейчас)", current_stuck)
            elif isinstance(resp.get("items"), list):
                items = resp.get("items") or []
                result["currently_stuck"] = sum(
                    1 for it in items
                    if isinstance(it, dict) and (it.get("is_sticky") or it.get("isSticky"))
                )

            # Если stick_slots_total не нашли — берём текущее как минимально возможное
            if result["stick_slots_total"] is None and result["currently_stuck"]:
                result["stick_slots_total"] = result["currently_stuck"]
                logger.info(
                    "stick_slots_total не найден в /me — используем фактическое количество закреплённых = {}",
                    result["currently_stuck"],
                )

        logger.info("detect_limits: {}", result)
        return result

    def list_my_items(self, page: int = 1, tag_id: int | None = None, **params: Any) -> dict[str, Any]:
        user = self.get_me().get("user") or self.get_me()
        user_id = user.get("user_id") or user.get("id")
        if not user_id:
            raise ApiError(0, "Не удалось определить user_id из /me")
        params.setdefault("page", page)
        # Перекриваємо дефолтні фільтри періоду — щоб отримати ВСІ items без
        # фільтрації за датою публікації (інакше API віддає лише останні N).
        params.setdefault("published_startDate", 0)
        params.setdefault("published_endDate", 0)
        params.setdefault("filter_by_published_date", 0)
        params.setdefault("filter_by_buyer_operation_date", 0)
        params.setdefault("show_unpublished", 1)
        if tag_id is not None:
            params["tag_id[]"] = [int(tag_id)]
        return self._submit("GET", f"user/{user_id}/items", priority=PRIORITY_HIGH, params=params).result()

    def create_tag(self, title: str) -> dict[str, Any]:
        """Створити новий приватний тег. POST /managing/tag/{title}"""
        path = f"managing/tag/{title}"
        return self._submit("POST", path, priority=PRIORITY_MEDIUM).result()

    def assign_tag(self, item_id: int, tag_id: int) -> dict[str, Any]:
        """Додати тег до item. POST /:itemId/tag з body tag_id."""
        return self._submit(
            "POST", f"{item_id}/tag",
            priority=PRIORITY_MEDIUM,
            json={"tag_id": int(tag_id)},
        ).result()

    def unassign_tag(self, item_id: int, tag_id: int) -> dict[str, Any]:
        """Зняти тег з item. DELETE /:itemId/tag з body tag_id."""
        return self._submit(
            "DELETE", f"{item_id}/tag",
            priority=PRIORITY_MEDIUM,
            json={"tag_id": int(tag_id)},
        ).result()

    def list_my_tags(self, max_pages: int = 50) -> list[dict[str, Any]]:
        """В Lolzteam Market нет отдельного endpoint для списка тегов —
        они приходят только в составе items.

        Делает несколько запросов /user/:id/items (пагинация), агрегирует
        уникальные теги. Останавливается на первой неполной/пустой странице
        либо при достижении max_pages.
        """
        seen: dict[int, str] = {}
        per_page_seen = 0
        for page in range(1, max_pages + 1):
            try:
                resp = self.list_my_items(page=page)
            except ApiError as exc:
                logger.warning("list_my_tags page={}: {}", page, exc)
                break
            items = resp.get("items") or resp.get("data") or []
            if not items:
                break
            per_page_seen = max(per_page_seen, len(items))
            for it in items:
                for tag in _extract_tags_from_item(it):
                    tid = tag["id"]
                    if tag["title"]:
                        seen[tid] = tag["title"]
                    elif tid not in seen:
                        seen[tid] = ""
            if len(items) < per_page_seen:
                break
        result = [{"id": k, "title": v} for k, v in sorted(seen.items())]
        logger.info("list_my_tags: всего уникальных тегов: {}", len(result))
        return result

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


def _extract_tags_from_item(item: dict[str, Any]) -> list[dict[str, Any]]:
    """Достаёт список приватных меток из объекта item (`/user/:id/items` ответ).

    Повертає всі теги — і default, і кастомні. isDefault зберігаємо в полі
    щоб UI міг показати ⚠.
    """
    raw = item.get("tags") or item.get("user_tags") or item.get("private_tags")
    out: list[dict[str, Any]] = []
    if isinstance(raw, dict):
        for k, v in raw.items():
            if not str(k).lstrip("-").isdigit():
                continue
            if isinstance(v, dict):
                title = v.get("title") or v.get("name") or ""
                is_default = bool(v.get("isDefault") or v.get("is_default"))
            else:
                title = v
                is_default = False
            out.append({"id": int(k), "title": str(title), "isDefault": is_default})
        return out
    if isinstance(raw, list):
        for t in raw:
            if isinstance(t, dict):
                tid = t.get("tag_id") or t.get("id")
                title = t.get("title") or t.get("name") or t.get("tag") or ""
                is_default = bool(t.get("isDefault") or t.get("is_default"))
                if tid:
                    out.append({"id": int(tid), "title": str(title), "isDefault": is_default})
            elif isinstance(t, int):
                out.append({"id": t, "title": "", "isDefault": False})
            elif isinstance(t, str) and t.lstrip("-").isdigit():
                out.append({"id": int(t), "title": "", "isDefault": False})
        return out
    raw_ids = item.get("tag_ids") or item.get("tagIds")
    if isinstance(raw_ids, list):
        return [
            {"id": int(x), "title": "", "isDefault": False}
            for x in raw_ids
            if str(x).lstrip("-").isdigit()
        ]
    return []
