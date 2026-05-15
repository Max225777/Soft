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


def _build_app(dp: Dispatcher, bot: Bot, webhook_path: str | None) -> web.Application:
    app = web.Application()
    if webhook_path:
        SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path=webhook_path)
    app.router.add_get("/health", health)
    if os.path.exists(STATIC_DIR):
        app.router.add_static("/assets", os.path.join(STATIC_DIR, "assets"), show_index=False)
        app.router.add_get("/", index)
        app.router.add_get("/{tail:.*}", index)
    else:
        app.router.add_get("/", health)
    return app


async def _run_app(app: web.Application) -> None:
    port = int(os.environ.get("PORT", 8080))
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", port).start()
    log.info("Web server on :%s", port)


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

    webhook_base = settings.WEBAPP_URL.rstrip("/") if settings.WEBAPP_URL else ""

    if webhook_base:
        # Webhook mode — no polling conflicts on redeploy
        webhook_path = "/webhook"
        webhook_url = webhook_base + webhook_path
        log.info("Встановлюю webhook: %s", webhook_url)
        await bot.set_webhook(webhook_url, drop_pending_updates=True)
        app = _build_app(dp, bot, webhook_path)
        await _run_app(app)
        log.info("🦎 Лемур бот запущено (webhook)")
        await asyncio.Event().wait()
    else:
        # Polling mode — wait for previous instance to die after SIGTERM
        app = _build_app(dp, bot, None)
        await _run_app(app)
        log.info("Чекаю завершення попереднього інстансу...")
        await asyncio.sleep(15)
        await bot.delete_webhook(drop_pending_updates=True)
        log.info("🦎 Лемур бот запущено (polling)")
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


if __name__ == "__main__":
    asyncio.run(main())
