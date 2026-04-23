"""24-часовая кривая распределения поднятий.

Интерактивный график: 24 точки (по одной на каждый час суток),
которые пользователь перетаскивает мышкой. Значение = количество bump-ов
в данном часу.
"""

from __future__ import annotations

import pyqtgraph as pg
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget


class HourlyScheduleWidget(QWidget):
    changed = Signal(list)  # новый список из 24 чисел

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        pg.setConfigOption("background", "#151515")
        pg.setConfigOption("foreground", "#e6e6e6")

        self._values: list[int] = [0] * 24
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        hint = QLabel(
            "Расписание поднятий по часам суток (0–23). Перетаскивайте точки, "
            "чтобы задать когда и сколько bump-ов делать. Сумма = всего поднятий в сутки."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color:#9e9e9e; font-size:10pt;")
        layout.addWidget(hint)

        self.plot = pg.PlotWidget()
        self.plot.setMinimumHeight(180)
        self.plot.setMouseEnabled(x=False, y=True)
        self.plot.setXRange(-0.5, 23.5, padding=0)
        self.plot.setYRange(0, 10, padding=0)
        self.plot.getAxis("bottom").setTicks([[(h, f"{h:02d}") for h in range(0, 24, 2)]])
        self.plot.setLabel("bottom", "Час суток")
        self.plot.setLabel("left", "Поднятий")
        layout.addWidget(self.plot)

        self._bars = pg.BarGraphItem(x=list(range(24)), height=self._values, width=0.85, brush="#4caf50")
        self.plot.addItem(self._bars)

        self._scatter = pg.ScatterPlotItem(
            x=list(range(24)),
            y=self._values,
            size=14,
            brush="#2196f3",
            pen=pg.mkPen("w", width=1),
        )
        self.plot.addItem(self._scatter)
        self.plot.scene().sigMouseClicked.connect(self._on_click)

        btn_row = QHBoxLayout()
        btn_reset = QPushButton("Сброс (0 во всех часах)")
        btn_reset.clicked.connect(lambda: self.set_values([0] * 24))
        btn_row.addWidget(btn_reset)

        btn_uniform = QPushButton("Распределить равномерно")
        btn_uniform.clicked.connect(self._distribute_uniform)
        btn_row.addWidget(btn_uniform)

        btn_row.addStretch()
        self.sum_label = QLabel("Сумма: 0")
        self.sum_label.setStyleSheet("color:#4caf50; font-weight:600;")
        btn_row.addWidget(self.sum_label)
        layout.addLayout(btn_row)

    def set_values(self, values: list[int]) -> None:
        if not values or len(values) != 24:
            values = [0] * 24
        self._values = [max(0, int(v)) for v in values]
        self._refresh()

    def values(self) -> list[int]:
        return list(self._values)

    # ---------- helpers ----------
    def _refresh(self) -> None:
        max_val = max(self._values + [10])
        self.plot.setYRange(0, max_val + 1, padding=0)
        self._bars.setOpts(x=list(range(24)), height=self._values, width=0.85)
        self._scatter.setData(x=list(range(24)), y=self._values)
        self.sum_label.setText(f"Сумма: {sum(self._values)}")
        self.changed.emit(self._values)

    def _distribute_uniform(self) -> None:
        total = sum(self._values) or 24
        base = total // 24
        extra = total % 24
        new = [base] * 24
        for i in range(extra):
            new[i] += 1
        self.set_values(new)

    def _on_click(self, ev) -> None:
        pos = self.plot.plotItem.vb.mapSceneToView(ev.scenePos())
        hour = int(round(pos.x()))
        count = int(round(max(0, pos.y())))
        if 0 <= hour < 24:
            self._values[hour] = count
            self._refresh()
