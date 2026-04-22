"""Карточка ниши в боковом списке."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout, QWidget

from app.core.niche_manager import niche_summary
from app.db.models import Niche


class NicheCard(QFrame):
    def __init__(self, niche: Niche, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.niche = niche
        self.setObjectName("NicheCard")
        self.setStyleSheet(
            "QFrame#NicheCard { background: #1f1f1f; border: 1px solid #2a2a2a; border-radius: 6px; padding: 6px; }"
            "QFrame#NicheCard:hover { border-color: #4caf50; }"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)

        title = QLabel(niche.name)
        title.setStyleSheet("font-size: 14pt; font-weight: 600; color: #e6e6e6;")
        layout.addWidget(title)

        summary = niche_summary(niche)
        info = QLabel(
            f"Аккаунтов: <b>{summary['count']}</b>  |  "
            f"Ø цена: <b>{summary['avg_price']:.2f}</b>  |  "
            f"Ø с/с: <b>{summary['avg_cost']:.2f}</b><br>"
            f"Ожидаемая прибыль: <span style='color:#4caf50'>{summary['expected_profit']:.2f}</span>"
        )
        info.setTextFormat(Qt.TextFormat.RichText)
        info.setStyleSheet("color: #9e9e9e;")
        layout.addWidget(info)

        flags = []
        if niche.auto_bump:
            flags.append("🔺 auto-bump")
        if niche.auto_stick:
            flags.append("📌 auto-stick")
        if flags:
            badge = QLabel(" | ".join(flags))
            badge.setStyleSheet("color:#2196f3;")
            layout.addWidget(badge)
