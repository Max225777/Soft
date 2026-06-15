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
    # Бекфілл cost_usd для SMM замовлень (курс 70₽/$)
    # Формула ratio = cost_rub_per_1000 * 100 / (1000 * 70 * price_per_100_stars * 0.013)
    # Підписники: 41*100/(1000*70*10*0.013) = 4100/9100 = 0.4505
    "UPDATE orders SET cost_usd = ROUND(CAST(price_usd AS NUMERIC) * 0.4505, 6) WHERE category = 'tg_subscribers' AND (cost_usd IS NULL OR cost_usd = 0) AND status = 'delivered'",
    # Перегляди: 8.8*100/(1000*70*1.5*0.013) = 880/1365 = 0.6447
    "UPDATE orders SET cost_usd = ROUND(CAST(price_usd AS NUMERIC) * 0.6447, 6) WHERE category = 'tg_views' AND (cost_usd IS NULL OR cost_usd = 0) AND status = 'delivered'",
    # Реакції: 0.9*100/(1000*70*3.34*0.013) = 90/3039.4 = 0.02962
    # Безумовно виправляємо ВСІ reaction замовлення
    "UPDATE orders SET cost_usd = ROUND(CAST(price_usd AS NUMERIC) * 0.02962, 6) WHERE category IN ('tg_reactions','tg_react_like','tg_react_dislike','tg_react_heart','tg_react_fire','tg_react_poop','tg_react_clown','tg_react_middlefinger','tg_react_vomit','tg_react_nails','tg_react_crazy','tg_react_heartarrow','tg_react_monkey','tg_react_kiss','tg_react_sunglasses','tg_react_alien','tg_react_shrug','tg_react_angry','tg_react_neg_mix1','tg_react_mix_fun','tg_react_mix_ghost','tg_react_neg_mix2','tg_react_mix_scare') AND status = 'delivered'",
    # Додаємо колонку smm_quantity для зберігання кількості накрутки
    "ALTER TABLE orders ADD COLUMN IF NOT EXISTS smm_quantity INT DEFAULT 0",
    # Таблиця для промо в біо
    """CREATE TABLE IF NOT EXISTS bio_promos (
        user_id BIGINT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
        joined_at TIMESTAMP DEFAULT NOW(),
        last_check_at TIMESTAMP,
        last_rewarded_at TIMESTAMP,
        is_active BOOLEAN DEFAULT FALSE,
        total_rewarded INT DEFAULT 0
    )""",
    # Реферальні виплати — поле зірок
    "ALTER TABLE referral_payouts ADD COLUMN IF NOT EXISTS amount_stars INT DEFAULT 0",
    # Розширюємо precision price_usd/cost_usd до 6dp (було 2dp → SMM-копійки округлялись)
    "ALTER TABLE orders ALTER COLUMN price_usd TYPE NUMERIC(10,6)",
    "ALTER TABLE orders ALTER COLUMN cost_usd TYPE NUMERIC(10,6)",
    # Ре-бекфіл cost_usd для SMM (попередній бекфіл зберігся як 2dp і втратив точність)
    "UPDATE orders SET cost_usd = ROUND(CAST(price_usd AS NUMERIC) * 0.4505, 6) WHERE category = 'tg_subscribers' AND status = 'delivered'",
    "UPDATE orders SET cost_usd = ROUND(CAST(price_usd AS NUMERIC) * 0.6447, 6) WHERE category = 'tg_views' AND status = 'delivered'",
    "UPDATE orders SET cost_usd = ROUND(CAST(price_usd AS NUMERIC) * 0.02962, 6) WHERE category IN ('tg_reactions','tg_react_like','tg_react_dislike','tg_react_heart','tg_react_fire','tg_react_poop','tg_react_clown','tg_react_middlefinger','tg_react_vomit','tg_react_sunglasses','tg_react_angry','tg_react_neg_mix1') AND status = 'delivered'",
    """CREATE TABLE IF NOT EXISTS promo_codes (
        id SERIAL PRIMARY KEY,
        code VARCHAR(32) UNIQUE NOT NULL,
        reward_stars INT DEFAULT 0,
        max_activations INT DEFAULT 1,
        activations INT DEFAULT 0,
        is_active BOOLEAN DEFAULT TRUE,
        created_by BIGINT NOT NULL,
        created_at TIMESTAMP DEFAULT NOW()
    )""",
    """CREATE TABLE IF NOT EXISTS promo_activations (
        id SERIAL PRIMARY KEY,
        code_id INT NOT NULL REFERENCES promo_codes(id),
        user_id BIGINT NOT NULL REFERENCES users(id),
        activated_at TIMESTAMP DEFAULT NOW(),
        UNIQUE(code_id, user_id)
    )""",
]


async def create_tables() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        for sql in _MIGRATIONS:
            await conn.execute(text(sql))
