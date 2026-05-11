"""Тёмная тема в стиле Lolzteam Market."""

DARK_QSS = """
* { font-family: "Segoe UI", "Roboto", "Inter", sans-serif; color: #e6e6e6; }
QWidget { background: #1a1a1a; color: #e6e6e6; }
QMainWindow { background: #141414; }

QTabWidget::pane { border: 1px solid #2a2a2a; background: #1a1a1a; }
QTabBar::tab {
    background: #1f1f1f;
    color: #bdbdbd;
    padding: 8px 18px;
    border: 1px solid #2a2a2a;
    border-bottom: none;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    margin-right: 2px;
}
QTabBar::tab:selected { background: #2a2a2a; color: #4caf50; }
QTabBar::tab:hover { background: #262626; }

QPushButton {
    background: #2a2a2a;
    color: #e6e6e6;
    padding: 6px 14px;
    border: 1px solid #333;
    border-radius: 4px;
}
QPushButton:hover { background: #333; border-color: #444; }
QPushButton:pressed { background: #222; }
QPushButton#primary { background: #4caf50; color: #0b0b0b; border: 1px solid #4caf50; }
QPushButton#primary:hover { background: #5cbf60; }
QPushButton#danger { background: #f44336; color: #fff; border: 1px solid #f44336; }
QPushButton#danger:hover { background: #e53935; }

QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QTextEdit, QPlainTextEdit {
    background: #111; color: #e6e6e6;
    border: 1px solid #2a2a2a; border-radius: 4px; padding: 4px 8px;
    selection-background-color: #2196f3;
}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus { border-color: #2196f3; }

QHeaderView::section {
    background: #1f1f1f; color: #9e9e9e;
    padding: 6px; border: 1px solid #2a2a2a;
}
QTableView, QTableWidget {
    background: #151515; alternate-background-color: #1a1a1a;
    gridline-color: #262626; selection-background-color: #2196f3;
    border: 1px solid #2a2a2a;
}

QStatusBar { background: #0e0e0e; color: #9e9e9e; }
QMenu { background: #1a1a1a; border: 1px solid #2a2a2a; }
QMenu::item:selected { background: #2a2a2a; color: #4caf50; }

QListWidget {
    background: #151515; border: 1px solid #2a2a2a;
}
QListWidget::item { padding: 8px; border-bottom: 1px solid #222; }
QListWidget::item:selected { background: #202020; color: #4caf50; }

QGroupBox {
    border: 1px solid #2a2a2a; border-radius: 6px;
    margin-top: 10px; padding-top: 12px;
}
QGroupBox::title { subcontrol-origin: margin; left: 10px; color: #4caf50; }

QCheckBox { spacing: 6px; }
QScrollBar:vertical { background: #111; width: 10px; }
QScrollBar::handle:vertical { background: #333; border-radius: 5px; }
"""
