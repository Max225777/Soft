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
from aiogram.webhook.aiohttp_server import SimpleRequestHandler

from lemur_shop.config import settings
from lemur_shop.db.init import create_tables
from lemur_shop.handlers import admin, profile, shop, start

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)
log = logging.getLogger(__name__)

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")


async def health(request: web.Request) -> web.Response:
    return web.Response(text="ok")


async def index(request: web.Request) -> web.Response:
    index_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_path):
        with open(index_path) as f:
            return web.Response(text=f.read(), content_type="text/html")
    return web.Response(text="Mini App not built yet")


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

    bot = Bot(
        token=settings.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(start.router)
    dp.include_router(shop.router)
    dp.include_router(profile.router)
    dp.include_router(admin.router)

    port = int(os.environ.get("PORT", 8080))
    app = web.Application()

    # Try webhook if WEBAPP_URL looks valid (starts with https://)
    webapp_url = settings.WEBAPP_URL.rstrip("/") if settings.WEBAPP_URL else ""
    use_webhook = False

    if webapp_url.startswith("https://"):
        webhook_url = webapp_url + "/webhook"
        log.info("Спроба webhook: %s", webhook_url)
        try:
            await bot.set_webhook(webhook_url, drop_pending_updates=True)
            SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path="/webhook")
            use_webhook = True
            log.info("Webhook активний")
        except Exception as e:
            log.warning("Webhook не вдалось: %s — переходжу на polling", e)
            await bot.delete_webhook()

    app.router.add_get("/health", health)
    if os.path.exists(STATIC_DIR):
        app.router.add_static("/assets", os.path.join(STATIC_DIR, "assets"), show_index=False)
        app.router.add_get("/", index)
        app.router.add_get("/{tail:.*}", index)
    else:
        app.router.add_get("/", health)

    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", port).start()
    log.info("Web server on :%s", port)

    if use_webhook:
        log.info("🦎 Лемур бот запущено (webhook)")
        await asyncio.Event().wait()
    else:
        await bot.delete_webhook(drop_pending_updates=False)
        log.info("🦎 Лемур бот запущено (polling)")
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


if __name__ == "__main__":
    asyncio.run(main())
