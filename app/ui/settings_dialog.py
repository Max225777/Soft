"""Диалог настроек приложения."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

from app.config import Settings
from app.core import niche_manager
from app.services import settings_store
from app.services.crypto import mask_token


class SettingsDialog(QDialog):
    def __init__(self, settings: Settings, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Настройки")
        self.resize(560, 520)
        self.settings = settings
        self._build_ui()
        self._load()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        api_box = QGroupBox("API Lolzteam Market")
        api_form = QFormLayout(api_box)
        self.token_edit = QLineEdit()
        self.token_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.token_edit.setPlaceholderText("Вставьте токен (scope: read+post+market)")
        self.show_token_btn = QPushButton("Показать")
        self.show_token_btn.setCheckable(True)
        self.show_token_btn.toggled.connect(self._toggle_token)

        token_row = QFormLayout()
        token_row.addRow(self.token_edit)
        api_form.addRow("Токен API:", self.token_edit)
        api_form.addRow("", self.show_token_btn)

        self.base_url_edit = QLineEdit()
        api_form.addRow("Базовый URL:", self.base_url_edit)

        self.lang_combo = QComboBox()
        self.lang_combo.addItems(["ru", "en"])
        api_form.addRow("Язык ответов:", self.lang_combo)

        self.min_delay_spin = QDoubleSpinBox()
        self.min_delay_spin.setRange(3.0, 30.0)
        self.min_delay_spin.setSingleStep(0.5)
        self.min_delay_spin.setSuffix(" сек")
        api_form.addRow("Мин. задержка между запросами:", self.min_delay_spin)

        self.max_retries_spin = QSpinBox()
        self.max_retries_spin.setRange(0, 10)
        api_form.addRow("Макс. повторов при ошибке:", self.max_retries_spin)

        layout.addWidget(api_box)

        cycle_box = QGroupBox("Цикл обновления")
        cycle_form = QFormLayout(cycle_box)
        self.interval_spin = QSpinBox()
        self.interval_spin.setRange(1, 180)
        self.interval_spin.setSuffix(" мин")
        cycle_form.addRow("Интервал цикла:", self.interval_spin)
        self.autostart_chk = QCheckBox("Автоматически запускать при старте приложения")
        cycle_form.addRow(self.autostart_chk)
        self.notify_sales_chk = QCheckBox("Уведомлять о продажах")
        cycle_form.addRow(self.notify_sales_chk)
        self.sound_sale_chk = QCheckBox("Звуковое оповещение о продаже")
        cycle_form.addRow(self.sound_sale_chk)
        layout.addWidget(cycle_box)

        # --- Глобальные лимиты Lolzteam ---
        limits_box = QGroupBox("Лимиты поднятий и закреплений")
        limits_form = QFormLayout(limits_box)

        btn_autodetect = QPushButton("🔍 Определить автоматически с API")
        btn_autodetect.clicked.connect(self._autodetect_limits)
        limits_form.addRow(btn_autodetect)
        self.autodetect_status = QLabel("")
        self.autodetect_status.setWordWrap(True)
        self.autodetect_status.setStyleSheet("color:#9e9e9e; font-size:10pt;")
        limits_form.addRow(self.autodetect_status)

        self.bumps_per_acc_spin = QSpinBox()
        self.bumps_per_acc_spin.setRange(1, 24)
        limits_form.addRow("Поднятий на аккаунт в сутки:", self.bumps_per_acc_spin)
        hint_b = QLabel("Стандартно 3 (Lolzteam Market). Если у вас VIP/Premium — нажмите кнопку выше.")
        hint_b.setStyleSheet("color:#9e9e9e; font-size:10pt;")
        limits_form.addRow(hint_b)

        self.stick_slots_total_spin = QSpinBox()
        self.stick_slots_total_spin.setRange(0, 100)
        limits_form.addRow("Всего слотов закреплений:", self.stick_slots_total_spin)
        hint_s = QLabel(
            "Сколько всего аккаунтов можно держать закреплёнными одновременно. "
            "Зависит от уровня продавца — нажмите «Определить автоматически» чтобы взять с API."
        )
        hint_s.setWordWrap(True)
        hint_s.setStyleSheet("color:#9e9e9e; font-size:10pt;")
        limits_form.addRow(hint_s)

        self.progress_label = QLabel("Прогресс: —")
        self.progress_label.setStyleSheet(
            "color:#4caf50; font-weight:600; padding:8px; "
            "background:#111; border:1px solid #2a2a2a; border-radius:4px;"
        )
        limits_form.addRow(self.progress_label)

        layout.addWidget(limits_box)

        # --- Интерфейс ---
        ui_box = QGroupBox("Интерфейс")
        ui_form = QFormLayout(ui_box)
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["dark", "light"])
        ui_form.addRow("Тема:", self.theme_combo)
        self.rows_spin = QSpinBox()
        self.rows_spin.setRange(10, 500)
        ui_form.addRow("Строк в таблице:", self.rows_spin)
        layout.addWidget(ui_box)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _autodetect_limits(self) -> None:
        win = self.window().parent() if self.window() else None
        # ищем main window для доступа к client
        client = None
        w = self
        while w is not None:
            if hasattr(w, "client"):
                client = getattr(w, "client")
                break
            w = w.parent()
        if client is None:
            QMessageBox.warning(self, "Ошибка", "API-клиент недоступен — откройте окно из главного меню")
            return
        self.autodetect_status.setText("Запрос к API… подождите")
        self.autodetect_status.repaint()

        try:
            limits = client.detect_limits()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Ошибка автоопределения", str(exc))
            self.autodetect_status.setText(f"⚠ {exc}")
            return

        bpa = limits.get("bumps_per_account")
        sst = limits.get("stick_slots_total")
        msg_parts = []
        if bpa is not None:
            self.bumps_per_acc_spin.setValue(int(bpa))
            msg_parts.append(f"bump/акк/сутки = {bpa}")
        if sst is not None:
            self.stick_slots_total_spin.setValue(int(sst))
            msg_parts.append(f"слотов закреплений = {sst}")

        if msg_parts:
            self.autodetect_status.setText(
                "<span style='color:#4caf50'>✓ Применено: "
                + ", ".join(msg_parts) + "</span>"
            )
        else:
            self.autodetect_status.setText(
                "<span style='color:#f44336'>API не вернул нужные поля. "
                "Проверьте логи — там перечислены ключи /me и items.</span>"
            )

    def _refresh_progress(self) -> None:
        from app.db.session import get_session
        from app.db.models import Niche
        from sqlalchemy import select

        with get_session() as s:
            niches = list(s.execute(select(Niche)).scalars())

        total_planned_bumps = sum(n.bumps_per_day for n in niches)
        total_planned_stuck_bumps = sum(n.stuck_bumps_per_day for n in niches)
        total_stick_slots_used = sum(n.stick_slots for n in niches if n.auto_stick)

        bumps_done = niche_manager.global_bumps_today(stuck=False)
        stuck_bumps_done = niche_manager.global_bumps_today(stuck=True)
        currently_stuck = niche_manager.total_stuck_count()
        global_stick = settings_store.get_global_stick_slots()

        text = (
            f"🔺 Обычных bump-ов сегодня:  <b>{bumps_done}</b> / {total_planned_bumps or '∞'}<br>"
            f"🔺📌 Bump закреплённых:     <b>{stuck_bumps_done}</b> / {total_planned_stuck_bumps or '∞'}<br>"
            f"📌 Закреплено сейчас:       <b>{currently_stuck}</b> / {global_stick}  "
            f"(плановых слотов: {total_stick_slots_used})"
        )
        self.progress_label.setText(text)

    def _toggle_token(self, checked: bool) -> None:
        self.token_edit.setEchoMode(QLineEdit.EchoMode.Normal if checked else QLineEdit.EchoMode.Password)
        self.show_token_btn.setText("Скрыть" if checked else "Показать")

    def _load(self) -> None:
        self.token_edit.setText(settings_store.load_token() or self.settings.api_token)
        self.base_url_edit.setText(self.settings.api_base_url)
        self.lang_combo.setCurrentText(self.settings.api_lang)
        self.min_delay_spin.setValue(self.settings.api_min_delay)
        self.max_retries_spin.setValue(self.settings.api_max_retries)
        self.interval_spin.setValue(self.settings.cycle_interval_minutes)
        self.autostart_chk.setChecked(self.settings.cycle_autostart)
        self.notify_sales_chk.setChecked(self.settings.notify_sales)
        self.sound_sale_chk.setChecked(self.settings.sound_on_sale)
        self.theme_combo.setCurrentText(self.settings.theme)
        self.rows_spin.setValue(self.settings.rows_per_page)
        self.bumps_per_acc_spin.setValue(settings_store.get_global_bumps_per_account())
        self.stick_slots_total_spin.setValue(settings_store.get_global_stick_slots())
        self._refresh_progress()

    def accept(self) -> None:
        token = self.token_edit.text().strip()
        if token:
            settings_store.save_token(token)
            self.settings.api_token = token

        self.settings.api_base_url = self.base_url_edit.text().strip() or self.settings.api_base_url
        self.settings.api_lang = self.lang_combo.currentText()
        self.settings.api_min_delay = float(self.min_delay_spin.value())
        self.settings.api_max_retries = int(self.max_retries_spin.value())
        self.settings.cycle_interval_minutes = int(self.interval_spin.value())
        self.settings.cycle_autostart = self.autostart_chk.isChecked()
        self.settings.notify_sales = self.notify_sales_chk.isChecked()
        self.settings.sound_on_sale = self.sound_sale_chk.isChecked()
        self.settings.theme = self.theme_combo.currentText()
        self.settings.rows_per_page = int(self.rows_spin.value())

        settings_store.set_kv("api_base_url", self.settings.api_base_url)
        settings_store.set_kv("api_lang", self.settings.api_lang)
        settings_store.set_kv("cycle_interval_minutes", str(self.settings.cycle_interval_minutes))
        settings_store.set_kv("ui_theme", self.settings.theme)
        settings_store.set_global_bumps_per_account(self.bumps_per_acc_spin.value())
        settings_store.set_global_stick_slots(self.stick_slots_total_spin.value())

        super().accept()
