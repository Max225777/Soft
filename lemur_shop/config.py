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
    # 1 Star ≈ $0.013 (курс при поповненні балансу зірками)
    STAR_DISPLAY_USD: float = 0.013
    # Stars з користувача за $1 собівартості товару
    STARS_PER_PRODUCT_USD: int = 130
    # Stars за $1 при поповненні через бот-команду /topup
    STARS_PER_USD: int = 77

    FREEKASSA_MERCHANT_ID: str = ""
    FREEKASSA_SECRET1: str = ""
    FREEKASSA_SECRET2: str = ""
    FREEKASSA_API_KEY: str = ""

    CRYPTOBOT_TOKEN: str = ""


settings = Settings()
