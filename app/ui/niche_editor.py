"""Диалог создания/редактирования ниши."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QSpinBox,
    QVBoxLayout,
)

from app.core import niche_manager
from app.db.models import Niche
from app.services import settings_store
from app.ui.widgets.hourly_schedule import HourlyScheduleWidget


class NicheEditor(QDialog):
    def __init__(self, niche: Niche | None = None, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Редактирование ниши" if niche else "Новая ниша")
        self.resize(620, 820)
        self.niche = niche
        self._build_ui()
        if niche:
            self._load(niche)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        # --- Основное ---
        main_box = QGroupBox("Основное")
        main_form = QFormLayout(main_box)
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Например: UA Telegram Premium")
        main_form.addRow("Название ниши *:", self.name_edit)
        self.category_edit = QLineEdit()
        self.category_edit.setText("telegram")
        main_form.addRow("Категория:", self.category_edit)
        self.country_edit = QLineEdit()
        self.country_edit.setPlaceholderText("UA / RU / US / … (пусто = любая)")
        main_form.addRow("Страна происхождения:", self.country_edit)
        layout.addWidget(main_box)

        # --- Фильтры аккаунтов ---
        filter_box = QGroupBox("Фильтры аккаунтов")
        filter_form = QFormLayout(filter_box)
        self.price_min = QDoubleSpinBox()
        self.price_min.setRange(0, 1_000_000)
        self.price_min.setSpecialValueText("—")
        self.price_min.setSuffix(" $")
        filter_form.addRow("Цена от:", self.price_min)
        self.price_max = QDoubleSpinBox()
        self.price_max.setRange(0, 1_000_000)
        self.price_max.setSpecialValueText("—")
        self.price_max.setSuffix(" $")
        filter_form.addRow("Цена до:", self.price_max)
        self.keywords_edit = QLineEdit()
        self.keywords_edit.setPlaceholderText("через запятую: premium, verified, aged")
        filter_form.addRow("Ключевые слова:", self.keywords_edit)

        self.exact_title_edit = QLineEdit()
        self.exact_title_edit.setPlaceholderText("напр.: «UA Telegram 2020» — точная фраза в названии (опц.)")
        filter_form.addRow("Точное название:", self.exact_title_edit)
        hint_et = QLabel(
            "Если задано — в нишу попадут только аккаунты, у которых эта фраза\n"
            "встречается в названии. Работает отдельно от «Ключевых слов»."
        )
        hint_et.setStyleSheet("color:#9e9e9e; font-size:10pt;")
        filter_form.addRow(hint_et)
        layout.addWidget(filter_box)

        # --- Ценообразование ---
        price_box = QGroupBox("Ценообразование")
        price_form = QFormLayout(price_box)
        self.default_cost = QDoubleSpinBox()
        self.default_cost.setRange(0, 1_000_000)
        self.default_cost.setDecimals(2)
        self.default_cost.setSuffix(" $")
        price_form.addRow("Себестоимость по умолчанию:", self.default_cost)
        self.markup = QDoubleSpinBox()
        self.markup.setRange(0, 1_000_000)
        self.markup.setDecimals(2)
        self.markup.setSuffix(" $")
        price_form.addRow("Наценка (сумма):", self.markup)
        layout.addWidget(price_box)

        # --- Автоподнятие обычных ---
        bump_box = QGroupBox("🔺 Автоподнятие (обычные аккаунты)")
        bump_form = QFormLayout(bump_box)
        self.auto_bump_chk = QCheckBox("Включить автоподнятие")
        bump_form.addRow(self.auto_bump_chk)
        self.bumps_per_day = QSpinBox()
        self.bumps_per_day.setRange(0, 500)
        self.bumps_per_day.setSpecialValueText("не ограничено")
        bump_form.addRow("Поднятий в сутки от этой ниши:", self.bumps_per_day)

        self.niche_progress_label = QLabel("Сегодня использовано: —")
        self.niche_progress_label.setStyleSheet("color:#2196f3;")
        bump_form.addRow(self.niche_progress_label)
        layout.addWidget(bump_box)

        # --- Расписание по часам ---
        schedule_box = QGroupBox("📈 Расписание поднятий по часам")
        schedule_layout = QVBoxLayout(schedule_box)
        self.schedule_widget = HourlyScheduleWidget()
        schedule_layout.addWidget(self.schedule_widget)
        layout.addWidget(schedule_box)

        # --- Автозакрепление ---
        stick_box = QGroupBox("📌 Автозакрепление")
        stick_form = QFormLayout(stick_box)
        self.auto_stick_chk = QCheckBox("Включить автозакрепление")
        stick_form.addRow(self.auto_stick_chk)
        self.stick_slots = QSpinBox()
        self.stick_slots.setRange(0, 50)
        stick_form.addRow("Слотов занимает эта ниша:", self.stick_slots)

        global_slots = settings_store.get_global_stick_slots()
        hint_stick = QLabel(
            f"Всего у вас доступно {global_slots} слотов закреплений (см. Настройки → Лимиты).\n"
            "Пример: если здесь 2 — бот будет держать закреплёнными 2 лучших аккаунта из этой ниши."
        )
        hint_stick.setStyleSheet("color:#9e9e9e; font-size:10pt;")
        stick_form.addRow(hint_stick)
        layout.addWidget(stick_box)

        # --- Поднятие закреплённых (отдельный пул) ---
        stuck_box = QGroupBox("🔺📌 Поднятие закреплённых (отдельный пул)")
        stuck_form = QFormLayout(stuck_box)
        self.auto_bump_stuck_chk = QCheckBox("Поднимать закреплённые аккаунты")
        stuck_form.addRow(self.auto_bump_stuck_chk)
        self.stuck_bumps_per_day = QSpinBox()
        self.stuck_bumps_per_day.setRange(0, 500)
        self.stuck_bumps_per_day.setSpecialValueText("не ограничено")
        stuck_form.addRow("Поднятий закреплённых в сутки:", self.stuck_bumps_per_day)
        self.stuck_cooldown = QSpinBox()
        self.stuck_cooldown.setRange(0, 1440)
        self.stuck_cooldown.setSuffix(" мин")
        self.stuck_cooldown.setValue(60)
        stuck_form.addRow("Пауза между bump одного акк:", self.stuck_cooldown)
        hint_stuck = QLabel(
            "Lolzteam разрешает поднимать аккаунт не чаще ~1 раза в час.\n"
            "Бот не будет bump-ать один и тот же закреплённый чаще указанной паузы."
        )
        hint_stuck.setStyleSheet("color:#9e9e9e; font-size:10pt;")
        stuck_form.addRow(hint_stuck)
        layout.addWidget(stuck_box)

        # --- Приоритет ---
        priority_box = QGroupBox("Приоритетный аккаунт")
        priority_form = QFormLayout(priority_box)
        self.priority_item = QSpinBox()
        self.priority_item.setRange(0, 999_999_999)
        self.priority_item.setSpecialValueText("не задан")
        priority_form.addRow("item_id приоритетного аккаунта:", self.priority_item)
        layout.addWidget(priority_box)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _load(self, n: Niche) -> None:
        self.name_edit.setText(n.name)
        self.category_edit.setText(n.category or "telegram")
        self.country_edit.setText(n.country or "")
        self.price_min.setValue(n.price_min or 0)
        self.price_max.setValue(n.price_max or 0)
        self.keywords_edit.setText(n.keywords or "")
        self.exact_title_edit.setText(n.exact_title or "")
        self.default_cost.setValue(n.default_cost)
        self.markup.setValue(n.markup)
        self.auto_bump_chk.setChecked(n.auto_bump)
        self.bumps_per_day.setValue(n.bumps_per_day)
        self.auto_stick_chk.setChecked(n.auto_stick)
        self.stick_slots.setValue(n.stick_slots)
        self.auto_bump_stuck_chk.setChecked(n.auto_bump_stuck)
        self.stuck_bumps_per_day.setValue(n.stuck_bumps_per_day)
        self.stuck_cooldown.setValue(n.stuck_bump_cooldown_min)
        self.priority_item.setValue(n.priority_item_id or 0)
        self.schedule_widget.set_values(list(n.hourly_schedule or []))

        used = niche_manager.niche_bumps_today(n.id, stuck=False)
        self.niche_progress_label.setText(
            f"Сегодня использовано: <b>{used}</b> / {n.bumps_per_day or '∞'} "
            "(обычные bump-ы этой ниши)"
        )

    def values(self) -> dict:
        return {
            "name": self.name_edit.text().strip(),
            "category": self.category_edit.text().strip() or "telegram",
            "country": self.country_edit.text().strip(),
            "price_min": self.price_min.value() or None,
            "price_max": self.price_max.value() or None,
            "keywords": self.keywords_edit.text().strip(),
            "exact_title": self.exact_title_edit.text().strip(),
            "default_cost": float(self.default_cost.value()),
            "markup": float(self.markup.value()),
            "auto_bump": self.auto_bump_chk.isChecked(),
            "bumps_per_day": int(self.bumps_per_day.value()),
            "auto_stick": self.auto_stick_chk.isChecked(),
            "stick_slots": int(self.stick_slots.value()),
            "auto_bump_stuck": self.auto_bump_stuck_chk.isChecked(),
            "stuck_bumps_per_day": int(self.stuck_bumps_per_day.value()),
            "stuck_bump_cooldown_min": int(self.stuck_cooldown.value()),
            "hourly_schedule": self.schedule_widget.values(),
            "priority_item_id": int(self.priority_item.value()) or None,
        }
