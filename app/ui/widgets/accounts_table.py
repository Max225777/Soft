"""Таблица аккаунтов с inline-редактированием цены/себестоимости."""

from __future__ import annotations

from typing import Callable, Iterable

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import QCheckBox, QHeaderView, QTableWidget, QTableWidgetItem, QWidget

from app.db.models import Account


COLUMNS = [
    ("sel", "✓"),
    ("item_id", "ID"),
    ("title", "Название"),
    ("price", "Цена"),
    ("cost", "Себестоимость"),
    ("amount", "Остаток"),
    ("profit", "Прибыль"),
    ("status", "Статус"),
    ("bumps", "Поднятий"),
    ("sticks", "Закреплений"),
    ("priority", "Приоритет"),
]


class AccountsTable(QTableWidget):
    price_changed = Signal(int, float)  # item_id, new_price
    cost_changed = Signal(int, float)   # item_id, new_cost

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setColumnCount(len(COLUMNS))
        self.setHorizontalHeaderLabels([c[1] for c in COLUMNS])
        self.setAlternatingRowColors(True)
        self.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.setSortingEnabled(True)
        self.verticalHeader().setVisible(False)
        header = self.horizontalHeader()
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.itemChanged.connect(self._on_item_changed)
        self._updating = False
        self._accounts_by_row: dict[int, Account] = {}

    def set_accounts(self, accounts: Iterable[Account]) -> None:
        self._updating = True
        self.setSortingEnabled(False)
        self.clearContents()
        accounts = list(accounts)
        self.setRowCount(len(accounts))
        self._accounts_by_row.clear()

        for row, acc in enumerate(accounts):
            self._accounts_by_row[row] = acc

            chk = QTableWidgetItem()
            chk.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            chk.setCheckState(Qt.CheckState.Unchecked)
            self.setItem(row, 0, chk)

            self._set_ro(row, 1, str(acc.item_id))
            self._set_ro(row, 2, acc.title or "")
            self._set_editable(row, 3, f"{acc.price:.2f}")
            self._set_editable(row, 4, f"{acc.cost:.2f}")
            self._set_ro(row, 5, str(acc.amount))
            profit = acc.profit
            self._set_ro(row, 6, f"{profit:.2f}", color=_profit_color(profit))
            self._set_ro(row, 7, acc.status or "")
            self._set_ro(row, 8, str(acc.bumps_available))
            self._set_ro(row, 9, str(acc.sticks_available))
            self._set_ro(row, 10, "★" if acc.is_priority else "")

        self.setSortingEnabled(True)
        self._updating = False

    def selected_item_ids(self) -> list[int]:
        ids: list[int] = []
        for row in range(self.rowCount()):
            chk = self.item(row, 0)
            if chk and chk.checkState() == Qt.CheckState.Checked:
                acc = self._accounts_by_row.get(row)
                if acc:
                    ids.append(acc.item_id)
        return ids

    def select_all(self, checked: bool = True) -> None:
        self._updating = True
        state = Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
        for row in range(self.rowCount()):
            chk = self.item(row, 0)
            if chk:
                chk.setCheckState(state)
        self._updating = False

    # ---------- helpers ----------
    def _set_ro(self, row: int, col: int, text: str, color: QColor | None = None) -> None:
        item = QTableWidgetItem(text)
        item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
        if color:
            item.setForeground(QBrush(color))
        self.setItem(row, col, item)

    def _set_editable(self, row: int, col: int, text: str) -> None:
        item = QTableWidgetItem(text)
        item.setFlags(
            Qt.ItemFlag.ItemIsEnabled
            | Qt.ItemFlag.ItemIsSelectable
            | Qt.ItemFlag.ItemIsEditable
        )
        self.setItem(row, col, item)

    def _on_item_changed(self, item: QTableWidgetItem) -> None:
        if self._updating:
            return
        row = item.row()
        col = item.column()
        acc = self._accounts_by_row.get(row)
        if acc is None:
            return
        try:
            value = float(item.text().replace(",", "."))
        except ValueError:
            return
        if col == 3:
            self.price_changed.emit(acc.item_id, value)
        elif col == 4:
            self.cost_changed.emit(acc.item_id, value)


def _profit_color(profit: float) -> QColor:
    if profit > 0:
        return QColor("#4caf50")
    if profit < 0:
        return QColor("#f44336")
    return QColor("#bdbdbd")
