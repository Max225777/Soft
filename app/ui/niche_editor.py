"""Диалог создания/редактирования ниши.

Главный (и единственный) фильтр — приватный тег Lolzteam Market.
Остальные настройки касаются автоматизации (поднятий и закреплений).
"""

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
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.api.client import LolzMarketClient
from app.core import niche_manager
from app.core.tags import fetch_tags
from app.db.models import Niche
from app.services import settings_store
from app.ui.widgets.hourly_schedule import HourlyScheduleWidget


class NicheEditor(QDialog):
    def __init__(
        self,
        niche: Niche | None = None,
        client: LolzMarketClient | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Редактирование ниши" if niche else "Новая ниша")
        # компактный размер, остальное — внутри прокрутки
        self.resize(1100, 700)
        self.setMinimumSize(880, 520)
        self.niche = niche
        self.client = client
        self._tags_cache: list[dict] = []
        self._build_ui()
        self._load_tags()
        if niche:
            self._load(niche)

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)

        # --- прокручиваемая область с двумя колонками ---
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        outer.addWidget(scroll, 1)

        content = QWidget()
        scroll.setWidget(content)
        columns = QHBoxLayout(content)
        columns.setSpacing(12)

        left_col = QVBoxLayout()
        right_col = QVBoxLayout()
        columns.addLayout(left_col, 1)
        columns.addLayout(right_col, 1)

        # ===== ЛЕВАЯ КОЛОНКА =====
        # --- Основное: имя + тег ---
        main_box = QGroupBox("Основное")
        main_form = QFormLayout(main_box)
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Например: UA Telegram Premium")
        main_form.addRow("Название ниши *:", self.name_edit)

        tag_row = QVBoxLayout()
        self.tag_combo = QComboBox()
        self.tag_combo.addItem("— без тега —", None)
        tag_row.addWidget(self.tag_combo)

        btn_refresh_tags = QPushButton("🔄 Обновить список тегов с Lolzteam")
        btn_refresh_tags.clicked.connect(self._load_tags)
        tag_row.addWidget(btn_refresh_tags)

        self.tags_status = QLabel("")
        self.tags_status.setWordWrap(True)
        self.tags_status.setStyleSheet("color:#9e9e9e; font-size:10pt;")
        tag_row.addWidget(self.tags_status)

        hint_tag = QLabel(
            "<b>Главный и единственный критерий ниши</b> — приватный тег "
            "(метка) с lzt.market. Все аккаунты с выбранным тегом "
            "автоматически попадут в эту нишу."
        )
        hint_tag.setWordWrap(True)
        hint_tag.setStyleSheet("color:#9e9e9e; font-size:10pt;")
        tag_row.addWidget(hint_tag)

        main_form.addRow("Приватный тег Lolzteam:", tag_row)
        left_col.addWidget(main_box)

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
        left_col.addWidget(price_box)

        # --- Приоритет ---
        priority_box = QGroupBox("Приоритетный аккаунт")
        priority_form = QFormLayout(priority_box)
        self.priority_item = QSpinBox()
        self.priority_item.setRange(0, 999_999_999)
        self.priority_item.setSpecialValueText("не задан")
        priority_form.addRow("item_id приоритетного аккаунта:", self.priority_item)
        left_col.addWidget(priority_box)

        # --- Расписание по часам (на левой колонке снизу) ---
        schedule_box = QGroupBox("📈 Расписание поднятий по часам")
        schedule_layout = QVBoxLayout(schedule_box)
        self.schedule_widget = HourlyScheduleWidget()
        schedule_layout.addWidget(self.schedule_widget)
        left_col.addWidget(schedule_box)

        left_col.addStretch()

        # ===== ПРАВАЯ КОЛОНКА =====
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
        self.niche_progress_label.setWordWrap(True)
        bump_form.addRow(self.niche_progress_label)
        right_col.addWidget(bump_box)

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
            f"Всего у вас доступно {global_slots} слотов закреплений (см. Настройки → Лимиты)."
        )
        hint_stick.setWordWrap(True)
        hint_stick.setStyleSheet("color:#9e9e9e; font-size:10pt;")
        stick_form.addRow(hint_stick)
        right_col.addWidget(stick_box)

        # --- Поднятие закреплённых ---
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
        hint_stuck2 = QLabel("Lolzteam: bump одного аккаунта не чаще ~1 раза в час.")
        hint_stuck2.setWordWrap(True)
        hint_stuck2.setStyleSheet("color:#9e9e9e; font-size:10pt;")
        stuck_form.addRow(hint_stuck2)
        right_col.addWidget(stuck_box)

        right_col.addStretch()

        # --- Кнопки сохранения внизу диалога (вне прокрутки) ---
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        outer.addWidget(buttons)

    def _load_tags(self) -> None:
        try:
            tags = fetch_tags(self.client)
        except Exception as exc:  # noqa: BLE001
            tags = []
            self.tags_status.setText(f"⚠ Не удалось получить теги: {exc}")
        else:
            if tags:
                self.tags_status.setText(
                    f"<span style='color:#4caf50'>Найдено тегов: <b>{len(tags)}</b></span>"
                )
            else:
                self.tags_status.setText(
                    "<span style='color:#f44336'>Тегов не найдено.</span> "
                    "В Lolzteam теги приходят только в составе аккаунтов — "
                    "нажмите «🔄 Обновить список тегов с Lolzteam» (запросит ваши items с API), "
                    "либо «🔄 Обновить с API» на главной странице."
                )

        self._tags_cache = tags

        current = self.tag_combo.currentData()
        self.tag_combo.clear()
        self.tag_combo.addItem("— без тега —", None)
        for t in tags:
            label = f"#{t['id']}  {t['title']}" if t["title"] else f"#{t['id']}"
            self.tag_combo.addItem(label, int(t["id"]))
        if current is not None:
            idx = self.tag_combo.findData(current)
            if idx >= 0:
                self.tag_combo.setCurrentIndex(idx)

    def _load(self, n: Niche) -> None:
        self.name_edit.setText(n.name)
        if n.tag_id:
            idx = self.tag_combo.findData(int(n.tag_id))
            if idx < 0:
                label = f"#{n.tag_id}  {n.tag_name or ''}"
                self.tag_combo.addItem(label, int(n.tag_id))
                idx = self.tag_combo.count() - 1
            self.tag_combo.setCurrentIndex(idx)
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
        tag_id = self.tag_combo.currentData()
        tag_name = ""
        if tag_id is not None:
            for t in self._tags_cache:
                if int(t["id"]) == int(tag_id):
                    tag_name = t["title"]
                    break
        return {
            "name": self.name_edit.text().strip(),
            "tag_id": int(tag_id) if tag_id is not None else None,
            "tag_name": tag_name,
            # фильтры по категории / стране / цене / словам — больше не используем
            "category": "",
            "country": "",
            "price_min": None,
            "price_max": None,
            "keywords": "",
            "exact_title": "",
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
