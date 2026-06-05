from __future__ import annotations

from sqlalchemy import text

from lemur_shop.db.models import Base
from lemur_shop.db.session import engine

_MIGRATIONS = [
    "ALTER TABLE orders ADD COLUMN IF NOT EXISTS cost_usd NUMERIC(10,2)",
    "ALTER TABLE orders ADD COLUMN IF NOT EXISTS category VARCHAR(32)",
    "ALTER TABLE topups ADD COLUMN IF NOT EXISTS method VARCHAR(16) DEFAULT 'admin'",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS balance_stars BIGINT DEFAULT 0",
    # Одноразова конвертація USD→stars (лише для юзерів БЕЗ замовлень, щоб не відновлювати після покупок)
    "UPDATE users SET balance_stars = ROUND(CAST(balance_usd AS NUMERIC) / 0.013) WHERE balance_stars = 0 AND CAST(balance_usd AS NUMERIC) > 0.009 AND NOT EXISTS (SELECT 1 FROM orders WHERE orders.user_id = users.id)",
    "ALTER TABLE topups ADD COLUMN IF NOT EXISTS amount_stars BIGINT DEFAULT 0",
    "CREATE TABLE IF NOT EXISTS game_plays (id SERIAL PRIMARY KEY, user_id BIGINT NOT NULL, score INT DEFAULT 0, stars_earned INT DEFAULT 0, is_free BOOLEAN DEFAULT FALSE, created_at TIMESTAMP DEFAULT NOW())",
    "CREATE TABLE IF NOT EXISTS wheel_pot (id INTEGER PRIMARY KEY DEFAULT 1, stars BIGINT DEFAULT 0)",
    "INSERT INTO wheel_pot (id, stars) VALUES (1, 0) ON CONFLICT (id) DO NOTHING",
    "CREATE TABLE IF NOT EXISTS wheel_rooms (id SERIAL PRIMARY KEY, stake INT NOT NULL, max_players INT NOT NULL, status VARCHAR(16) DEFAULT 'waiting', winner_user_id BIGINT, winner_name VARCHAR(64), payout INT DEFAULT 0, created_at TIMESTAMP DEFAULT NOW())",
    "CREATE TABLE IF NOT EXISTS wheel_participants (id SERIAL PRIMARY KEY, room_id INT NOT NULL REFERENCES wheel_rooms(id), user_id BIGINT, name VARCHAR(64) NOT NULL, is_bot BOOLEAN DEFAULT FALSE, joined_at TIMESTAMP DEFAULT NOW())",
    "ALTER TABLE topups ADD COLUMN IF NOT EXISTS method VARCHAR(16) DEFAULT 'admin'",
    "ALTER TABLE topups ADD COLUMN IF NOT EXISTS charge_id VARCHAR(512)",
    "ALTER TABLE topups ALTER COLUMN charge_id TYPE VARCHAR(512)",
    "CREATE UNIQUE INDEX IF NOT EXISTS uq_topups_charge_id ON topups (charge_id) WHERE charge_id IS NOT NULL",
    # Перераховуємо price_usd для старих USA ордерів де зберігся прайсовий $1.30 замість реального $0.325 (25 зірок)
    "UPDATE orders SET price_usd = 0.3250 WHERE category = 'us' AND price_usd = 1.30",
    # Перераховуємо для UA/KZ: прайс $3.25 → реальний $1.95 (150 зірок × $0.013)
    "UPDATE orders SET price_usd = 1.9500 WHERE category IN ('ua','kz') AND price_usd = 3.25",
    # Бекфілл cost_usd для SMM замовлень де cost_usd IS NULL
    # Формула: cost = (price_usd / 0.013) * (100 / price_per_100_stars) * (cost_rub_per_1000 / 1000 / 90)
    # Підписники: price_per_100_stars=10, cost_rub=41  → ratio = 100/10 * 41/117000 = 0.3504
    "UPDATE orders SET cost_usd = ROUND(CAST(price_usd AS NUMERIC) * 0.3504, 6) WHERE category = 'tg_subscribers' AND (cost_usd IS NULL OR cost_usd = 0) AND status = 'delivered'",
    # Перегляди: price_per_100_stars=1.5, cost_rub=8.8 → ratio = 100/1.5 * 8.8/117000 = 0.5013
    "UPDATE orders SET cost_usd = ROUND(CAST(price_usd AS NUMERIC) * 0.5013, 6) WHERE category = 'tg_views' AND (cost_usd IS NULL OR cost_usd = 0) AND status = 'delivered'",
    # Реакції: price_per_100_stars=3.34, cost_rub=1.0 → ratio = 100*1.0/(1000*90*3.34*0.013) = 0.02559
    "UPDATE orders SET cost_usd = ROUND(CAST(price_usd AS NUMERIC) * 0.02559, 6) WHERE category IN ('tg_reactions','tg_react_poop','tg_react_clown','tg_react_middlefinger','tg_react_vomit') AND (cost_usd IS NULL OR cost_usd = 0) AND status = 'delivered'",
    # Додаємо колонку smm_quantity для зберігання кількості накрутки
    "ALTER TABLE orders ADD COLUMN IF NOT EXISTS smm_quantity INT DEFAULT 0",
    # Бекфілл cost_usd для нових реакцій (❤️ 6077, 🔥 6078, мікси 6255/6256) cost=0.98₽/1000
    # ratio = 100*0.98/(1000*90*3.34*0.013) = 0.02508
    "UPDATE orders SET cost_usd = ROUND(CAST(price_usd AS NUMERIC) * 0.02508, 6) WHERE category IN ('tg_react_heart','tg_react_fire','tg_react_mix_pos','tg_react_mix_neg') AND (cost_usd IS NULL OR cost_usd = 0) AND status = 'delivered'",
    # Виправлення старих реакцій де cost_usd був встановлений з неправильним ratio (0.000256 замість 0.02559)
    "UPDATE orders SET cost_usd = ROUND(CAST(price_usd AS NUMERIC) * 0.02559, 6) WHERE category IN ('tg_reactions','tg_react_poop','tg_react_clown','tg_react_middlefinger','tg_react_vomit') AND cost_usd > 0 AND cost_usd < 0.001 AND status = 'delivered'",
]


async def create_tables() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        for sql in _MIGRATIONS:
            await conn.execute(text(sql))
