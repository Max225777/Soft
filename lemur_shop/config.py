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

    CHANNEL_USERNAME: str = "@LEMUR_SHOP"   # канал для перевірки підписки
    SUPPORT_USERNAME: str = "@LEMUR_MANEGER"


settings = Settings()
