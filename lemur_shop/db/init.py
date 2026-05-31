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
    "CREATE TABLE IF NOT EXISTS wheel_pot (id INTEGER PRIMARY KEY DEFAULT 1, stars BIGINT DEFAULT 0)",
    "INSERT INTO wheel_pot (id, stars) VALUES (1, 0) ON CONFLICT (id) DO NOTHING",
    "CREATE TABLE IF NOT EXISTS wheel_rooms (id SERIAL PRIMARY KEY, stake INT NOT NULL, max_players INT NOT NULL, status VARCHAR(16) DEFAULT 'waiting', winner_user_id BIGINT, winner_name VARCHAR(64), payout INT DEFAULT 0, created_at TIMESTAMP DEFAULT NOW())",
    "CREATE TABLE IF NOT EXISTS wheel_participants (id SERIAL PRIMARY KEY, room_id INT NOT NULL REFERENCES wheel_rooms(id), user_id BIGINT, name VARCHAR(64) NOT NULL, is_bot BOOLEAN DEFAULT FALSE, joined_at TIMESTAMP DEFAULT NOW())",
    "ALTER TABLE topups ADD COLUMN IF NOT EXISTS method VARCHAR(16) DEFAULT 'admin'",
    "ALTER TABLE topups ADD COLUMN IF NOT EXISTS charge_id VARCHAR(128)",
    "CREATE UNIQUE INDEX IF NOT EXISTS uq_topups_charge_id ON topups (charge_id) WHERE charge_id IS NOT NULL",
]


async def create_tables() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        for sql in _MIGRATIONS:
            await conn.execute(text(sql))
