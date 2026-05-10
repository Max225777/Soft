"""Головне вікно — мінімум: одна форма + меню Файл/Цикл."""

from __future__ import annotations

from datetime import datetime, timezone

from loguru import logger
from PySide6.QtCore import QTimer
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QLabel,
    QMainWindow,
    QMessageBox,
    QStatusBar,
)

from app.api.client import LolzMarketClient
from app.api.queue import RequestQueue
from app.config import Settings
from app.core.cycle import UpdateCycle
from app.services import settings_store
from app.ui.logs_dialog import LogsDialog
from app.ui.settings_dialog import SettingsDialog


class MainWindow(QMainWindow):
    def __init__(self, settings: Settings) -> None:
        super().__init__()
        self.settings = settings

        token = settings_store.load_token() or settings.api_token
        self.queue = RequestQueue(min_delay=settings.api_min_delay)
        self.queue.start()
        self.client = LolzMarketClient(
            token=token,
            base_url=settings.api_base_url,
            lang=settings.api_lang,
            queue=self.queue,
            max_retries=settings.api_max_retries,
        )
        self.cycle = UpdateCycle(
            client=self.client,
            interval_seconds=settings.cycle_interval_seconds,
            on_tick=self._on_cycle_tick,
        )

        self.setWindowTitle("Lolzteam Bumper")
        self.resize(1100, 760)

        self._build_ui()
        self._build_menu()
        self._build_statusbar()

        if not token:
            QTimer.singleShot(200, self._prompt_for_token)
        elif settings.cycle_autostart:
            # Стартуємо tick одразу якщо БД порожня АБО є запущена ніша
            run_now = self._is_db_empty() or self._has_running_niche()
            self.cycle.start(run_now=run_now)
            if run_now:
                logger.info("Перший цикл стартує одразу (БД пуста або є запущена ніша)")

        self._status_timer = QTimer(self)
        self._status_timer.timeout.connect(self._refresh_status)
        self._status_timer.start(1000)

    @staticmethod
    def _is_db_empty() -> bool:
        from sqlalchemy import func, select

        from app.db.models import Account
        from app.db.session import get_session
        with get_session() as s:
            return (s.execute(select(func.count(Account.id))).scalar_one() or 0) == 0

    @staticmethod
    def _has_running_niche() -> bool:
        """Повертає True якщо в БД є хоча б одна ніша з auto_bump=True."""
        from sqlalchemy import select

        from app.db.models import Niche
        from app.db.session import get_session
        with get_session() as s:
            niche = s.execute(
                select(Niche).where(Niche.auto_bump.is_(True)).limit(1)
            ).scalar_one_or_none()
            return niche is not None

    # ---------- UI ----------
    def _build_ui(self) -> None:
        from app.ui.simple_form import SimpleForm
        self.home_tab = SimpleForm(client=self.client, trigger_refresh=self.cycle.trigger_now)
        self.setCentralWidget(self.home_tab)

    def _build_menu(self) -> None:
        menu = self.menuBar().addMenu("Файл")
        act_settings = QAction("Налаштування…", self)
        act_settings.triggered.connect(self._open_settings)
        menu.addAction(act_settings)

        act_logs = QAction("Журнал подій…", self)
        act_logs.triggered.connect(self._open_logs)
        menu.addAction(act_logs)

        menu.addSeparator()
        act_quit = QAction("Вихід", self)
        act_quit.triggered.connect(self.close)
        menu.addAction(act_quit)

        cycle_menu = self.menuBar().addMenu("Цикл")
        act_start = QAction("Запустити", self)
        act_start.triggered.connect(lambda: self.cycle.start(run_now=True))
        cycle_menu.addAction(act_start)
        act_stop = QAction("Зупинити", self)
        act_stop.triggered.connect(self.cycle.stop)
        cycle_menu.addAction(act_stop)
        act_now = QAction("Оновити зараз", self)
        act_now.triggered.connect(self.cycle.trigger_now)
        cycle_menu.addAction(act_now)

    def _build_statusbar(self) -> None:
        bar = QStatusBar()
        self.setStatusBar(bar)
        self.lbl_cycle = QLabel("Цикл: не запущено")
        self.lbl_queue = QLabel("Черга: 0")
        self.lbl_api = QLabel("API: — / —")
        bar.addPermanentWidget(self.lbl_cycle)
        bar.addPermanentWidget(self.lbl_queue)
        bar.addPermanentWidget(self.lbl_api)

    # ---------- slots ----------
    def _open_settings(self) -> None:
        dlg = SettingsDialog(self.settings, parent=self)
        dlg.client = self.client
        if dlg.exec() == SettingsDialog.DialogCode.Accepted:
            new_token = settings_store.load_token() or self.settings.api_token
            self.client.update_token(new_token)
            self.client.base_url = self.settings.api_base_url.rstrip("/") + "/"
            self.client.lang = self.settings.api_lang
            self.queue.min_delay = max(self.settings.api_min_delay, 0.3)
            if self.cycle._scheduler.running:
                self.cycle.stop()
            self.cycle.interval_seconds = self.settings.cycle_interval_seconds
            if self.settings.cycle_autostart:
                self.cycle.start(run_now=False)
            self.statusBar().showMessage("Налаштування збережено", 3000)

    def _open_logs(self) -> None:
        LogsDialog(parent=self).exec()

    def _prompt_for_token(self) -> None:
        QMessageBox.information(
            self,
            "Потрібен токен",
            "API-токен не знайдено. Відкрию налаштування — вставте токен зі scope read+post+market.",
        )
        self._open_settings()

    def _on_cycle_tick(self, summary: dict) -> None:
        # Колбек прилітає з фонового потоку — маршалимо в main thread.
        logger.info("Цикл завершено: {}", summary)
        QTimer.singleShot(0, lambda: self._on_cycle_tick_main(summary))

    def _on_cycle_tick_main(self, summary: dict) -> None:
        if summary.get("sold") and self.settings.notify_sales:
            self.statusBar().showMessage(
                f"Виявлено продажів: {summary['sold']}, "
                f"підйомів: {summary.get('auto', {}).get('bumps', 0)}",
                8000,
            )

    def _refresh_status(self) -> None:
        next_tick = self.cycle.next_tick()
        if next_tick is None:
            self.lbl_cycle.setText("Цикл: не запущено")
        else:
            delta = (next_tick - datetime.now(timezone.utc)).total_seconds()
            mins, secs = divmod(max(int(delta), 0), 60)
            self.lbl_cycle.setText(f"Наст. цикл через: {mins:02d}:{secs:02d}")

        self.lbl_queue.setText(f"Черга: {self.queue.pending()}")
        normal, search = self.queue.recent_requests()
        self.lbl_api.setText(f"API: {normal}/хв (пошук {search}/хв)")

    # ---------- lifecycle ----------
    def closeEvent(self, event) -> None:  # noqa: N802
        logger.info("Завершення роботи")
        try:
            self.cycle.stop()
        finally:
            self.queue.stop()
            self.client.close()
        super().closeEvent(event)
