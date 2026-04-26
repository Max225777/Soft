"""24-часовая кривая распределения поднятий.

Интерактивный график: 24 точки (по одной на каждый час суток),
которые пользователь перетаскивает мышкой. Значение = количество bump-ов
в данном часу.
"""

from __future__ import annotations

import pyqtgraph as pg
from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)


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
        layout.setContentsMargins(0, 0, 0, 0)

        hint = QLabel(
            "Кликайте по столбцам — задаёте сколько bump-ов в этот час. "
            "Можно использовать «всего» снизу для авто-распределения."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color:#9e9e9e; font-size:10pt;")
        layout.addWidget(hint)

        self.plot = pg.PlotWidget()
        # достаточно большой и растягиваемый
        self.plot.setMinimumHeight(260)
        self.plot.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.plot.setMouseEnabled(x=False, y=True)
        self.plot.setXRange(-0.5, 23.5, padding=0)
        self.plot.setYRange(0, 10, padding=0)
        self.plot.getAxis("bottom").setTicks([[(h, f"{h:02d}") for h in range(0, 24)]])
        self.plot.setLabel("bottom", "Час суток")
        self.plot.setLabel("left", "Bump-ов")
        layout.addWidget(self.plot, 1)

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

        # --- управление расписанием ---
        ctrl_row = QHBoxLayout()
        ctrl_row.addWidget(QLabel("Всего в сутки:"))
        self.total_spin = QSpinBox()
        self.total_spin.setRange(0, 5000)
        self.total_spin.setValue(0)
        ctrl_row.addWidget(self.total_spin)

        btn_uniform = QPushButton("Распределить равномерно")
        btn_uniform.clicked.connect(self._fill_uniform_from_total)
        ctrl_row.addWidget(btn_uniform)

        btn_daytime = QPushButton("Только днём (10–22)")
        btn_daytime.clicked.connect(lambda: self._fill_window(10, 22))
        ctrl_row.addWidget(btn_daytime)

        btn_evening = QPushButton("Вечер пик (18–23)")
        btn_evening.clicked.connect(lambda: self._fill_window(18, 23))
        ctrl_row.addWidget(btn_evening)

        btn_reset = QPushButton("Сброс")
        btn_reset.clicked.connect(lambda: self.set_values([0] * 24))
        ctrl_row.addWidget(btn_reset)

        ctrl_row.addStretch()
        self.sum_label = QLabel("Сумма: 0")
        self.sum_label.setStyleSheet("color:#4caf50; font-weight:600;")
        ctrl_row.addWidget(self.sum_label)
        layout.addLayout(ctrl_row)

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
        self._distribute_total_over(total, 0, 23)

    def _fill_uniform_from_total(self) -> None:
        total = int(self.total_spin.value())
        if total <= 0:
            return
        self._distribute_total_over(total, 0, 23)

    def _fill_window(self, start_hour: int, end_hour: int) -> None:
        total = int(self.total_spin.value()) or sum(self._values) or (end_hour - start_hour + 1)
        self._distribute_total_over(total, start_hour, end_hour)

    def _distribute_total_over(self, total: int, start_h: int, end_h: int) -> None:
        slots = end_h - start_h + 1
        if slots <= 0:
            return
        base, extra = divmod(total, slots)
        new = [0] * 24
        for i in range(slots):
            new[start_h + i] = base + (1 if i < extra else 0)
        self.set_values(new)
        self.total_spin.setValue(total)

    def _on_click(self, ev) -> None:
        pos = self.plot.plotItem.vb.mapSceneToView(ev.scenePos())
        hour = int(round(pos.x()))
        count = int(round(max(0, pos.y())))
        if 0 <= hour < 24:
            self._values[hour] = count
            self._refresh()
