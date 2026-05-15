from __future__ import annotations

import asyncio
import logging
import os
import sys
from aiohttp import web

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from lemur_shop.config import settings
from lemur_shop.db.init import create_tables
from lemur_shop.handlers import admin, profile, shop, start

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)
log = logging.getLogger(__name__)


async def health(request: web.Request) -> web.Response:
    return web.Response(text="ok")


async def run_health_server() -> None:
    port = int(os.environ.get("PORT", 8080))
    app = web.Application()
    app.router.add_get("/", health)
    app.router.add_get("/health", health)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", port).start()
    log.info("Health server on port %s", port)


async def main() -> None:
    if not settings.BOT_TOKEN:
        log.error("BOT_TOKEN не задано — зупинка")
        return

    log.info("Підключення до БД...")
    try:
        await create_tables()
        log.info("БД готова")
    except Exception as e:
        log.error("Помилка БД: %s", e)
        raise

    await run_health_server()

    bot = Bot(
        token=settings.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    await bot.delete_webhook(drop_pending_updates=True)
    log.info("Webhook видалено")

    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(start.router)
    dp.include_router(shop.router)
    dp.include_router(profile.router)
    dp.include_router(admin.router)

    log.info("🦎 Лемур бот запущено")
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


if __name__ == "__main__":
    asyncio.run(main())
