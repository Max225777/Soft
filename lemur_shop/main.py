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

    # On Render use webhook (no polling conflict on redeploy).
    # Locally fall back to polling.
    render_url = os.environ.get("RENDER_EXTERNAL_URL", "")
    webhook_base = (settings.WEBAPP_URL or render_url).rstrip("/")

    if webhook_base:
        webhook_url = webhook_base + "/webhook"
        await bot.set_webhook(webhook_url, drop_pending_updates=True)
        log.info("Webhook встановлено: %s", webhook_url)

        port = int(os.environ.get("PORT", 8080))
        app = web.Application()
        SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path="/webhook")
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
        log.info("Web server (webhook) on :%s", port)
        log.info("🦎 Лемур бот запущено")
        await asyncio.Event().wait()
    else:
        # Local dev: polling mode
        port = int(os.environ.get("PORT", 8080))
        app = web.Application()
        app.router.add_get("/health", health)
        app.router.add_get("/", health)
        runner = web.AppRunner(app)
        await runner.setup()
        await web.TCPSite(runner, "0.0.0.0", port).start()
        log.info("Web server (polling) on :%s", port)

        await bot.delete_webhook(drop_pending_updates=True)
        log.info("🦎 Лемур бот запущено (polling)")
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


if __name__ == "__main__":
    asyncio.run(main())
