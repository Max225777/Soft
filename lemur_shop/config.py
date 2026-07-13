from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    BOT_TOKEN: str = ""
    ADMIN_IDS: list[int] = []

    DATABASE_URL: str = "postgresql+asyncpg://lemur:lemur@localhost:5432/lemur"

    LOLZ_API_TOKEN: str = ""
    LOLZ_API_BASE_URL: str = "https://prod-api.lzt.market/"

    REFERRAL_BONUS_PERCENT: float = 5.0

    WEBAPP_URL: str = ""   # https://your-domain.com — URL задеплоєного Mini App

    CHANNEL_USERNAME: str = "@LEMUR_SHOP"
    SUPPORT_USERNAME: str = "@LEMUR_MANEGER"
    # Публічний канал з відгуками покупців (для банку — реальні відгуки)
    REVIEWS_CHANNEL_USERNAME: str = "@LEMUR_SHOP_REP"
    # E-mail підтримки (необов'язково; якщо порожньо — показуємо лише юзернейм)
    SUPPORT_EMAIL: str = ""
    # Канал-вітрина, куди бот постить кожну покупку (соц-докз для покупців)
    SELL_CHANNEL_USERNAME: str = "@LEMUR_SHOP_SELL"
    # Keywords for tier-2 detection — any match (normalized) alongside lemurshop = tier 2
    # "накрутка" covers UA+RU phrase, "cheap" covers EN phrase
    BIO_PROMO_PHRASE_KEYWORDS: list[str] = ["накрутка", "cheap"]
    # 1 Star ≈ $0.013 (курс при поповненні балансу зірками)
    STAR_DISPLAY_USD: float = 0.013
    # Stars з користувача за $1 ціни товару (= round(1/STAR_DISPLAY_USD))
    STARS_PER_PRODUCT_USD: int = 77
    # Stars за $1 при поповненні через бот-команду /topup
    STARS_PER_USD: int = 77

    CRYPTOBOT_TOKEN: str = ""

    # Heleket (крипто-платіжка, ex-Cryptomus). Обидва значення — з розділу API
    # твого проєкту в дешборді Heleket.
    HELEKET_MERCHANT_ID: str = ""
    HELEKET_API_KEY: str = ""

    SMMWAY_API_KEY: str = ""
    PREVIEW_MODE: bool = False


settings = Settings()
