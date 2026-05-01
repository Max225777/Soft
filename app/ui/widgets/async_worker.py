"""Лёгкий Qt-friendly воркер для фоновых API-вызовов.

Запускает callable() в отдельном QThread и эмитит сигнал с результатом
в main thread через Qt.AutoConnection. UI не зависает.

Безпека:
- При закритті parent-диалогу AsyncCall.cancel() блокує доставку сигналів
  у вже видалені об'єкти (інакше Qt може впасти STATUS_STACK_BUFFER_OVERRUN).
- Thread очікується (wait) перед деструкцією, щоб уникнути race-condition.
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
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    def run(self) -> None:
        try:
            result = self._fn()
        except Exception as exc:  # noqa: BLE001
            if not self._cancelled:
                self.failed.emit(exc)
            return
        if not self._cancelled:
            self.finished.emit(result)


class AsyncCall(QObject):
    """Безпечне виконання callable у фоновому потоці.

    Приклад:
        self._call = AsyncCall(fetch_tags, self.client,
                               on_done=self._tags_loaded,
                               on_error=self._tags_failed,
                               parent=self)
        self._call.start()

    При закритті parent (QObject деструктор) AsyncCall автоматично
    cancel-ується через connection до destroyed signal.
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
        super().__init__(parent)
        bound = lambda: fn(*args, **kwargs)
        self._thread = QThread(self)
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

        # Якщо parent зникає — скасовуємо доставку сигналів у мертві об'єкти
        if parent is not None:
            parent.destroyed.connect(self.cancel)

    def start(self) -> None:
        self._thread.start()

    def cancel(self) -> None:
        """Зупиняє доставку сигналів і дочікується завершення потоку."""
        try:
            self._job.cancel()
        except RuntimeError:
            return
        if self._thread.isRunning():
            self._thread.quit()
            # wait не довше за 3 сек — якщо API залип, не зависаємо назавжди
            self._thread.wait(3000)
