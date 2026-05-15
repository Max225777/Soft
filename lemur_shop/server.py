from __future__ import annotations

import asyncio
import hashlib
import hmac
import httpx
import json
import logging
import os
from contextlib import asynccontextmanager
from urllib.parse import parse_qsl, unquote

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Update
from fastapi import Depends, FastAPI, HTTPException, Header, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy import func, select

from lemur_shop.api.lolz import LolzApiError
from lemur_shop.config import settings
from lemur_shop.db.init import create_tables
from lemur_shop.db.models import Order, ReferralPayout, User
from lemur_shop.db.session import AsyncSessionLocal
from decimal import Decimal

from lemur_shop.services.lolz_shop import CATEGORIES, auto_buy_category
from lemur_shop.utils.currency import get_rate

log = logging.getLogger(__name__)
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")

_bot: Bot | None = None
_dp: Dispatcher | None = None
_polling_task: asyncio.Task | None = None
_keepalive_task: asyncio.Task | None = None


async def _keepalive(url: str) -> None:
    """Пінгує власний /health кожні 10 хв, щоб Render не вимикав сервіс."""
    async with httpx.AsyncClient(timeout=10) as client:
        while True:
            await asyncio.sleep(600)
            try:
                await client.get(url)
                log.debug("keepalive ping ok")
            except Exception as e:
                log.debug("keepalive ping failed: %s", e)

