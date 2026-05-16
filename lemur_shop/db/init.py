from __future__ import annotations

from sqlalchemy import text

from lemur_shop.db.models import Base
from lemur_shop.db.session import engine

_MIGRATIONS = [
    "ALTER TABLE orders ADD COLUMN IF NOT EXISTS cost_usd NUMERIC(10,2)",
    "ALTER TABLE orders ADD COLUMN IF NOT EXISTS category VARCHAR(32)",
]


async def create_tables() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        for sql in _MIGRATIONS:
            await conn.execute(text(sql))
