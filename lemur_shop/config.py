from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Telegram
    BOT_TOKEN: str = ""
    ADMIN_IDS: list[int] = []

    # DB
    DATABASE_URL: str = "postgresql+asyncpg://lemur:lemur@localhost:5432/lemur"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # Lolzteam
    LOLZ_API_TOKEN: str = ""
    LOLZ_API_BASE_URL: str = "https://prod-api.lzt.market/"

    # CryptoBot
    CRYPTOBOT_TOKEN: str = ""
    CRYPTOBOT_API_URL: str = "https://pay.crypt.bot/api"

    # FreeCassa
    FREECASSA_MERCHANT_ID: str = ""
    FREECASSA_SECRET1: str = ""
    FREECASSA_SECRET2: str = ""

    # Stars
    STARS_PER_USD: float = 50.0  # оновлюється динамічно

    # Referral
    REFERRAL_BONUS_PERCENT: float = 5.0

    # Mini App
    WEBAPP_URL: str = ""


settings = Settings()
