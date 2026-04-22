"""20-минутный цикл обновления."""

from __future__ import annotations

import threading
from datetime import datetime, time as dtime, timezone
from typing import Callable

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from loguru import logger
from sqlalchemy import select

from app.api.client import ApiError, LolzMarketClient
from app.core.bulk_actions import bump_items, stick_items
from app.core.niche_manager import reclassify_accounts
from app.core.sale_tracker import sync_accounts_snapshot
from app.db.models import Account, Niche
from app.db.session import get_session


class UpdateCycle:
    def __init__(
        self,
        client: LolzMarketClient,
        interval_minutes: int = 20,
        on_tick: Callable[[dict], None] | None = None,
    ) -> None:
        self.client = client
        self.interval_minutes = interval_minutes
        self.on_tick = on_tick
        self._scheduler = BackgroundScheduler(timezone="UTC")
        self._lock = threading.Lock()
        self._last_tick: datetime | None = None
        self._last_summary: dict = {}

    # ---------- lifecycle ----------
    def start(self, run_now: bool = True) -> None:
        if self._scheduler.running:
            return
        self._scheduler.add_job(
            self._safe_tick,
            IntervalTrigger(minutes=self.interval_minutes),
            id="update_cycle",
            replace_existing=True,
            next_run_time=datetime.now(timezone.utc) if run_now else None,
        )
        self._scheduler.start()
        logger.info("Цикл обновления запущен (каждые {} мин)", self.interval_minutes)

    def stop(self) -> None:
        if self._scheduler.running:
            self._scheduler.shutdown(wait=False)
            logger.info("Цикл обновления остановлен")

    def trigger_now(self) -> None:
        threading.Thread(target=self._safe_tick, daemon=True, name="CycleManual").start()

    # ---------- public getters ----------
    @property
    def last_tick(self) -> datetime | None:
        return self._last_tick

    @property
    def last_summary(self) -> dict:
        return dict(self._last_summary)

    def next_tick(self) -> datetime | None:
        try:
            job = self._scheduler.get_job("update_cycle")
            return job.next_run_time if job else None
        except Exception:
            return None

    # ---------- core tick ----------
    def _safe_tick(self) -> None:
        if not self._lock.acquire(blocking=False):
            logger.warning("Цикл уже выполняется — пропускаем запуск")
            return
        try:
            self._tick()
        except Exception as exc:  # noqa: BLE001
            logger.exception("Ошибка в цикле обновления: {}", exc)
        finally:
            self._lock.release()

    def _tick(self) -> None:
        started = datetime.now(timezone.utc)
        logger.info("=== TICK START {} ===", started.isoformat())

        # 1. Проверка API + получение списка моих аккаунтов
        try:
            me = self.client.get_me()
            logger.debug("API /me ok: user_id={}", (me.get("user") or {}).get("user_id") or me.get("user_id"))
        except ApiError as exc:
            logger.error("API недоступен: {}", exc)
            self._last_summary = {"error": str(exc)}
            return

        items = self._fetch_all_items()

        # 2. Синхронизация и фиксация продаж
        sync_summary = sync_accounts_snapshot(items)

        # 3. Реклассификация аккаунтов по нишам
        reclassify_accounts()

        # 4. Ежедневный сброс счётчиков bumps/sticks
        self._reset_daily_limits()

        # 5. Автоматические действия по нишам
        auto_summary = self._run_auto_actions()

        self._last_tick = datetime.now(timezone.utc)
        self._last_summary = {
            **sync_summary,
            "auto": auto_summary,
            "duration_sec": (self._last_tick - started).total_seconds(),
        }
        logger.info("=== TICK END {} ===", self._last_summary)

        if self.on_tick:
            try:
                self.on_tick(self._last_summary)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Ошибка в on_tick: {}", exc)

    def _fetch_all_items(self) -> list[dict]:
        all_items: list[dict] = []
        page = 1
        while True:
            try:
                resp = self.client.list_my_items(page=page)
            except ApiError as exc:
                logger.error("Ошибка получения списка аккаунтов (page={}): {}", page, exc)
                break

            items = resp.get("items") or resp.get("data") or []
            if not items:
                break
            all_items.extend(items)

            total_pages = (resp.get("pageNav") or {}).get("totalPages") or resp.get("total_pages") or 1
            if page >= int(total_pages):
                break
            page += 1
            if page > 50:  # safety
                break
        logger.info("Получено {} аккаунтов из API", len(all_items))
        return all_items

    def _reset_daily_limits(self) -> None:
        now = datetime.now(timezone.utc)
        if now.time() > dtime(0, 20):
            return  # сбрасываем только в пределах первого тика после полуночи
        with get_session() as s:
            accounts = list(s.execute(select(Account)).scalars())
            for acc in accounts:
                acc.bumps_available = 3
                acc.sticks_available = 1
            s.commit()
        logger.info("Дневные лимиты bump/stick сброшены")

    def _run_auto_actions(self) -> dict:
        auto_result = {"bumps": 0, "sticks": 0}
        with get_session() as s:
            niches = list(s.execute(select(Niche)).scalars())
            for n in niches:
                if not (n.auto_bump or n.auto_stick):
                    continue
                accounts = list(
                    s.execute(
                        select(Account).where(Account.niche_id == n.id, Account.status == "active")
                    ).scalars()
                )
                accounts.sort(key=lambda a: (not a.is_priority, -(a.price or 0)))
                ids = [a.item_id for a in accounts]
                if n.priority_item_id and n.priority_item_id in ids:
                    ids.remove(n.priority_item_id)
                    ids.insert(0, n.priority_item_id)

                if n.auto_bump:
                    ids_to_bump = [i for i in ids if self._can_bump(s, i)]
                    if ids_to_bump:
                        res = bump_items(self.client, ids_to_bump[:5])
                        auto_result["bumps"] += sum(1 for v in res.values() if v == "ok")
                if n.auto_stick:
                    ids_to_stick = [i for i in ids if self._can_stick(s, i)]
                    if ids_to_stick:
                        res = stick_items(self.client, ids_to_stick[:1])
                        auto_result["sticks"] += sum(1 for v in res.values() if v == "ok")
        return auto_result

    @staticmethod
    def _can_bump(session, item_id: int) -> bool:
        acc = session.execute(select(Account).where(Account.item_id == item_id)).scalar_one_or_none()
        return bool(acc and acc.bumps_available > 0)

    @staticmethod
    def _can_stick(session, item_id: int) -> bool:
        acc = session.execute(select(Account).where(Account.item_id == item_id)).scalar_one_or_none()
        return bool(acc and acc.sticks_available > 0)
