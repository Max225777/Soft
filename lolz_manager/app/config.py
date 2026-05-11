"""Конфигурация приложения: загрузка из .env и аргументов CLI."""

from __future__ import annotations

import argparse
import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv


ROOT_DIR = Path(__file__).resolve().parent.parent


def _get_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _get_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    try:
        return float(raw) if raw is not None else default
    except ValueError:
        return default


def _get_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    try:
        return int(raw) if raw is not None else default
    except ValueError:
        return default


@dataclass
class Settings:
    # API
    api_token: str = ""
    api_base_url: str = "https://prod-api.lzt.market/"
    api_lang: str = "ru"
    api_min_delay: float = 3.0
    api_max_retries: int = 3

    # Cycle
    cycle_interval_seconds: int = 1200  # bump tick — 20 хв default
    fetch_interval_seconds: int = 600   # повний fetch items з API — 10 хв default
    cycle_autostart: bool = True
    notify_sales: bool = True
    sound_on_sale: bool = False

    # Database
    db_path: Path = field(default_factory=lambda: ROOT_DIR / "data" / "app.db")
    db_encrypted: bool = False

    # Logging
    log_level: str = "INFO"
    log_file: Path = field(default_factory=lambda: ROOT_DIR / "logs" / "app.log")

    # UI
    theme: str = "dark"
    rows_per_page: int = 50

    # Runtime flags (from CLI)
    debug: bool = False
    no_auto_cycle: bool = False

    @classmethod
    def load(cls, env_file: Path | None = None, argv: list[str] | None = None) -> "Settings":
        load_dotenv(env_file or ROOT_DIR / ".env")
        args = _parse_cli(argv)

        db_path_raw = os.getenv("DB_PATH", "data/app.db")
        db_path = Path(db_path_raw) if Path(db_path_raw).is_absolute() else ROOT_DIR / db_path_raw
        if args.db:
            db_path = Path(args.db).expanduser().resolve()

        log_file_raw = os.getenv("LOG_FILE", "logs/app.log")
        log_file = Path(log_file_raw) if Path(log_file_raw).is_absolute() else ROOT_DIR / log_file_raw

        return cls(
            api_token=os.getenv("LOLZ_API_TOKEN", ""),
            api_base_url=os.getenv("LOLZ_API_BASE_URL", "https://prod-api.lzt.market/"),
            api_lang=os.getenv("LOLZ_API_LANG", "ru"),
            # 0.6 сек безопасно: 60/0.6 = 100 запросов/мин (лимит Lolzteam: 120/мин для items).
            # Для search-эндпоинтов queue.RequestQueue отдельно держит окно 20/мин.
            api_min_delay=max(_get_float("LOLZ_API_MIN_DELAY", 0.6), 0.3),
            api_max_retries=_get_int("LOLZ_API_MAX_RETRIES", 3),
            cycle_interval_seconds=_get_int(
                "CYCLE_INTERVAL_SECONDS",
                _get_int("CYCLE_INTERVAL_MINUTES", 20) * 60,
            ),
            fetch_interval_seconds=_get_int("FETCH_INTERVAL_SECONDS", 600),
            cycle_autostart=_get_bool("CYCLE_AUTOSTART", True) and not args.no_auto_cycle,
            notify_sales=_get_bool("NOTIFY_SALES", True),
            sound_on_sale=_get_bool("SOUND_ON_SALE", False),
            db_path=db_path,
            db_encrypted=_get_bool("DB_ENCRYPTED", False),
            log_level="DEBUG" if args.debug else os.getenv("LOG_LEVEL", "INFO"),
            log_file=log_file,
            theme=os.getenv("UI_THEME", "dark"),
            rows_per_page=_get_int("UI_ROWS_PER_PAGE", 50),
            debug=args.debug,
            no_auto_cycle=args.no_auto_cycle,
        )


def _parse_cli(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="lolz-market-manager", description="Менеджер ниш и статистики Lolzteam Market")
    parser.add_argument("--debug", action="store_true", help="Включить подробное логирование")
    parser.add_argument("--no-auto-cycle", action="store_true", help="Не запускать 20-минутный цикл при старте")
    parser.add_argument("--config", type=str, default=None, help="Путь к альтернативному .env")
    parser.add_argument("--db", type=str, default=None, help="Путь к альтернативному файлу БД")
    return parser.parse_args(argv)
