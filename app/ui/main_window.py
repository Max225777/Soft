"""Главное окно приложения."""

from __future__ import annotations

from datetime import datetime, timezone

from loguru import logger
from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStatusBar,
    QWidget,
)

from app.api.client import LolzMarketClient
from app.api.queue import RequestQueue
from app.config import Settings
from app.core.cycle import UpdateCycle
from app.services import settings_store
from app.ui.home_tab import HomeTab
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
            interval_minutes=settings.cycle_interval_minutes,
            on_tick=self._on_cycle_tick,
        )

        self.setWindowTitle("Lolzteam Market Manager")
        self.resize(1400, 820)

        self._build_ui()
        self._build_menu()
        self._build_statusbar()

        if not token:
            QTimer.singleShot(200, self._prompt_for_token)
        elif settings.cycle_autostart:
            # При первом запуске (БД пустая) — сразу подтягиваем items с API,
            # чтобы тег-кеш и список аккаунтов сразу был готов.
            run_now = self._is_db_empty()
            self.cycle.start(run_now=run_now)
            if run_now:
                logger.info("БД пустая — запускаем первый цикл сейчас, чтобы подтянуть items+теги")

        self._status_timer = QTimer(self)
        self._status_timer.timeout.connect(self._refresh_status)
        self._status_timer.start(1000)

        # Періодично оновлюємо UI з БД — щоб точно бачити актуальний стан
        # навіть коли цикл або ручні дії змінили дані без явного сигналу.
        self._ui_refresh_timer = QTimer(self)
        self._ui_refresh_timer.timeout.connect(self._refresh_ui)
        self._ui_refresh_timer.start(5000)  # 5 секунд

    @staticmethod
    def _is_db_empty() -> bool:
        from sqlalchemy import func, select
        from app.db.models import Account
        from app.db.session import get_session
        with get_session() as s:
            return (s.execute(select(func.count(Account.id))).scalar_one() or 0) == 0

    # ---------- UI ----------
    def _build_ui(self) -> None:
        # Поки що тільки головна вкладка — статистика прибрана за запитом
        self.home_tab = HomeTab(client=self.client, trigger_refresh=self.cycle.trigger_now)
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

        # --- Меню «Дані» з небезпечними операціями ---
        data_menu = self.menuBar().addMenu("Дані")
        act_clear_stats = QAction("🧹 Очистити статистику (продажі + лог)", self)
        act_clear_stats.triggered.connect(self._clear_statistics)
        data_menu.addAction(act_clear_stats)

        act_reclassify = QAction("🔄 Перекласифікувати акаунти за нішами", self)
        act_reclassify.triggered.connect(self._reclassify)
        data_menu.addAction(act_reclassify)

    def _build_statusbar(self) -> None:
        bar = QStatusBar()
        self.setStatusBar(bar)
        self.lbl_cycle = QLabel("Цикл: не запущен")
        self.lbl_queue = QLabel("Очередь: 0")
        self.lbl_api = QLabel("API: — / —")
        bar.addPermanentWidget(self.lbl_cycle)
        bar.addPermanentWidget(self.lbl_queue)
        bar.addPermanentWidget(self.lbl_api)

    # ---------- slots ----------
    def _open_settings(self) -> None:
        dlg = SettingsDialog(self.settings, parent=self)
        if dlg.exec() == SettingsDialog.DialogCode.Accepted:
            new_token = settings_store.load_token() or self.settings.api_token
            self.client.update_token(new_token)
            self.client.base_url = self.settings.api_base_url.rstrip("/") + "/"
            self.client.lang = self.settings.api_lang
            self.queue.min_delay = max(self.settings.api_min_delay, 3.0)
            if self.cycle._scheduler.running:
                self.cycle.stop()
            self.cycle.interval_minutes = self.settings.cycle_interval_minutes
            if self.settings.cycle_autostart:
                self.cycle.start(run_now=False)
            self.statusBar().showMessage("Настройки сохранены", 3000)

    def _open_logs(self) -> None:
        LogsDialog(parent=self).exec()

    def _prompt_for_token(self) -> None:
        QMessageBox.information(
            self,
            "Требуется токен",
            "API-токен не найден. Откроем настройки — вставьте токен со scope read+post+market.",
        )
        self._open_settings()

    def _clear_statistics(self) -> None:
        confirm = QMessageBox.question(
            self,
            "Очистити статистику",
            "Видалити ВСІ записи з таблиць Sale, ActionLog, PriceHistory?\n"
            "Аккаунти й ніші залишаться. Це необоротна операція.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        from app.db.models import ActionLog, PriceHistory, Sale
        from app.db.session import get_session

        with get_session() as s:
            sales = s.query(Sale).delete()
            logs = s.query(ActionLog).delete()
            ph = s.query(PriceHistory).delete()
            s.commit()
        logger.info("Очищена статистика: sales={}, action_log={}, price_history={}", sales, logs, ph)
        self.statusBar().showMessage(
            f"Очищено: {sales} продажів, {logs} записів логу, {ph} історії цін", 6000,
        )
        self._refresh_ui()

    def _reclassify(self) -> None:
        from app.core import niche_manager
        counts = niche_manager.reclassify_accounts()
        total = sum(counts.values())
        QMessageBox.information(
            self,
            "Перекласифіковано",
            f"Класифіковано {total} акк за {len(counts)} ніш.\nДеталі — у журналі подій (Файл → Журнал).",
        )
        self._refresh_ui()

    def _refresh_ui(self) -> None:
        self.home_tab.reload()

    def _on_cycle_tick(self, summary: dict) -> None:
        # Колбэк прилетает из фонового потока APScheduler — нельзя
        # напрямую трогать Qt-виджеты, иначе на Windows окно "не отвечает".
        # Маршалим всё в main thread через QTimer.singleShot.
        logger.info("Цикл завершён: {}", summary)
        QTimer.singleShot(0, lambda: self._on_cycle_tick_main(summary))

    def _on_cycle_tick_main(self, summary: dict) -> None:
        self._refresh_ui()
        if summary.get("sold") and self.settings.notify_sales:
            self.statusBar().showMessage(
                f"Обнаружено продаж: {summary['sold']}, "
                f"поднятий: {summary.get('auto', {}).get('bumps', 0)}",
                8000,
            )

    def _refresh_status(self) -> None:
        # cycle
        next_tick = self.cycle.next_tick()
        if next_tick is None:
            self.lbl_cycle.setText("Цикл: не запущен")
        else:
            delta = (next_tick - datetime.now(timezone.utc)).total_seconds()
            mins, secs = divmod(max(int(delta), 0), 60)
            self.lbl_cycle.setText(f"След. цикл через: {mins:02d}:{secs:02d}")

        self.lbl_queue.setText(f"Очередь: {self.queue.pending()}")
        normal, search = self.queue.recent_requests()
        self.lbl_api.setText(f"API: {normal}/мин (поиск {search}/мин)")

        # передаём время след. цикла в панель задач
        if hasattr(self, "home_tab") and hasattr(self.home_tab, "tasks_panel"):
            self.home_tab.tasks_panel.set_next_cycle(next_tick)

    # ---------- lifecycle ----------
    def closeEvent(self, event) -> None:  # noqa: N802
        logger.info("Завершение работы")
        try:
            self.cycle.stop()
        finally:
            self.queue.stop()
            self.client.close()
        super().closeEvent(event)
