"""Безпечний фоновий виклик API без QThread.

Використовує plain `threading.Thread` (не QThread!) для виконання callable —
це уникає несумісностей між Qt thread-pool і блокуючими C-extension'ами
(httpx, ssl, sqlite) на Windows, які іноді призводять до
STATUS_STACK_BUFFER_OVERRUN (0xC0000409).

Результат повертається в main thread через Qt сигнал з QueuedConnection.
"""

from __future__ import annotations

import threading
from typing import Callable

from PySide6.QtCore import QObject, Qt, Signal


class AsyncCall(QObject):
    _done = Signal(object)
    _failed = Signal(object)

    def __init__(
        self,
        fn: Callable,
        *args,
        on_done: Callable[[object], None] | None = None,
        on_error: Callable[[Exception], None] | None = None,
        parent: QObject | None = None,
        **kwargs,
    ) -> None:
        super().__init__(parent)
        self._fn = fn
        self._args = args
        self._kwargs = kwargs
        self._cancelled = False

        if on_done is not None:
            self._done.connect(self._safe_call_done(on_done), Qt.ConnectionType.QueuedConnection)
        if on_error is not None:
            self._failed.connect(self._safe_call_error(on_error), Qt.ConnectionType.QueuedConnection)

        self._thread = threading.Thread(target=self._run, daemon=True, name="AsyncCall")

        if parent is not None:
            parent.destroyed.connect(self.cancel)

    def _safe_call_done(self, callback):
        def wrapper(result):
            if self._cancelled:
                return
            try:
                callback(result)
            except Exception:  # noqa: BLE001
                from loguru import logger
                logger.exception("AsyncCall on_done callback failed")
        return wrapper

    def _safe_call_error(self, callback):
        def wrapper(exc):
            if self._cancelled:
                return
            try:
                callback(exc)
            except Exception:  # noqa: BLE001
                from loguru import logger
                logger.exception("AsyncCall on_error callback failed")
        return wrapper

    def _run(self) -> None:
        try:
            result = self._fn(*self._args, **self._kwargs)
        except Exception as exc:  # noqa: BLE001
            if not self._cancelled:
                try:
                    self._failed.emit(exc)
                except RuntimeError:
                    pass
            return
        if not self._cancelled:
            try:
                self._done.emit(result)
            except RuntimeError:
                pass

    def start(self) -> None:
        self._thread.start()

    def cancel(self) -> None:
        self._cancelled = True
