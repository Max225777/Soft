"""Лёгкий Qt-friendly воркер для фоновых API-вызовов.

Запускает callable() в отдельном QThread и эмитит сигнал с результатом
в main thread через Qt.AutoConnection. UI не зависает.
"""

from __future__ import annotations

from typing import Callable

from PySide6.QtCore import QObject, QThread, Signal


class _Job(QObject):
    finished = Signal(object)
    failed = Signal(Exception)

    def __init__(self, fn: Callable[[], object]):
        super().__init__()
        self._fn = fn

    def run(self) -> None:
        try:
            result = self._fn()
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(exc)
            return
        self.finished.emit(result)


class AsyncCall:
    """Пример использования:

        self._call = AsyncCall(fetch_tags, self.client,
                               on_done=self._tags_loaded,
                               on_error=self._tags_failed,
                               parent=self)
        self._call.start()
    """

    def __init__(
        self,
        fn: Callable,
        *args,
        on_done: Callable[[object], None] | None = None,
        on_error: Callable[[Exception], None] | None = None,
        parent: QObject | None = None,
        **kwargs,
    ) -> None:
        bound = lambda: fn(*args, **kwargs)
        self._thread = QThread(parent)
        self._job = _Job(bound)
        self._job.moveToThread(self._thread)
        self._thread.started.connect(self._job.run)

        if on_done is not None:
            self._job.finished.connect(on_done)
        if on_error is not None:
            self._job.failed.connect(on_error)

        # cleanup
        self._job.finished.connect(self._thread.quit)
        self._job.failed.connect(self._thread.quit)
        self._thread.finished.connect(self._job.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)

    def start(self) -> None:
        self._thread.start()
