from __future__ import annotations

from sqlalchemy import text

from lemur_shop.db.models import Base
from lemur_shop.db.session import engine

_MIGRATIONS = [
    "ALTER TABLE orders ADD COLUMN IF NOT EXISTS cost_usd NUMERIC(10,2)",
    "ALTER TABLE orders ADD COLUMN IF NOT EXISTS category VARCHAR(32)",
    "ALTER TABLE topups ADD COLUMN IF NOT EXISTS method VARCHAR(16) DEFAULT 'admin'",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS balance_stars BIGINT DEFAULT 0",
    # Конвертуємо старий баланс в Stars (тільки якщо balance_stars ще 0)
    "UPDATE users SET balance_stars = ROUND(CAST(balance_usd AS FLOAT) / 0.013) WHERE balance_stars = 0 AND CAST(balance_usd AS FLOAT) > 0.009",
]


async def create_tables() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        for sql in _MIGRATIONS:
            await conn.execute(text(sql))
