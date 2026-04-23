"""Проверка, что init_db добавляет недостающие колонки к существующей БД."""

from pathlib import Path

from sqlalchemy import create_engine, text

from app.db.init import init_db
from app.db.session import init_engine


def test_auto_migration_adds_missing_columns(tmp_path: Path) -> None:
    db = tmp_path / "old.db"

    # создаём «старую» таблицу niches без новых колонок
    engine = create_engine(f"sqlite:///{db}")
    with engine.begin() as conn:
        conn.execute(text(
            "CREATE TABLE niches ("
            " id INTEGER PRIMARY KEY AUTOINCREMENT,"
            " name VARCHAR(128) NOT NULL UNIQUE,"
            " category VARCHAR(64) DEFAULT 'telegram',"
            " country VARCHAR(64) DEFAULT '',"
            " created_at DATETIME, updated_at DATETIME"
            ")"
        ))
        conn.execute(text("INSERT INTO niches (name) VALUES ('legacy niche')"))
    engine.dispose()

    # запускаем init_db на этой же БД — авто-миграция должна добавить недостающие колонки
    init_db(db)

    # перепроверяем что колонки добавились и данные остались
    engine2 = init_engine(db)
    with engine2.begin() as conn:
        row = conn.execute(text("SELECT name, markup, bumps_per_day, exact_title FROM niches")).fetchone()
    assert row is not None
    assert row[0] == "legacy niche"
    # markup/bumps_per_day/exact_title получили дефолты из ALTER
    assert row[1] in (0.0, 0, None)
    assert row[2] in (0, None)
    assert row[3] in ("", None)
