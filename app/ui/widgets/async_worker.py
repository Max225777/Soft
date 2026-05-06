"""Безпечний фоновий виклик API без QThread.

Використовує plain `threading.Thread` (не QThread!) для виконання callable —
це уникає несумісностей між Qt thread-pool і блокуючими C-extension'ами
(httpx, ssl, sqlite) на Windows.

Результат повертається в main thread через Qt сигнал. Slot — це метод
самого AsyncCall (QObject), тому Qt правильно маршалить через event loop.
"""

from __future__ import annotations

import threading
from typing import Callable

from PySide6.QtCore import QObject, Qt, Signal, Slot


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
        self._on_done = on_done
        self._on_error = on_error
        self._cancelled = False

        # ЯВНА QueuedConnection — emit з threading.Thread (не QThread!)
        # AutoConnection не може правильно визначити цей випадок і робить
        # DirectConnection → slot виконається у BG потоці і UI зламається.
        self._done.connect(self._handle_done, Qt.ConnectionType.QueuedConnection)
        self._failed.connect(self._handle_failed, Qt.ConnectionType.QueuedConnection)

        self._thread = threading.Thread(target=self._run, daemon=True, name="AsyncCall")

        if parent is not None:
            try:
                parent.destroyed.connect(self.cancel)
            except Exception:  # noqa: BLE001
                pass

    @Slot(object)
    def _handle_done(self, result) -> None:
        if self._cancelled or self._on_done is None:
            return
        try:
            self._on_done(result)
        except Exception:  # noqa: BLE001
            from loguru import logger
            logger.exception("AsyncCall on_done callback failed")

    @Slot(object)
    def _handle_failed(self, exc) -> None:
        if self._cancelled or self._on_error is None:
            return
        try:
            self._on_error(exc)
        except Exception:  # noqa: BLE001
            from loguru import logger
            logger.exception("AsyncCall on_error callback failed")

    def _run(self) -> None:
        try:
            result = self._fn(*self._args, **self._kwargs)
        except Exception as exc:  # noqa: BLE001
            from loguru import logger
            logger.exception("AsyncCall fn raised: {}", exc)
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
