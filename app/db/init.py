"""Инициализация схемы БД + авто-миграция недостающих колонок.

Поскольку приложение пока без Alembic, используется простой механизм:
при старте сверяем колонки из моделей с фактическими в SQLite и добавляем
недостающие через ALTER TABLE. Удалять/менять типы пока не умеет — для этого
достаточно удалить data/app.db и приложение создаст схему с нуля.
"""

from __future__ import annotations

import sys
from pathlib import Path

from loguru import logger
from sqlalchemy import inspect, text

from app.config import Settings
from app.db.models import Base
from app.db.session import init_engine


def init_db(db_path: Path) -> None:
    engine = init_engine(db_path)
    Base.metadata.create_all(engine)
    _auto_migrate(engine)
    logger.info("Схема БД готова: {}", db_path)


def _auto_migrate(engine) -> None:
    """Добавляет недостающие колонки в существующие таблицы."""
    inspector = inspect(engine)
    with engine.begin() as conn:
        for table_name, table in Base.metadata.tables.items():
            if not inspector.has_table(table_name):
                continue  # create_all уже создал
            existing_cols = {col["name"] for col in inspector.get_columns(table_name)}
            for col in table.columns:
                if col.name in existing_cols:
                    continue
                col_type = col.type.compile(dialect=engine.dialect)
                default_sql = ""
                if col.default is not None and getattr(col.default, "is_scalar", False):
                    val = col.default.arg
                    if isinstance(val, bool):
                        default_sql = f" DEFAULT {1 if val else 0}"
                    elif isinstance(val, (int, float)):
                        default_sql = f" DEFAULT {val}"
                    elif isinstance(val, str):
                        default_sql = f" DEFAULT '{val}'"
                nullable = "" if col.nullable else " NOT NULL"
                # SQLite NOT NULL без DEFAULT нельзя — делаем колонку NULLABLE
                if not col.nullable and not default_sql:
                    nullable = ""

                stmt = f'ALTER TABLE "{table_name}" ADD COLUMN "{col.name}" {col_type}{default_sql}{nullable}'
                try:
                    conn.execute(text(stmt))
                    logger.info("Авто-миграция: + {}.{}", table_name, col.name)
                except Exception as exc:  # noqa: BLE001
                    logger.warning("Не удалось добавить {}.{}: {}", table_name, col.name, exc)


def main() -> int:
    settings = Settings.load()
    init_db(settings.db_path)
    print(f"БД готова: {settings.db_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
