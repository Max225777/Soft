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
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.config import Settings
from app.core import niche_manager
from app.services import settings_store
from app.ui.widgets.async_worker import AsyncCall
from app.services.crypto import mask_token


class SettingsDialog(QDialog):
    def __init__(self, settings: Settings, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Налаштування")
        # Прямокутне (горизонтальне) вікно — поміщається на 1280×720
        self.resize(1180, 660)
        self.setMinimumSize(960, 520)
        self.settings = settings
        self._build_ui()
        self._load()

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)

        # Прокручувана область з 2 колонками
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        outer.addWidget(scroll, 1)

        content = QWidget()
        scroll.setWidget(content)
        cols = QHBoxLayout(content)
        cols.setSpacing(12)

        left_col = QVBoxLayout()
        right_col = QVBoxLayout()
        cols.addLayout(left_col, 1)
        cols.addLayout(right_col, 1)

        # ===== ЛІВА КОЛОНКА =====

        # --- API ---
        api_box = QGroupBox("API Lolzteam Market")
        api_form = QFormLayout(api_box)
        self.token_edit = QLineEdit()
        self.token_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.token_edit.setPlaceholderText("Вставте токен (scope: read+post+market)")
        self.show_token_btn = QPushButton("Показати")
        self.show_token_btn.setCheckable(True)
        self.show_token_btn.toggled.connect(self._toggle_token)

        api_form.addRow("Токен API:", self.token_edit)
        api_form.addRow("", self.show_token_btn)

        self.base_url_edit = QLineEdit()
        api_form.addRow("Базовий URL:", self.base_url_edit)

        self.lang_combo = QComboBox()
        self.lang_combo.addItems(["ru", "en"])
        api_form.addRow("Мова відповідей:", self.lang_combo)

        self.min_delay_spin = QDoubleSpinBox()
        self.min_delay_spin.setRange(0.3, 30.0)
        self.min_delay_spin.setSingleStep(0.1)
        self.min_delay_spin.setSuffix(" сек")
        api_form.addRow("Мін. пауза між запитами:", self.min_delay_spin)

        self.max_retries_spin = QSpinBox()
        self.max_retries_spin.setRange(0, 10)
        api_form.addRow("Макс. повторів при помилці:", self.max_retries_spin)
        left_col.addWidget(api_box)

        # --- Цикл ---
        cycle_box = QGroupBox("Цикл оновлення")
        cycle_form = QFormLayout(cycle_box)
        self.interval_spin = QSpinBox()
        self.interval_spin.setRange(1, 86400)
        self.interval_spin.setSuffix(" сек")
        cycle_form.addRow("Інтервал циклу (сек):", self.interval_spin)
        self.autostart_chk = QCheckBox("Автоматично запускати при старті")
        cycle_form.addRow(self.autostart_chk)
        self.notify_sales_chk = QCheckBox("Сповіщати про продажі")
        cycle_form.addRow(self.notify_sales_chk)
        self.sound_sale_chk = QCheckBox("Звуковий сигнал на продаж")
        cycle_form.addRow(self.sound_sale_chk)
        left_col.addWidget(cycle_box)

        # --- Інтерфейс ---
        ui_box = QGroupBox("Інтерфейс")
        ui_form = QFormLayout(ui_box)
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["dark", "light"])
        ui_form.addRow("Тема:", self.theme_combo)
        self.rows_spin = QSpinBox()
        self.rows_spin.setRange(10, 500)
        ui_form.addRow("Рядків у таблиці:", self.rows_spin)
        left_col.addWidget(ui_box)
        left_col.addStretch()

        # ===== ПРАВА КОЛОНКА =====

        # --- Глобальні ліміти ---
        limits_box = QGroupBox("Ліміти підйомів і закріплень")
        limits_form = QFormLayout(limits_box)

        btn_autodetect = QPushButton("🔍 Визначити автоматично з API")
        btn_autodetect.clicked.connect(self._autodetect_limits)
        limits_form.addRow(btn_autodetect)
        self.autodetect_status = QLabel("")
        self.autodetect_status.setWordWrap(True)
        self.autodetect_status.setStyleSheet("color:#9e9e9e; font-size:10pt;")
        limits_form.addRow(self.autodetect_status)

        self.bumps_per_acc_spin = QSpinBox()
        self.bumps_per_acc_spin.setRange(1, 24)
        limits_form.addRow("Підйомів на 1 акк в добу:", self.bumps_per_acc_spin)
        hint_b = QLabel("Стандартно 3 (Lolzteam). Якщо у вас VIP/Premium — натисніть кнопку вище.")
        hint_b.setWordWrap(True)
        hint_b.setStyleSheet("color:#9e9e9e; font-size:10pt;")
        limits_form.addRow(hint_b)

        self.global_bumps_per_day_spin = QSpinBox()
        self.global_bumps_per_day_spin.setRange(0, 10000)
        limits_form.addRow("Всього підйомів на день (всі ніші):", self.global_bumps_per_day_spin)
        hint_g = QLabel(
            "Загальний ліміт на ВСІ ніші. Наприклад: «не більше 200 bump на день, "
            "розподіляй між нішами як вмієш». 0 — без обмеження."
        )
        hint_g.setWordWrap(True)
        hint_g.setStyleSheet("color:#9e9e9e; font-size:10pt;")
        limits_form.addRow(hint_g)

        self.stick_slots_total_spin = QSpinBox()
        self.stick_slots_total_spin.setRange(0, 100)
        limits_form.addRow("Всього слотів закріплень:", self.stick_slots_total_spin)
        hint_s = QLabel(
            "Скільки акк можна тримати закріпленими одночасно. "
            "Залежить від рівня продавця — натисніть «Визначити автоматично»."
        )
        hint_s.setWordWrap(True)
        hint_s.setStyleSheet("color:#9e9e9e; font-size:10pt;")
        limits_form.addRow(hint_s)

        self.progress_label = QLabel("Прогрес: —")
        self.progress_label.setWordWrap(True)
        self.progress_label.setTextFormat(Qt.TextFormat.RichText)
        self.progress_label.setStyleSheet(
            "color:#4caf50; font-weight:600; padding:8px; "
            "background:#111; border:1px solid #2a2a2a; border-radius:4px;"
        )
        limits_form.addRow(self.progress_label)

        right_col.addWidget(limits_box)
        right_col.addStretch()

        # ===== Кнопки внизу (поза прокруткою) =====
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        outer.addWidget(buttons)

    def closeEvent(self, event) -> None:  # noqa: N802
        prev = getattr(self, "_autodetect_call", None)
        if prev is not None:
            try:
                prev.cancel()
            except Exception:  # noqa: BLE001
                pass
        super().closeEvent(event)

    def _autodetect_limits(self) -> None:
        # client може бути встановлений напряму як атрибут диалога,
        # або знайдений у дереві предків
        client = getattr(self, "client", None)
        if client is None:
            w = self.parent()
            while w is not None:
                if hasattr(w, "client"):
                    client = getattr(w, "client")
                    break
                w = w.parent()
        if client is None:
            QMessageBox.warning(self, "Помилка", "API-клієнт недоступний — відкрийте діалог з головного меню")
            return
        self.autodetect_status.setText("Запит до API… зачекайте")
        # Cancel попередній якщо є
        prev = getattr(self, "_autodetect_call", None)
        if prev is not None:
            try:
                prev.cancel()
            except Exception:  # noqa: BLE001
                pass
        self._autodetect_call = AsyncCall(
            client.detect_limits,
            on_done=self._on_autodetect_done,
            on_error=self._on_autodetect_error,
            parent=self,
        )
        self._autodetect_call.start()

    def _on_autodetect_done(self, limits: dict) -> None:
        bpa = limits.get("bumps_per_account") if isinstance(limits, dict) else None
        sst = limits.get("stick_slots_total") if isinstance(limits, dict) else None
        msg_parts = []
        if bpa is not None:
            self.bumps_per_acc_spin.setValue(int(bpa))
            msg_parts.append(f"bump/акк/сутки = {bpa}")
        if sst is not None:
            self.stick_slots_total_spin.setValue(int(sst))
            msg_parts.append(f"слотов закреплений = {sst}")
        if msg_parts:
            self.autodetect_status.setText(
                "<span style='color:#4caf50'>✓ Применено: " + ", ".join(msg_parts) + "</span>"
            )
        else:
            self.autodetect_status.setText(
                "<span style='color:#f44336'>API не вернул нужные поля. "
                "Проверьте логи — там перечислены ключи /me и items.</span>"
            )

    def _on_autodetect_error(self, exc: Exception) -> None:
        self.autodetect_status.setText(f"<span style='color:#f44336'>⚠ {exc}</span>")

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

        global_max = settings_store.get_global_bumps_per_day()
        plan_str = str(total_planned_bumps) if total_planned_bumps else "∞"
        if global_max:
            plan_str += f" (стеля {global_max})"

        text = (
            f"📊 <b>План bump на день для ВСІХ ніш разом: {total_planned_bumps}</b><br>"
            f"🔺 Bump звичайних сьогодні:  <b>{bumps_done}</b> / {plan_str}<br>"
            f"🔺📌 Bump закріплених:     <b>{stuck_bumps_done}</b> / {total_planned_stuck_bumps or '∞'}<br>"
            f"📌 Закріплено зараз:       <b>{currently_stuck}</b> / {global_stick}  "
            f"(планових слотів: {total_stick_slots_used})"
        )
        self.progress_label.setText(text)

    def _toggle_token(self, checked: bool) -> None:
        self.token_edit.setEchoMode(QLineEdit.EchoMode.Normal if checked else QLineEdit.EchoMode.Password)
        self.show_token_btn.setText("Сховати" if checked else "Показати")

    def _load(self) -> None:
        self.token_edit.setText(settings_store.load_token() or self.settings.api_token)
        self.base_url_edit.setText(self.settings.api_base_url)
        self.lang_combo.setCurrentText(self.settings.api_lang)
        self.min_delay_spin.setValue(self.settings.api_min_delay)
        self.max_retries_spin.setValue(self.settings.api_max_retries)
        self.interval_spin.setValue(self.settings.cycle_interval_seconds)
        self.autostart_chk.setChecked(self.settings.cycle_autostart)
        self.notify_sales_chk.setChecked(self.settings.notify_sales)
        self.sound_sale_chk.setChecked(self.settings.sound_on_sale)
        self.theme_combo.setCurrentText(self.settings.theme)
        self.rows_spin.setValue(self.settings.rows_per_page)
        self.bumps_per_acc_spin.setValue(settings_store.get_global_bumps_per_account())
        self.stick_slots_total_spin.setValue(settings_store.get_global_stick_slots())
        self.global_bumps_per_day_spin.setValue(settings_store.get_global_bumps_per_day())
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
        self.settings.cycle_interval_seconds = int(self.interval_spin.value())
        self.settings.cycle_autostart = self.autostart_chk.isChecked()
        self.settings.notify_sales = self.notify_sales_chk.isChecked()
        self.settings.sound_on_sale = self.sound_sale_chk.isChecked()
        self.settings.theme = self.theme_combo.currentText()
        self.settings.rows_per_page = int(self.rows_spin.value())

        settings_store.set_kv("api_base_url", self.settings.api_base_url)
        settings_store.set_kv("api_lang", self.settings.api_lang)
        settings_store.set_kv("cycle_interval_seconds", str(self.settings.cycle_interval_seconds))
        settings_store.set_kv("ui_theme", self.settings.theme)
        settings_store.set_global_bumps_per_account(self.bumps_per_acc_spin.value())
        settings_store.set_global_stick_slots(self.stick_slots_total_spin.value())
        settings_store.set_global_bumps_per_day(self.global_bumps_per_day_spin.value())

        super().accept()
