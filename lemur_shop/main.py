from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from bot.config import settings
from bot.db.init import create_tables
from bot.handlers import balance, profile, start
from bot.services.stars import fetch_stars_rate, set_rate
from bot.utils.currency import fetch_rates, set_rates

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)


async def on_startup(bot: Bot) -> None:
    await create_tables()

    # Курс зірок
    rate = await fetch_stars_rate()
    set_rate(rate)
    log.info("Stars rate: 1 USD = %s ⭐", rate)

    # Курси валют
    rates = await fetch_rates()
    set_rates(rates)
    log.info("Exchange rates loaded: %s", rates)


async def main() -> None:
    bot = Bot(
        token=settings.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()

    dp.startup.register(on_startup)

    dp.include_router(start.router)
    dp.include_router(balance.router)
    dp.include_router(profile.router)

    log.info("Starting Лемур bot...")
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


if __name__ == "__main__":
    asyncio.run(main())
