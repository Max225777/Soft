"""Создание схемы БД при первом запуске."""

from __future__ import annotations

import sys
from pathlib import Path

from loguru import logger

from app.config import Settings
from app.db.models import Base
from app.db.session import init_engine


def init_db(db_path: Path) -> None:
    engine = init_engine(db_path)
    Base.metadata.create_all(engine)
    logger.info("Схема БД инициализирована: {}", db_path)


def main() -> int:
    settings = Settings.load()
    init_db(settings.db_path)
    print(f"БД создана: {settings.db_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
