"""Инициализация схемы БД + авто-миграция.

Поддерживает 2 сценария:
1. Добавление новых колонок к существующей таблице (ALTER TABLE ADD COLUMN)
2. Удаление устаревших NOT NULL колонок через пересоздание таблицы
   (нужно потому что SQLite не умеет ALTER COLUMN DROP NOT NULL)
"""

from __future__ import annotations

import sys
from pathlib import Path

from loguru import logger
from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

from app.config import Settings
from app.db.models import Base
from app.db.session import init_engine


def init_db(db_path: Path) -> None:
    engine = init_engine(db_path)
    _drop_obsolete_tables(engine)  # пересоздаём таблицы где есть устаревшие NOT NULL
    Base.metadata.create_all(engine)
    _add_missing_columns(engine)
    logger.info("Схема БД готова: {}", db_path)


def _drop_obsolete_tables(engine: Engine) -> None:
    """Если в существующей таблице есть NOT NULL колонки, которых нет в модели,
    INSERT'ы будут падать. Пересоздаём такую таблицу с актуальной схемой,
    сохраняя данные общих колонок.
    """
    inspector = inspect(engine)
    for table_name, table in Base.metadata.tables.items():
        if not inspector.has_table(table_name):
            continue
        existing_cols = inspector.get_columns(table_name)
        model_col_names = {col.name for col in table.columns}

        obsolete_not_null = []
        for col_info in existing_cols:
            name = col_info["name"]
            if name in model_col_names:
                continue
            if col_info.get("nullable", True):
                continue  # NULL разрешён — INSERT без этой колонки не упадёт
            if col_info.get("default") is not None:
                continue  # есть DEFAULT — тоже OK
            obsolete_not_null.append(name)

        if not obsolete_not_null:
            continue

        logger.warning(
            "Пересоздаю таблицу {} чтобы сбросить устаревшие NOT NULL колонки: {}",
            table_name, obsolete_not_null,
        )
        common_cols = sorted(model_col_names & {c["name"] for c in existing_cols})
        old_col_names = {c["name"] for c in existing_cols}
        model_cols_by_name = {c.name: c for c in table.columns}

        # SELECT для общих колонок: COALESCE(col, default) если в модели NOT NULL и есть дефолт
        select_parts = []
        for name in common_cols:
            col = model_cols_by_name[name]
            if not col.nullable:
                default_lit = _python_default_literal(col)
                if default_lit is not None:
                    if "DATETIME" in str(col.type).upper() or "TIMESTAMP" in str(col.type).upper():
                        default_lit = "CURRENT_TIMESTAMP"
                    select_parts.append(f'COALESCE("{name}", {default_lit})')
                    continue
            select_parts.append(f'"{name}"')

        # Колонки которые есть в модели с NOT NULL и Python-дефолтом, но отсутствуют в старой таблице
        extra_target_cols = []
        for col in table.columns:
            if col.name in old_col_names:
                continue
            if col.nullable:
                continue
            default = _python_default_literal(col)
            if default is None:
                continue
            if "DATETIME" in str(col.type).upper() or "TIMESTAMP" in str(col.type).upper():
                default = "CURRENT_TIMESTAMP"
            extra_target_cols.append(col.name)
            select_parts.append(default)

        target_cols_sql = ", ".join(f'"{c}"' for c in common_cols + extra_target_cols)
        select_sql = ", ".join(select_parts)

        old_name = f"{table_name}__legacy"
        with engine.begin() as conn:
            conn.execute(text("PRAGMA foreign_keys=OFF"))
            conn.execute(text(f'ALTER TABLE "{table_name}" RENAME TO "{old_name}"'))
        # create_all создаст таблицу с актуальной схемой
        table.create(engine)
        with engine.begin() as conn:
            conn.execute(text(
                f'INSERT INTO "{table_name}" ({target_cols_sql}) '
                f'SELECT {select_sql} FROM "{old_name}"'
            ))
            conn.execute(text(f'DROP TABLE "{old_name}"'))
            conn.execute(text("PRAGMA foreign_keys=ON"))
        logger.info("Таблица {} пересоздана. Скопировано колонок: {}", table_name, common_cols)


def _python_default_literal(col) -> str | None:
    """Возвращает SQL-литерал для Python-дефолта колонки (для INSERT … SELECT).

    None — если разумного значения не нашли.
    """
    if col.default is not None and getattr(col.default, "is_scalar", False):
        val = col.default.arg
        if isinstance(val, bool):
            return "1" if val else "0"
        if isinstance(val, (int, float)):
            return str(val)
        if isinstance(val, str):
            escaped = val.replace("'", "''")
            return f"'{escaped}'"
    # default_factory (например list/dict) — для JSON колонок
    factory = getattr(col.default, "arg", None) if col.default is not None else None
    if callable(factory):
        try:
            sample = factory()
            if isinstance(sample, list):
                return "'[]'"
            if isinstance(sample, dict):
                return "'{}'"
        except Exception:  # noqa: BLE001
            pass
    # типовые fallback-и по типу
    type_str = str(col.type).upper()
    if "DATETIME" in type_str or "TIMESTAMP" in type_str or "DATE" in type_str:
        return "CURRENT_TIMESTAMP"
    if "INT" in type_str or "FLOAT" in type_str or "NUMERIC" in type_str or "REAL" in type_str:
        return "0"
    if "VARCHAR" in type_str or "TEXT" in type_str or "STRING" in type_str:
        return "''"
    if "BOOL" in type_str:
        return "0"
    if "JSON" in type_str:
        return "'{}'"
    return None


def _add_missing_columns(engine: Engine) -> None:
    inspector = inspect(engine)
    with engine.begin() as conn:
        for table_name, table in Base.metadata.tables.items():
            if not inspector.has_table(table_name):
                continue
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
