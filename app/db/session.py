"""Глобальная сессия SQLAlchemy."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker


_engine: Engine | None = None
_SessionFactory: sessionmaker[Session] | None = None


def init_engine(db_path: Path, echo: bool = False) -> Engine:
    global _engine, _SessionFactory
    db_path.parent.mkdir(parents=True, exist_ok=True)
    url = f"sqlite:///{db_path}"
    _engine = create_engine(url, echo=echo, future=True)
    _SessionFactory = sessionmaker(bind=_engine, expire_on_commit=False, future=True)
    return _engine


def get_engine() -> Engine:
    if _engine is None:
        raise RuntimeError("Engine не инициализирован. Вызовите init_engine() сначала.")
    return _engine


def get_session() -> Session:
    if _SessionFactory is None:
        raise RuntimeError("Session factory не инициализирована.")
    return _SessionFactory()
