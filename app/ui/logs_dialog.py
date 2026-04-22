"""Диалог просмотра журнала событий."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)
from sqlalchemy import select

from app.db.models import ActionLog
from app.db.session import get_session


LEVELS = ["ALL", "INFO", "WARNING", "ERROR", "DEBUG"]


class LogsDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Журнал событий")
        self.resize(900, 520)
        self._build_ui()
        self.reload()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        filters = QHBoxLayout()
        filters.addWidget(QLabel("Уровень:"))
        self.level_combo = QComboBox()
        self.level_combo.addItems(LEVELS)
        self.level_combo.currentTextChanged.connect(lambda _: self.reload())
        filters.addWidget(self.level_combo)

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("поиск по тексту / action / item_id")
        self.search_edit.returnPressed.connect(self.reload)
        filters.addWidget(self.search_edit, 1)

        btn = QPushButton("Обновить")
        btn.clicked.connect(self.reload)
        filters.addWidget(btn)
        layout.addLayout(filters)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Время", "Уровень", "Действие", "item_id", "Сообщение"])
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table)

    def reload(self) -> None:
        level = self.level_combo.currentText()
        search = self.search_edit.text().strip().lower()
        with get_session() as s:
            stmt = select(ActionLog).order_by(ActionLog.created_at.desc()).limit(500)
            if level != "ALL":
                stmt = stmt.where(ActionLog.level == level)
            rows = list(s.execute(stmt).scalars())

        filtered = []
        for r in rows:
            if search:
                haystack = f"{r.action} {r.item_id or ''} {r.message}".lower()
                if search not in haystack:
                    continue
            filtered.append(r)

        self.table.setRowCount(len(filtered))
        for i, r in enumerate(filtered):
            self.table.setItem(i, 0, QTableWidgetItem(r.created_at.strftime("%Y-%m-%d %H:%M:%S")))
            self.table.setItem(i, 1, QTableWidgetItem(r.level))
            self.table.setItem(i, 2, QTableWidgetItem(r.action))
            self.table.setItem(i, 3, QTableWidgetItem(str(r.item_id or "")))
            self.table.setItem(i, 4, QTableWidgetItem(r.message))
