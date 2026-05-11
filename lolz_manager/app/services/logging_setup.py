"""Инициализация логирования через loguru."""

from __future__ import annotations

import sys
from pathlib import Path

from loguru import logger


def setup_logging(level: str = "INFO", log_file: Path | None = None) -> None:
    logger.remove()
    fmt = (
        "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
        "<level>{level:<7}</level> | "
        "<cyan>{name}:{function}:{line}</cyan> - <level>{message}</level>"
    )
    # Без enqueue=True — на Windows + PySide6 та фоновими потоками
    # внутрішня черга loguru може спричиняти крах STATUS_STACK_BUFFER_OVERRUN.
    # Синхронне логування достатньо швидке для нашого використання.
    logger.add(sys.stderr, level=level, format=fmt)
    if log_file is not None:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        logger.add(
            log_file,
            level="DEBUG",
            rotation="10 MB",
            retention="30 days",
            compression="zip",
            encoding="utf-8",
        )
    logger.info("Логування ініціалізоване (level={})", level)
