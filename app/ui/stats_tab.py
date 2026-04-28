"""Вкладка «Статистика»: дашборд, графіки, звіти.

Весь контент у QScrollArea — навіть при малому вікні все доступне через скрол.
"""

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
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)
from loguru import logger
from sqlalchemy import func, select

from app.db.models import Account, Niche, Sale
from app.db.session import get_session
from app.services.export import export_csv, export_xlsx


PERIODS = {
    "День": timedelta(days=1),
    "Тиждень": timedelta(days=7),
    "Місяць": timedelta(days=30),
    "Рік": timedelta(days=365),
}


class StatsTab(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        pg.setConfigOption("background", "#151515")
        pg.setConfigOption("foreground", "#e6e6e6")
        self._build_ui()
        self.reload()

    def _build_ui(self) -> None:
        # Зовнішній layout — top-bar (фіксовано) + scroll-area з контентом
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        # --- верхній бар з періодом і кнопками (поза прокруткою) ---
        top = QHBoxLayout()
        top.setContentsMargins(8, 8, 8, 8)
        top.addWidget(QLabel("<h2>Статистика</h2>"))
        top.addStretch()
        self.period_combo = QComboBox()
        self.period_combo.addItems(list(PERIODS.keys()))
        self.period_combo.setCurrentText("Місяць")
        self.period_combo.currentTextChanged.connect(lambda _: self.reload())
        top.addWidget(QLabel("Період:"))
        top.addWidget(self.period_combo)
        btn_refresh = QPushButton("Оновити")
        btn_refresh.clicked.connect(self.reload)
        top.addWidget(btn_refresh)

        top.addWidget(QLabel("Експорт:"))
        btn_csv = QPushButton("CSV")
        btn_csv.clicked.connect(lambda: self._export("csv"))
        top.addWidget(btn_csv)
        btn_xlsx = QPushButton("XLSX")
        btn_xlsx.clicked.connect(lambda: self._export("xlsx"))
        top.addWidget(btn_xlsx)
        outer.addLayout(top)

        # --- прокручувана область з усім вмістом ---
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        outer.addWidget(scroll, 1)

        content = QWidget()
        scroll.setWidget(content)
        body = QVBoxLayout(content)
        body.setContentsMargins(8, 4, 8, 8)
        body.setSpacing(10)

        # --- KPI ---
        self.kpi_box = QGroupBox("Ключові показники")
        self.kpi_layout = QGridLayout(self.kpi_box)
        self.kpi_layout.setSpacing(8)
        body.addWidget(self.kpi_box)

        # --- 3 графіки в рядок (з мін. висотою) ---
        charts_box = QGroupBox("Динаміка по днях")
        charts_layout = QHBoxLayout(charts_box)
        self.sales_plot = self._make_plot("Продажі (шт) по днях")
        self.revenue_plot = self._make_plot("Оборот по днях")
        self.profit_plot = self._make_plot("Чистий прибуток по днях")
        charts_layout.addWidget(self.sales_plot)
        charts_layout.addWidget(self.revenue_plot)
        charts_layout.addWidget(self.profit_plot)
        body.addWidget(charts_box)

        # --- Порівняння прибутку по нішах (горизонтальний бар-чарт) ---
        niche_box = QGroupBox("Порівняння прибутку по нішах")
        niche_layout = QVBoxLayout(niche_box)
        self.niche_compare_plot = pg.PlotWidget()
        self.niche_compare_plot.setMinimumHeight(280)
        self.niche_compare_plot.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.MinimumExpanding
        )
        self.niche_compare_plot.getPlotItem().invertY(True)
        niche_layout.addWidget(self.niche_compare_plot)
        body.addWidget(niche_box)

        body.addStretch()

    @staticmethod
    def _make_plot(title: str) -> pg.PlotWidget:
        p = pg.PlotWidget(title=title)
        p.setMinimumHeight(220)
        p.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.MinimumExpanding)
        return p

    def reload(self) -> None:
        period = PERIODS[self.period_combo.currentText()]
        since = datetime.now(timezone.utc) - period
        today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

        with get_session() as s:
            sales = list(s.execute(select(Sale).where(Sale.sold_at >= since).order_by(Sale.sold_at)).scalars())
            active_count = s.execute(
                select(func.count(Account.id)).where(Account.status == "active")
            ).scalar_one() or 0
            niches_count = s.execute(select(func.count(Niche.id))).scalar_one() or 0
            stuck_now = s.execute(
                select(func.count(Account.id)).where(Account.is_stuck.is_(True), Account.status == "active")
            ).scalar_one() or 0

            from app.db.models import ActionLog
            bumps_today = s.execute(
                select(func.count(ActionLog.id)).where(
                    ActionLog.action == "bump",
                    ActionLog.level == "INFO",
                    ActionLog.created_at >= today_start,
                )
            ).scalar_one() or 0
            sticks_today = s.execute(
                select(func.count(ActionLog.id)).where(
                    ActionLog.action == "stick",
                    ActionLog.level == "INFO",
                    ActionLog.created_at >= today_start,
                )
            ).scalar_one() or 0

            sold_today = s.execute(
                select(func.count(Sale.id)).where(Sale.sold_at >= today_start)
            ).scalar_one() or 0
            revenue_today = s.execute(
                select(func.coalesce(func.sum(Sale.price), 0)).where(Sale.sold_at >= today_start)
            ).scalar_one() or 0
            profit_today = s.execute(
                select(func.coalesce(func.sum(Sale.profit), 0)).where(Sale.sold_at >= today_start)
            ).scalar_one() or 0

        total_qty = len(sales)
        total_revenue = sum(sale.price for sale in sales)
        total_profit = sum(sale.profit for sale in sales)
        avg_check = (total_revenue / total_qty) if total_qty else 0.0

        # Детальне логування — щоб зрозуміти що рахується
        logger.info(
            "📊 StatsTab.reload: період={}, з={} → {} продажів, оборот=${:.2f}, прибуток=${:.2f}",
            self.period_combo.currentText(),
            since.isoformat(timespec="seconds"),
            total_qty,
            total_revenue,
            total_profit,
        )
        logger.info(
            "📊 Сьогодні: продано={}, оборот=${:.2f}, прибуток=${:.2f}, bump={}, stick={}",
            sold_today, revenue_today, profit_today, bumps_today, sticks_today,
        )
        # Розподіл продажів за нішами (для виявлення «всі продажі в одну нішу»)
        with get_session() as s2:
            niches_map = {n.id: n.name for n in s2.execute(select(Niche)).scalars()}
        by_niche: dict = {}
        for sale in sales:
            key = niches_map.get(sale.niche_id, "БЕЗ НІШІ") if sale.niche_id else "БЕЗ НІШІ"
            d = by_niche.setdefault(key, {"qty": 0, "revenue": 0.0, "profit": 0.0})
            d["qty"] += 1
            d["revenue"] += sale.price or 0
            d["profit"] += sale.profit or 0
        for name, d in by_niche.items():
            logger.info(
                "   📁 '{}': {} продажів, оборот ${:.2f}, прибуток ${:.2f}",
                name, d["qty"], d["revenue"], d["profit"],
            )

        self._render_kpi({
            # Сьогодні
            "Продано сьогодні": f"{sold_today} шт",
            "Оборот сьогодні": f"{revenue_today:,.2f} $",
            "Прибуток сьогодні": f"{profit_today:,.2f} $",
            "Bump сьогодні": f"{bumps_today}",
            "Закріплень сьогодні": f"{sticks_today}",
            "Закріплено зараз": f"{stuck_now}",
            # За період
            "Продано за період": f"{total_qty} шт",
            "Оборот": f"{total_revenue:,.2f} $",
            "Прибуток": f"{total_profit:,.2f} $",
            "Середній чек": f"{avg_check:,.2f} $",
            "Активних акаунтів": str(active_count),
            "Всього ніш": str(niches_count),
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

        self.niche_compare_plot.clear()
        if not profit_by_niche:
            return

        sorted_items = sorted(profit_by_niche.items(), key=lambda kv: kv[1], reverse=True)
        names = [niches.get(nid, f"Niche #{nid}") for nid, _ in sorted_items]
        values = [v for _, v in sorted_items]

        y_pos = list(range(len(values)))
        bar = pg.BarGraphItem(
            x0=[0] * len(values), y=y_pos, width=values, height=0.7, brush="#4caf50"
        )
        self.niche_compare_plot.addItem(bar)
        self.niche_compare_plot.getAxis("left").setTicks([[(i, names[i]) for i in y_pos]])
        self.niche_compare_plot.setLabel("bottom", "Прибуток ($)")
        # Висота графіка адаптується під кількість ніш (мінімум 280, +28 на нішу)
        height = max(280, 60 + len(values) * 28)
        self.niche_compare_plot.setMinimumHeight(height)

    def _render_kpi(self, kpis: dict[str, str]) -> None:
        # очищуємо сітку
        while self.kpi_layout.count():
            item = self.kpi_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        # 4 колонки KPI (12 карток → 3 ряди)
        cols = 4
        for i, (k, v) in enumerate(kpis.items()):
            row, col = divmod(i, cols)
            box = QGroupBox()
            box.setMinimumHeight(80)
            lay = QVBoxLayout(box)
            lay.setContentsMargins(6, 6, 6, 6)
            title = QLabel(k)
            title.setStyleSheet("color:#9e9e9e; font-size:10pt;")
            title.setWordWrap(True)
            value = QLabel(v)
            value.setStyleSheet("font-size:14pt; font-weight:600; color:#4caf50;")
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
        # показуємо не всі підписи якщо їх багато (інакше каша)
        step = max(1, len(x_labels) // 10)
        ticks = [(i, x_labels[i]) for i in range(0, len(x_labels), step)]
        axis.setTicks([ticks])

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
        path_str, _ = QFileDialog.getSaveFileName(self, "Зберегти звіт", f"sales.{suffix}", f"*.{suffix}")
        if not path_str:
            return
        path = Path(path_str)
        try:
            if fmt == "csv":
                export_csv(rows, headers, path)
            else:
                export_xlsx(rows, headers, path)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Помилка експорту", str(exc))
            return
        QMessageBox.information(self, "Експорт", f"Збережено: {path}")


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
