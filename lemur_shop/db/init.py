from __future__ import annotations

from sqlalchemy import text

from lemur_shop.db.models import Base
from lemur_shop.db.session import engine

_MIGRATIONS = [
    "ALTER TABLE orders ADD COLUMN IF NOT EXISTS cost_usd NUMERIC(10,2)",
    "ALTER TABLE orders ADD COLUMN IF NOT EXISTS category VARCHAR(32)",
    "ALTER TABLE topups ADD COLUMN IF NOT EXISTS method VARCHAR(16) DEFAULT 'admin'",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS balance_stars BIGINT DEFAULT 0",
    "UPDATE users SET balance_stars = ROUND(CAST(balance_usd AS FLOAT) / 0.013) WHERE balance_stars = 0 AND CAST(balance_usd AS FLOAT) > 0.009",
    "ALTER TABLE topups ADD COLUMN IF NOT EXISTS amount_stars BIGINT DEFAULT 0",
    "CREATE TABLE IF NOT EXISTS game_plays (id SERIAL PRIMARY KEY, user_id BIGINT NOT NULL, score INT DEFAULT 0, stars_earned INT DEFAULT 0, is_free BOOLEAN DEFAULT FALSE, created_at TIMESTAMP DEFAULT NOW())",
]


async def create_tables() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        for sql in _MIGRATIONS:
            await conn.execute(text(sql))
