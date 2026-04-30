"""20-минутный цикл обновления."""

from __future__ import annotations

import threading
from datetime import datetime, time as dtime, timedelta, timezone
from typing import Callable

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from loguru import logger
from sqlalchemy import func, select

from app.api.client import ApiError, LolzMarketClient
from app.core.bulk_actions import bump_items, stick_items
from app.core.niche_manager import reclassify_accounts
from app.core.sale_tracker import sync_accounts_snapshot
from app.db.models import Account, ActionLog, Niche
from app.db.session import get_session
from app.services import settings_store


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

    def trigger_now(self) -> bool:
        """Спробувати запустити tick прямо зараз. Повертає True якщо потік
        стартував, False якщо інший tick уже виконується.
        """
        if self._lock.locked():
            logger.warning("trigger_now: цикл вже виконується, пропускаю")
            return False
        threading.Thread(target=self._safe_tick, daemon=True, name="CycleManual").start()
        return True

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
        per_page_seen = 0
        while True:
            try:
                resp = self.client.list_my_items(page=page)
            except ApiError as exc:
                logger.error("Ошибка получения списка аккаунтов (page={}): {}", page, exc)
                break

            items = resp.get("items") or resp.get("data") or []
            if page == 1 and isinstance(resp, dict):
                top_keys = sorted(resp.keys())
                logger.info("list_my_items page 1: top-level keys = {}", top_keys)
                page_nav = resp.get("pageNav") or resp.get("page_nav") or resp.get("pagination") or {}
                if page_nav:
                    logger.info("  pagination = {}", page_nav)

            if not items:
                logger.info("Страница {} пустая — конец пагинации", page)
                break
            all_items.extend(items)
            per_page_seen = max(per_page_seen, len(items))
            logger.info("  page {}: получено {} items (всего: {})", page, len(items), len(all_items))

            # Останавливаемся, если страница неполная (значит это последняя)
            if len(items) < per_page_seen:
                break

            total_pages = (
                (resp.get("pageNav") or {}).get("totalPages")
                or (resp.get("page_nav") or {}).get("totalPages")
                or (resp.get("pagination") or {}).get("totalPages")
                or resp.get("total_pages")
                or resp.get("totalPages")
            )
            if total_pages and page >= int(total_pages):
                break
            page += 1
            if page > 200:  # safety
                logger.warning("Достигнут лимит 200 страниц — прерываем")
                break
        logger.info("Всего получено {} аккаунтов из API", len(all_items))
        return all_items

    def _reset_daily_limits(self) -> None:
        now = datetime.now(timezone.utc)
        if now.time() > dtime(0, 20):
            return  # сбрасываем только в пределах первого тика после полуночи
        global_bump = settings_store.get_global_bumps_per_account()
        with get_session() as s:
            accounts = list(s.execute(select(Account)).scalars())
            for acc in accounts:
                acc.bumps_available = global_bump
                acc.sticks_available = 1
            s.commit()
        logger.info("Дневные лимиты bump/stick сброшены (bump={}/акк)", global_bump)

    def _run_auto_actions(self) -> dict:
        auto_result = {"bumps": 0, "sticks": 0, "stuck_bumps": 0, "unsticks": 0}
        today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        global_max = settings_store.get_global_bumps_per_day()
        already_today_global = self._count_global_bumps_today(today_start) if global_max else 0

        with get_session() as s:
            niches = list(s.execute(select(Niche)).scalars())
            for n in niches:
                accounts = list(
                    s.execute(
                        select(Account).where(Account.niche_id == n.id, Account.status == "active")
                    ).scalars()
                )
                if not accounts:
                    continue
                accounts.sort(key=lambda a: (not a.is_priority, -(a.price or 0)))
                if n.priority_item_id:
                    accounts.sort(key=lambda a: 0 if a.item_id == n.priority_item_id else 1)

                normal_accounts = [a for a in accounts if not a.is_stuck]
                stuck_accounts = [a for a in accounts if a.is_stuck]

                # --- 1. Автозакрепление — доводим кол-во закреплённых до stick_slots ---
                if n.auto_stick and n.stick_slots > 0:
                    need_more = n.stick_slots - len(stuck_accounts)
                    if need_more > 0:
                        candidates = [a for a in normal_accounts if a.sticks_available > 0]
                        # с fallback: если stick падает на акк (ошибка/продан) — пробуем следующий
                        sticked_ok = self._try_action_with_fallback(
                            stick_items, candidates, need_more,
                        )
                        for item_id in sticked_ok:
                            acc = s.execute(select(Account).where(Account.item_id == item_id)).scalar_one_or_none()
                            if acc:
                                acc.is_stuck = True
                        auto_result["sticks"] += len(sticked_ok)

                # --- 2. Автоподнятие обычных ---
                if n.auto_bump and n.bumps_per_day > 0:
                    done_today = self._count_bumps_today(s, n.id, today_start, stuck=False)
                    remaining = n.bumps_per_day - done_today
                    # глобальный лимит — общая шапка по всем нишам
                    if global_max:
                        global_left = max(0, global_max - already_today_global - auto_result["bumps"])
                        remaining = min(remaining, global_left)
                    if remaining > 0:
                        per_tick = self._target_for_this_hour(n, done_today)
                        if global_max:
                            per_tick = min(per_tick, remaining)
                        candidates = [a for a in normal_accounts if a.bumps_available > 0]
                        bumped_ok = self._try_action_with_fallback(
                            bump_items, candidates, per_tick,
                        )
                        auto_result["bumps"] += len(bumped_ok)

                # --- 3. Отдельное поднятие закреплённых (с учётом 1h cooldown) ---
                if n.auto_bump_stuck and n.stuck_bumps_per_day > 0 and stuck_accounts:
                    done_today = self._count_bumps_today(s, n.id, today_start, stuck=True)
                    remaining = n.stuck_bumps_per_day - done_today
                    if remaining > 0:
                        cooldown = timedelta(minutes=max(1, n.stuck_bump_cooldown_min))
                        now = datetime.now(timezone.utc)
                        eligible = [
                            a for a in stuck_accounts
                            if a.bumps_available > 0
                            and (a.last_bumped_at is None or (now - a.last_bumped_at) >= cooldown)
                        ]
                        per_tick = self._bumps_for_this_tick(remaining, today_start)
                        bumped_ok = self._try_action_with_fallback(
                            bump_items, eligible, per_tick,
                        )
                        auto_result["stuck_bumps"] += len(bumped_ok)
            s.commit()
        return auto_result

    @staticmethod
    def _count_global_bumps_today(today_start: datetime) -> int:
        """Сколько успешных bump-ов сделано сегодня по ВСЕМ нишам (для глобального лимита)."""
        with get_session() as s:
            stmt = select(func.count(ActionLog.id)).where(
                ActionLog.action == "bump",
                ActionLog.level == "INFO",
                ActionLog.created_at >= today_start,
            )
            return s.execute(stmt).scalar_one() or 0

    @staticmethod
    def _count_bumps_today(session, niche_id: int, today_start: datetime, stuck: bool) -> int:
        """Считает успешные bump-ы сегодня для ниши.

        Различаем обычные от поднятий закреплённых по details.stuck.
        """
        stmt = (
            select(func.count(ActionLog.id))
            .join(Account, Account.item_id == ActionLog.item_id, isouter=True)
            .where(
                ActionLog.action == "bump",
                ActionLog.level == "INFO",
                ActionLog.created_at >= today_start,
                Account.niche_id == niche_id,
                Account.is_stuck.is_(stuck),
            )
        )
        return session.execute(stmt).scalar_one() or 0

    def _try_action_with_fallback(
        self,
        action_fn,
        candidates: list[Account],
        target_count: int,
    ) -> list[int]:
        """Применяет action_fn(client, [item_ids]) пачками, пока не наберём
        target_count успехов либо не закончатся кандидаты.

        Если на акк прилетела ошибка (продан, нет прав, лимит) — берём
        следующий из этой же ниши. Якщо 403 повторюється >= 5 разів поспіль —
        припиняємо (значить у користувача проблеми з доступом до групи акк).
        """
        if target_count <= 0 or not candidates:
            return []
        success_ids: list[int] = []
        idx = 0
        consecutive_403 = 0
        max_attempts = max(target_count * 3, 20)
        attempts = 0
        while len(success_ids) < target_count and idx < len(candidates):
            need = target_count - len(success_ids)
            batch = candidates[idx:idx + need]
            idx += len(batch)
            if not batch:
                break
            attempts += len(batch)
            if attempts > max_attempts:
                logger.warning("Досягнуто ліміту спроб ({}) — припиняю спроби", max_attempts)
                break
            res = action_fn(self.client, [a.item_id for a in batch])
            for item_id, result in res.items():
                if isinstance(result, str) and (result == "ok" or result.startswith("ok")):
                    success_ids.append(item_id)
                    consecutive_403 = 0
                else:
                    if isinstance(result, str) and "403" in result:
                        consecutive_403 += 1
                    logger.info(
                        "Дія на item {} не вдалась ({}), пробуємо наступний з ніші",
                        item_id, str(result)[:100],
                    )
            if consecutive_403 >= 5:
                logger.warning(
                    "🚫 5 поспіль помилок 403 — припиняю спроби. "
                    "Перевірте права токена або стан акаунтів у Lolzteam."
                )
                break
        return success_ids

    def _bumps_for_this_tick(self, remaining_today: int, today_start: datetime) -> int:
        """Распределяет оставшиеся bumps равномерно до конца суток."""
        now = datetime.now(timezone.utc)
        seconds_left = max((today_start.replace(hour=23, minute=59) - now).total_seconds(), 60)
        ticks_left = max(int(seconds_left / (self.interval_minutes * 60)), 1)
        per_tick = max(1, remaining_today // ticks_left)
        return min(per_tick, remaining_today)

    def _target_for_this_hour(self, niche: Niche, done_today: int) -> int:
        """Если у ниши задан hourly_schedule — сверяем сколько уже сделано и
        сколько должно быть сделано к этому часу."""
        schedule = list(niche.hourly_schedule or [])
        if len(schedule) != 24 or sum(schedule) == 0:
            # нет расписания — распределяем равномерно
            remaining = max(0, niche.bumps_per_day - done_today)
            today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
            return self._bumps_for_this_tick(remaining, today_start)

        current_hour = datetime.now(timezone.utc).hour
        target_so_far = sum(schedule[: current_hour + 1])
        return max(0, target_so_far - done_today)
