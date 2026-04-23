"""Вкладка «Статистика»: дашборд, графики, отчёты."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pyqtgraph as pg
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from sqlalchemy import func, select

from app.db.models import Account, Niche, Sale
from app.db.session import get_session
from app.services.export import export_csv, export_xlsx


PERIODS = {
    "День": timedelta(days=1),
    "Неделя": timedelta(days=7),
    "Месяц": timedelta(days=30),
    "Год": timedelta(days=365),
}


class StatsTab(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        pg.setConfigOption("background", "#151515")
        pg.setConfigOption("foreground", "#e6e6e6")
        self._build_ui()
        self.reload()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)

        top = QHBoxLayout()
        top.addWidget(QLabel("<h2>Статистика</h2>"))
        top.addStretch()
        self.period_combo = QComboBox()
        self.period_combo.addItems(list(PERIODS.keys()))
        self.period_combo.setCurrentText("Месяц")
        self.period_combo.currentTextChanged.connect(lambda _: self.reload())
        top.addWidget(QLabel("Период:"))
        top.addWidget(self.period_combo)
        btn_refresh = QPushButton("Обновить")
        btn_refresh.clicked.connect(self.reload)
        top.addWidget(btn_refresh)
        root.addLayout(top)

        self.kpi_box = QGroupBox("Ключевые показатели")
        self.kpi_layout = QGridLayout(self.kpi_box)
        root.addWidget(self.kpi_box)

        charts = QHBoxLayout()
        self.sales_plot = pg.PlotWidget(title="Продажи (шт) по дням")
        self.revenue_plot = pg.PlotWidget(title="Оборот по дням")
        self.profit_plot = pg.PlotWidget(title="Чистая прибыль по дням")
        charts.addWidget(self.sales_plot)
        charts.addWidget(self.revenue_plot)
        charts.addWidget(self.profit_plot)
        root.addLayout(charts, 1)

        # --- Горизонтальное сравнение прибыли по нишам ---
        niche_box = QGroupBox("Сравнение прибыли по нишам")
        niche_layout = QVBoxLayout(niche_box)
        self.niche_compare_plot = pg.PlotWidget()
        self.niche_compare_plot.setMinimumHeight(240)
        self.niche_compare_plot.getPlotItem().invertY(True)  # сверху вниз
        niche_layout.addWidget(self.niche_compare_plot)
        root.addWidget(niche_box, 1)

        export_bar = QHBoxLayout()
        export_bar.addWidget(QLabel("Экспорт:"))
        btn_csv = QPushButton("CSV")
        btn_csv.clicked.connect(lambda: self._export("csv"))
        export_bar.addWidget(btn_csv)
        btn_xlsx = QPushButton("XLSX")
        btn_xlsx.clicked.connect(lambda: self._export("xlsx"))
        export_bar.addWidget(btn_xlsx)
        export_bar.addStretch()
        root.addLayout(export_bar)

    def reload(self) -> None:
        period = PERIODS[self.period_combo.currentText()]
        since = datetime.now(timezone.utc) - period

        with get_session() as s:
            sales = list(s.execute(select(Sale).where(Sale.sold_at >= since).order_by(Sale.sold_at)).scalars())
            active_count = s.execute(
                select(func.count(Account.id)).where(Account.status == "active")
            ).scalar_one() or 0
            niches_count = s.execute(select(func.count(Niche.id))).scalar_one() or 0

        total_qty = len(sales)
        total_revenue = sum(sale.price for sale in sales)
        total_profit = sum(sale.profit for sale in sales)
        avg_check = (total_revenue / total_qty) if total_qty else 0.0

        self._render_kpi({
            "Продано за период": f"{total_qty} шт",
            "Оборот": f"{total_revenue:,.2f} $",
            "Чистая прибыль": f"{total_profit:,.2f} $",
            "Средний чек": f"{avg_check:,.2f} $",
            "Активных аккаунтов": str(active_count),
            "Всего ниш": str(niches_count),
        })

        daily = _group_daily(sales, period)
        self._draw(self.sales_plot, daily["dates"], daily["qty"], "#2196f3")
        self._draw(self.revenue_plot, daily["dates"], daily["revenue"], "#4caf50")
        self._draw(self.profit_plot, daily["dates"], daily["profit"], "#ffeb3b")

        self._draw_niche_compare(sales)

    def _draw_niche_compare(self, sales) -> None:
        with get_session() as s:
            niches = {n.id: n.name for n in s.execute(select(Niche)).scalars()}

        profit_by_niche: dict[int, float] = {}
        for sale in sales:
            if sale.niche_id is None:
                continue
            profit_by_niche[sale.niche_id] = profit_by_niche.get(sale.niche_id, 0.0) + (sale.profit or 0)

        if not profit_by_niche:
            self.niche_compare_plot.clear()
            return

        sorted_items = sorted(profit_by_niche.items(), key=lambda kv: kv[1], reverse=True)
        names = [niches.get(nid, f"Niche #{nid}") for nid, _ in sorted_items]
        values = [v for _, v in sorted_items]

        self.niche_compare_plot.clear()
        y_pos = list(range(len(values)))
        bar = pg.BarGraphItem(
            x0=[0] * len(values), y=y_pos, width=values, height=0.7, brush="#4caf50"
        )
        self.niche_compare_plot.addItem(bar)
        self.niche_compare_plot.getAxis("left").setTicks([[(i, names[i]) for i in y_pos]])
        self.niche_compare_plot.setLabel("bottom", "Прибыль ($)")

    def _render_kpi(self, kpis: dict[str, str]) -> None:
        # очищаем сетку
        while self.kpi_layout.count():
            item = self.kpi_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        for i, (k, v) in enumerate(kpis.items()):
            row, col = divmod(i, 3)
            box = QGroupBox()
            lay = QVBoxLayout(box)
            title = QLabel(k)
            title.setStyleSheet("color:#9e9e9e;")
            value = QLabel(v)
            value.setStyleSheet("font-size:18pt; font-weight:600; color:#4caf50;")
            value.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lay.addWidget(title)
            lay.addWidget(value)
            self.kpi_layout.addWidget(box, row, col)

    def _draw(self, plot: pg.PlotWidget, x_labels: list[str], y: list[float], color: str) -> None:
        plot.clear()
        if not y:
            return
        x = list(range(len(y)))
        plot.plot(x, y, pen=pg.mkPen(color=color, width=2), symbol="o", symbolBrush=color, symbolSize=5)
        axis = plot.getAxis("bottom")
        axis.setTicks([[(i, x_labels[i]) for i in range(len(x_labels))]])

    def _export(self, fmt: str) -> None:
        period = PERIODS[self.period_combo.currentText()]
        since = datetime.now(timezone.utc) - period
        with get_session() as s:
            sales = list(s.execute(select(Sale).where(Sale.sold_at >= since).order_by(Sale.sold_at)).scalars())
            niche_names = {n.id: n.name for n in s.execute(select(Niche)).scalars()}

        headers = ["sold_at", "item_id", "title", "price", "cost", "profit", "niche"]
        rows = [
            (sale.sold_at, sale.item_id, sale.title, sale.price, sale.cost, sale.profit, niche_names.get(sale.niche_id, ""))
            for sale in sales
        ]

        suffix = "csv" if fmt == "csv" else "xlsx"
        path_str, _ = QFileDialog.getSaveFileName(self, "Сохранить отчёт", f"sales.{suffix}", f"*.{suffix}")
        if not path_str:
            return
        path = Path(path_str)
        try:
            if fmt == "csv":
                export_csv(rows, headers, path)
            else:
                export_xlsx(rows, headers, path)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Ошибка экспорта", str(exc))
            return
        QMessageBox.information(self, "Экспорт", f"Сохранено: {path}")


def _group_daily(sales: list[Sale], period: timedelta) -> dict:
    if not sales:
        return {"dates": [], "qty": [], "revenue": [], "profit": []}
    start = (datetime.now(timezone.utc) - period).date()
    end = datetime.now(timezone.utc).date()
    days = (end - start).days + 1
    dates = [(start + timedelta(days=i)) for i in range(days)]
    qty = [0] * days
    revenue = [0.0] * days
    profit = [0.0] * days
    for sale in sales:
        idx = (sale.sold_at.date() - start).days
        if 0 <= idx < days:
            qty[idx] += 1
            revenue[idx] += sale.price
            profit[idx] += sale.profit
    return {
        "dates": [d.strftime("%d.%m") for d in dates],
        "qty": qty,
        "revenue": revenue,
        "profit": profit,
    }
