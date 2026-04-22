"""Компактная карточка ниши с ключевыми метриками."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from app.core.niche_manager import niche_summary
from app.db.models import Niche


class NicheCard(QFrame):
    def __init__(self, niche: Niche, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.niche = niche
        self.setObjectName("NicheCard")
        self.setStyleSheet(
            "QFrame#NicheCard { background: #1f1f1f; border: 1px solid #2a2a2a; border-radius: 6px; }"
            "QFrame#NicheCard:hover { border-color: #4caf50; }"
            "QLabel[role='metric_label'] { color:#7a7a7a; font-size:9pt; }"
            "QLabel[role='metric_value'] { color:#e6e6e6; font-size:11pt; font-weight:600; }"
            "QLabel[role='metric_green'] { color:#4caf50; font-size:11pt; font-weight:600; }"
            "QLabel[role='metric_blue']  { color:#2196f3; font-size:11pt; font-weight:600; }"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(2)

        # Заголовок: имя + бейджи автоматизации
        header = QHBoxLayout()
        title = QLabel(niche.name)
        title.setStyleSheet("font-size: 12pt; font-weight: 700; color: #e6e6e6;")
        header.addWidget(title)
        header.addStretch()
        for flag, text in [
            (niche.auto_bump, "🔺"),
            (niche.auto_stick, "📌"),
            (niche.auto_bump_stuck, "🔺📌"),
        ]:
            if flag:
                b = QLabel(text)
                b.setStyleSheet("font-size: 11pt;")
                header.addWidget(b)
        layout.addLayout(header)

        # Метрики в 2 ряда x 3 колонки
        summary = niche_summary(niche)
        grid = QGridLayout()
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(0)

        self._metric(grid, 0, 0, "На продаже", f"{summary['count']}", "value")
        self._metric(grid, 0, 1, "Продано за 30д", f"{summary['sold_count']}", "blue")
        self._metric(grid, 0, 2, "Прибыль 30д", f"{summary['sold_profit']:.0f} $", "green")

        self._metric(grid, 1, 0, "Ø цена", f"{summary['avg_price']:.2f}", "value")
        self._metric(grid, 1, 1, "Bumps left", f"{summary['bumps_left']}", "value")
        self._metric(grid, 1, 2,
                     "Stick slots",
                     f"{niche.stick_slots}" if niche.auto_stick else "—",
                     "value")

        layout.addLayout(grid)

    @staticmethod
    def _metric(grid: QGridLayout, row: int, col: int, label: str, value: str, style: str) -> None:
        wrapper = QVBoxLayout()
        wrapper.setSpacing(0)
        lbl = QLabel(label)
        lbl.setProperty("role", "metric_label")
        val = QLabel(value)
        val.setProperty("role", {
            "value": "metric_value",
            "green": "metric_green",
            "blue":  "metric_blue",
        }.get(style, "metric_value"))
        wrapper.addWidget(lbl)
        wrapper.addWidget(val)
        wrapper_widget = QFrame()
        wrapper_widget.setLayout(wrapper)
        grid.addWidget(wrapper_widget, row, col, Qt.AlignmentFlag.AlignLeft)
