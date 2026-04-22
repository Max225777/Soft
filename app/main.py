"""Точка входа приложения."""

from __future__ import annotations

import sys

from loguru import logger

from app.config import Settings
from app.db.init import init_db
from app.services.logging_setup import setup_logging


def main() -> int:
    settings = Settings.load()
    setup_logging(settings.log_level, settings.log_file)
    logger.info("Старт Lolzteam Market Manager (debug={})", settings.debug)

    init_db(settings.db_path)

    # Импорт Qt только после инициализации БД, чтобы не тянуть PySide6 в CLI-сценариях
    from PySide6.QtWidgets import QApplication

    from app.ui.main_window import MainWindow
    from app.ui.theme import DARK_QSS

    app = QApplication(sys.argv)
    if settings.theme == "dark":
        app.setStyleSheet(DARK_QSS)

    window = MainWindow(settings)
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