@asynccontextmanager
async def lifespan(app: FastAPI):
    global _bot, _dp, _polling_task

    if not settings.BOT_TOKEN:
        log.error("BOT_TOKEN не задано")
        yield
        return

    log.info("Підключення до БД...")
    await create_tables()
    log.info("БД готова")

    _bot = Bot(token=settings.BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    _dp = Dispatcher(storage=MemoryStorage())

    from lemur_shop.handlers import admin, profile, shop, start
    _dp.include_router(start.router)
    _dp.include_router(shop.router)
    _dp.include_router(profile.router)
    _dp.include_router(admin.router)

    webapp_url = settings.WEBAPP_URL.rstrip("/") if settings.WEBAPP_URL else ""
    use_webhook = False

    if webapp_url.startswith("https://"):
        try:
            await _bot.set_webhook(webapp_url + "/webhook", drop_pending_updates=True)
            use_webhook = True
            log.info("Webhook: %s/webhook", webapp_url)
        except Exception as e:
            log.warning("Webhook не вдалось (%s) — polling", e)
            await _bot.delete_webhook()

    if not use_webhook:
        await _bot.delete_webhook(drop_pending_updates=False)
        _polling_task = asyncio.create_task(
            _dp.start_polling(_bot, allowed_updates=_dp.resolve_used_update_types())
        )

    if webapp_url.startswith("https://"):
        _keepalive_task = asyncio.create_task(_keepalive(webapp_url + "/health"))

    log.info("🦎 Лемур бот запущено (%s)", "webhook" if use_webhook else "polling")
    yield

    if _keepalive_task:
        _keepalive_task.cancel()
        try:
            await _keepalive_task
        except asyncio.CancelledError:
            pass
    if _polling_task:
        _polling_task.cancel()
        try:
            await _polling_task
        except asyncio.CancelledError:
            pass
    if use_webhook:
        await _bot.delete_webhook()
    await _bot.session.close()


app = FastAPI(title="Lemur Shop", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Static files ─────────────────────────────────────────────────────────────

if os.path.exists(os.path.join(STATIC_DIR, "assets")):
    app.mount("/assets", StaticFiles(directory=os.path.join(STATIC_DIR, "assets")), name="assets")


# ─── Telegram initData auth ───────────────────────────────────────────────────

def _validate_init_data(init_data: str) -> dict:
    pairs = dict(parse_qsl(init_data, keep_blank_values=True))
    hash_val = pairs.pop("hash", "")
    data_check = "\n".join(f"{k}={v}" for k, v in sorted(pairs.items()))
    secret = hmac.new(b"WebAppData", settings.BOT_TOKEN.encode(), hashlib.sha256).digest()
    expected = hmac.new(secret, data_check.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, hash_val):
        raise HTTPException(status_code=401, detail="Invalid initData")
    return json.loads(unquote(pairs.get("user", "{}")))


async def get_current_user(x_init_data: str = Header(...)) -> User:
    tg_user = _validate_init_data(x_init_data)
    tg_id = int(tg_user["id"])
    async with AsyncSessionLocal() as s:
        user = await s.get(User, tg_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found. Start bot first.")
    return user


# ─── Webhook ──────────────────────────────────────────────────────────────────

@app.post("/webhook")
async def telegram_webhook(request: Request):
    if _dp is None or _bot is None:
        return Response(status_code=503)
    data = await request.json()
    update = Update.model_validate(data, context={"bot": _bot})
    await _dp.feed_update(_bot, update)
    return Response()


# ─── Health ───────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"ok": True}


# ─── Schemas ──────────────────────────────────────────────────────────────────

class BuyRequest(BaseModel):
    category: str

class SetLangRequest(BaseModel):
    lang: str


# ─── API Routes ───────────────────────────────────────────────────────────────

def _level_discount_pct(total_spent_usd: float) -> int:
    if total_spent_usd >= 100: return 5
    if total_spent_usd >= 50:  return 3
    if total_spent_usd >= 15:  return 2
    if total_spent_usd >= 5:   return 1
    return 0


@app.get("/api/me")
async def api_me(user: User = Depends(get_current_user)):
    uah = await get_rate("UAH")
    rub = await get_rate("RUB")
    async with AsyncSessionLocal() as s:
        orders_count = await s.scalar(select(func.count()).where(Order.user_id == user.id))
        total_spent = await s.scalar(
            select(func.sum(Order.price_usd)).where(Order.user_id == user.id, Order.status == "delivered")
        ) or Decimal(0)
    lang = user.lang
    usd = float(user.balance_usd)
    return {
        "id":              user.id,
        "name":            user.full_name or user.username or str(user.id),
        "username":        user.username,
        "lang":            lang,
        "balance_usd":     usd,
        "balance_uah":     round(usd * uah, 0),
        "balance_rub":     round(usd * rub, 0),
        "rate_uah":        uah,
        "rate_rub":        rub,
        "orders_count":    orders_count,
        "total_spent_usd": float(total_spent),
        "is_admin":        user.id in settings.ADMIN_IDS,
    }


@app.post("/api/set-lang")
async def api_set_lang(body: SetLangRequest, user: User = Depends(get_current_user)):
    if body.lang not in ("ua", "ru", "en"):
        raise HTTPException(status_code=400, detail="Invalid lang")
    async with AsyncSessionLocal() as s:
        async with s.begin():
            u = await s.get(User, user.id)
            if u:
                u.lang = body.lang
    return {"ok": True}


@app.get("/api/categories")
async def api_categories(user: User = Depends(get_current_user)):
    return [
        {
            "category":  cat,
            "flag":      info["flag"],
            "title":     info["title"],
            "price_usd": info["price_usd"],
        }
        for cat, info in CATEGORIES.items()
    ]


@app.post("/api/buy")
async def api_buy(body: BuyRequest, user: User = Depends(get_current_user)):
    cat_info = CATEGORIES.get(body.category)
    if not cat_info:
        raise HTTPException(status_code=400, detail="Unknown category")

    base_price = Decimal(str(cat_info["price_usd"]))

    async with AsyncSessionLocal() as s:
        total_spent = await s.scalar(
            select(func.sum(Order.price_usd)).where(Order.user_id == user.id, Order.status == "delivered")
        ) or Decimal(0)
    discount_pct = _level_discount_pct(float(total_spent))
    shop_price = (base_price * Decimal(str(100 - discount_pct)) / Decimal("100")).quantize(Decimal("0.01"))

    if user.balance_usd < shop_price:
        raise HTTPException(status_code=402, detail="insufficient_balance")

    try:
        phone, lolz_item_id = await auto_buy_category(body.category)
    except (LolzApiError, ValueError, httpx.TimeoutException) as e:
        raise HTTPException(status_code=502, detail=str(e))

    async with AsyncSessionLocal() as s:
        async with s.begin():
            u = await s.get(User, user.id)
            u.balance_usd = u.balance_usd - shop_price
            order = Order(
                user_id=user.id,
                product_id=0,
                lolz_item_id=lolz_item_id,
                price_usd=shop_price,
                status="delivered",
                delivered_data=phone,
                resend_count=0,
            )
            s.add(order)
            await s.flush()
            order_id = order.id
            created_at = order.created_at
    return {"order_id": order_id, "phone": phone, "created_at": created_at.isoformat()}


@app.post("/api/get-code/{order_id}")
async def api_get_code(order_id: int, user: User = Depends(get_current_user)):
    from lemur_shop.api.lolz import lolz as lolz_client
    async with AsyncSessionLocal() as s:
        order = await s.get(Order, order_id)
    if not order or order.user_id != user.id:
        raise HTTPException(status_code=404, detail="Order not found")
    if not order.lolz_item_id:
        raise HTTPException(status_code=400, detail="No lolz item linked to this order")
    try:
        code = await lolz_client.get_telegram_code(order.lolz_item_id)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))
    if not code:
        raise HTTPException(status_code=502, detail="Empty code returned")
    return {"code": code}


@app.get("/api/check-sub")
async def api_check_sub(user: User = Depends(get_current_user)):
    if not _bot or not settings.CHANNEL_USERNAME:
        return {"subscribed": True}
    try:
        member = await _bot.get_chat_member(
            chat_id=settings.CHANNEL_USERNAME, user_id=user.id
        )
        subscribed = member.status not in ("left", "kicked")
    except Exception as e:
        log.warning("check-sub error for user=%s: %s — blocking", user.id, e)
        subscribed = False
    return {"subscribed": subscribed}


@app.get("/api/orders")
async def api_orders(user: User = Depends(get_current_user)):
    async with AsyncSessionLocal() as s:
        result = await s.execute(
            select(Order).where(Order.user_id == user.id)
            .order_by(Order.created_at.desc()).limit(20)
        )
        orders = result.scalars().all()
    return [
        {"id": o.id, "price_usd": float(o.price_usd), "status": o.status,
         "created_at": o.created_at.isoformat(), "delivered_data": o.delivered_data}
        for o in orders
    ]


@app.get("/api/referral")
async def api_referral(user: User = Depends(get_current_user)):
    async with AsyncSessionLocal() as s:
        ref_count = await s.scalar(select(func.count()).where(User.referred_by_id == user.id))
        earned = await s.scalar(
            select(func.coalesce(func.sum(ReferralPayout.bonus_usd), 0))
            .where(ReferralPayout.referrer_id == user.id)
        )
    return {
        "referral_code": user.referral_code,
        "ref_count":     ref_count or 0,
        "earned_usd":    float(earned or 0),
        "bonus_pct":     settings.REFERRAL_BONUS_PERCENT,
    }


# ─── SPA fallback ─────────────────────────────────────────────────────────────

@app.get("/{path:path}")
async def spa_fallback(path: str):
    index = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index):
        return FileResponse(index)
    return JSONResponse({"ok": True})
