"""Потокобезопасная приоритизированная очередь запросов с rate-limiting.

Исполняется в фоновом потоке; результаты возвращаются через `Future`.
Параметры соответствуют ограничениям Lolzteam Market API:
- 120 запросов/мин для обычных эндпоинтов,
- 20 запросов/мин для поисковых,
- минимальная задержка между любыми запросами — не менее 3 секунд.
"""

from __future__ import annotations

import heapq
import itertools
import threading
import time
from collections import deque
from concurrent.futures import Future
from dataclasses import dataclass, field
from typing import Any, Callable


PRIORITY_HIGH = 0
PRIORITY_MEDIUM = 50
PRIORITY_LOW = 100


@dataclass(order=True)
class _Task:
    priority: int
    seq: int
    fn: Callable[[], Any] = field(compare=False)
    future: Future = field(compare=False)
    is_search: bool = field(default=False, compare=False)


class RequestQueue:
    def __init__(
        self,
        min_delay: float = 0.6,
        normal_per_minute: int = 120,
        search_per_minute: int = 20,
        search_min_delay: float = 3.0,
    ) -> None:
        # Для обычных endpoint-ов 0.6с безопасно (60/0.6=100/мин < лимита 120/мин).
        # Для search-endpoint-ов держим минимум 3с (лимит 20/мин).
        self.min_delay = max(min_delay, 0.3)
        self.search_min_delay = max(search_min_delay, 3.0)
        self.normal_per_minute = normal_per_minute
        self.search_per_minute = search_per_minute

        self._heap: list[_Task] = []
        self._seq = itertools.count()
        self._cond = threading.Condition()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

        self._last_call_at: float = 0.0
        self._normal_window: deque[float] = deque()
        self._search_window: deque[float] = deque()
        self._counter_lock = threading.Lock()

    # ---------- lifecycle ----------
    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="ApiQueue", daemon=True)
        self._thread.start()

    def stop(self, timeout: float = 2.0) -> None:
        self._stop.set()
        with self._cond:
            self._cond.notify_all()
        if self._thread:
            self._thread.join(timeout=timeout)

    # ---------- public ----------
    def submit(
        self,
        fn: Callable[[], Any],
        *,
        priority: int = PRIORITY_MEDIUM,
        is_search: bool = False,
    ) -> Future:
        fut: Future = Future()
        task = _Task(priority=priority, seq=next(self._seq), fn=fn, future=fut, is_search=is_search)
        with self._cond:
            heapq.heappush(self._heap, task)
            self._cond.notify()
        return fut

    def pending(self) -> int:
        with self._cond:
            return len(self._heap)

    def recent_requests(self) -> tuple[int, int]:
        """Возвращает (обычных за 60s, поисковых за 60s)."""
        now = time.monotonic()
        with self._counter_lock:
            self._trim(self._normal_window, now)
            self._trim(self._search_window, now)
            return len(self._normal_window), len(self._search_window)

    # ---------- internal ----------
    def _run(self) -> None:
        while not self._stop.is_set():
            task = self._pop_next()
            if task is None:
                continue
            self._respect_rate_limits(task.is_search)
            try:
                result = task.fn()
                task.future.set_result(result)
            except Exception as exc:  # noqa: BLE001
                task.future.set_exception(exc)
            finally:
                self._record(task.is_search)

    def _pop_next(self) -> _Task | None:
        with self._cond:
            while not self._heap and not self._stop.is_set():
                self._cond.wait(timeout=0.5)
            if self._stop.is_set():
                return None
            return heapq.heappop(self._heap)

    def _respect_rate_limits(self, is_search: bool) -> None:
        # минимальная пауза: для search строже (3 сек), для обычных — быстрее
        required = self.search_min_delay if is_search else self.min_delay
        now = time.monotonic()
        delta = now - self._last_call_at
        if delta < required:
            time.sleep(required - delta)

        # скользящее окно за 60 секунд
        while True:
            now = time.monotonic()
            with self._counter_lock:
                self._trim(self._normal_window, now)
                self._trim(self._search_window, now)
                if is_search:
                    if len(self._search_window) < self.search_per_minute:
                        break
                    wait = 60 - (now - self._search_window[0]) + 0.1
                else:
                    if len(self._normal_window) < self.normal_per_minute:
                        break
                    wait = 60 - (now - self._normal_window[0]) + 0.1
            time.sleep(max(wait, 0.5))

    def _record(self, is_search: bool) -> None:
        now = time.monotonic()
        self._last_call_at = now
        with self._counter_lock:
            if is_search:
                self._search_window.append(now)
            else:
                self._normal_window.append(now)

    @staticmethod
    def _trim(window: deque[float], now: float) -> None:
        threshold = now - 60.0
        while window and window[0] < threshold:
            window.popleft()
