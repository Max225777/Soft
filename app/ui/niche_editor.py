"""Диалог создания/редактирования ниши."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QLineEdit,
    QSpinBox,
    QVBoxLayout,
)

from app.db.models import Niche


class NicheEditor(QDialog):
    def __init__(self, niche: Niche | None = None, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Редактирование ниши" if niche else "Новая ниша")
        self.resize(520, 520)
        self.niche = niche
        self._build_ui()
        if niche:
            self._load(niche)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        main_box = QGroupBox("Основное")
        main_form = QFormLayout(main_box)
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Например: UA Telegram")
        main_form.addRow("Название ниши *:", self.name_edit)
        self.category_edit = QLineEdit()
        self.category_edit.setText("telegram")
        self.category_edit.setPlaceholderText("telegram (основная категория)")
        main_form.addRow("Категория:", self.category_edit)
        self.country_edit = QLineEdit()
        self.country_edit.setPlaceholderText("UA / RU / US / ...")
        main_form.addRow("Страна происхождения:", self.country_edit)
        layout.addWidget(main_box)

        filter_box = QGroupBox("Фильтры")
        filter_form = QFormLayout(filter_box)
        self.price_min = QDoubleSpinBox()
        self.price_min.setRange(0, 1_000_000)
        self.price_min.setSpecialValueText("—")
        filter_form.addRow("Цена от:", self.price_min)
        self.price_max = QDoubleSpinBox()
        self.price_max.setRange(0, 1_000_000)
        self.price_max.setSpecialValueText("—")
        filter_form.addRow("Цена до:", self.price_max)
        self.keywords_edit = QLineEdit()
        self.keywords_edit.setPlaceholderText("через запятую, например: premium, verified")
        filter_form.addRow("Ключевые слова:", self.keywords_edit)
        layout.addWidget(filter_box)

        auto_box = QGroupBox("Автоматизация")
        auto_form = QFormLayout(auto_box)
        self.auto_bump_chk = QCheckBox("Автоподнятие")
        auto_form.addRow(self.auto_bump_chk)
        self.bump_interval = QSpinBox()
        self.bump_interval.setRange(20, 1440)
        self.bump_interval.setSuffix(" мин")
        auto_form.addRow("Интервал поднятий:", self.bump_interval)
        self.auto_stick_chk = QCheckBox("Автозакрепление")
        auto_form.addRow(self.auto_stick_chk)
        self.priority_item = QSpinBox()
        self.priority_item.setRange(0, 999_999_999)
        self.priority_item.setSpecialValueText("не задан")
        auto_form.addRow("Приоритетный item_id:", self.priority_item)
        layout.addWidget(auto_box)

        price_box = QGroupBox("Ценообразование")
        price_form = QFormLayout(price_box)
        self.default_cost = QDoubleSpinBox()
        self.default_cost.setRange(0, 1_000_000)
        self.default_cost.setSuffix(" $")
        price_form.addRow("Себестоимость по умолчанию:", self.default_cost)
        self.markup = QDoubleSpinBox()
        self.markup.setRange(0, 1_000_000)
        self.markup.setDecimals(2)
        self.markup.setSuffix(" $")
        price_form.addRow("Наценка (сумма):", self.markup)
        layout.addWidget(price_box)

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
        self.auto_bump_chk.setChecked(n.auto_bump)
        self.bump_interval.setValue(n.bump_interval_min)
        self.auto_stick_chk.setChecked(n.auto_stick)
        self.priority_item.setValue(n.priority_item_id or 0)
        self.default_cost.setValue(n.default_cost)
        self.markup.setValue(n.markup)

    def values(self) -> dict:
        return {
            "name": self.name_edit.text().strip(),
            "category": self.category_edit.text().strip() or "telegram",
            "country": self.country_edit.text().strip(),
            "price_min": self.price_min.value() or None,
            "price_max": self.price_max.value() or None,
            "keywords": self.keywords_edit.text().strip(),
            "auto_bump": self.auto_bump_chk.isChecked(),
            "bump_interval_min": int(self.bump_interval.value()),
            "auto_stick": self.auto_stick_chk.isChecked(),
            "priority_item_id": int(self.priority_item.value()) or None,
            "default_cost": float(self.default_cost.value()),
            "markup": float(self.markup.value()),
        }
