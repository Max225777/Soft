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
from lemur_shop.db.models import Order, ReferralPayout, TopUp, User
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
    """Пінгує власний /health кожні 5 хв, перший пінг через 60с після старту."""
    async with httpx.AsyncClient(timeout=10) as client:
        await asyncio.sleep(60)
        while True:
            try:
                await client.get(url)
                log.info("keepalive ping ok")
            except Exception as e:
                log.warning("keepalive ping failed: %s", e)
            await asyncio.sleep(300)

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
    if user.is_banned:
        raise HTTPException(status_code=403, detail="banned")
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
        phone, lolz_item_id, lolz_price = await auto_buy_category(body.category)
    except (LolzApiError, ValueError, httpx.TimeoutException) as e:
        raise HTTPException(status_code=502, detail=str(e))

    lolz_cost = Decimal(str(round(lolz_price, 2)))

    async with AsyncSessionLocal() as s:
        async with s.begin():
            u = await s.get(User, user.id)
            u.balance_usd = u.balance_usd - shop_price
            order = Order(
                user_id=user.id,
                product_id=0,
                lolz_item_id=lolz_item_id,
                price_usd=shop_price,
                cost_usd=lolz_cost,
                category=body.category,
                status="delivered",
                delivered_data=phone,
                resend_count=0,
            )
            s.add(order)
            await s.flush()
            order_id = order.id
            created_at = order.created_at

    # Нотифікація адміну
    if _bot and settings.ADMIN_IDS:
        from lemur_shop.services.lolz_shop import CATEGORIES as _CATS
        cat_info = _CATS.get(body.category, {})
        profit = shop_price - lolz_cost
        uname = f"@{user.username}" if user.username else f"ID:{user.id}"
        flag = cat_info.get("flag", "")
        title = cat_info.get("title", body.category.upper())
        txt = (
            f"🛒 <b>Нова покупка!</b>\n\n"
            f"👤 {uname} (<code>{user.id}</code>)\n"
            f"📦 {flag} Telegram {title}\n"
            f"💳 Ціна: <b>${float(shop_price):.2f}</b>"
            + (f" (знижка {discount_pct}%)" if discount_pct else "") +
            f"\n💸 Витрати (Lolz): ${float(lolz_cost):.2f}\n"
            f"💰 Прибуток: <b>${float(profit):.2f}</b>\n\n"
            f"📱 Номер: <code>{phone}</code>\n"
            f"🆔 Lolz ID: <code>{lolz_item_id}</code>"
        )
        for admin_id in settings.ADMIN_IDS:
            try:
                await _bot.send_message(admin_id, txt, parse_mode="HTML")
            except Exception as e:
                log.warning("Admin notify failed for %s: %s", admin_id, e)

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
        from aiogram.enums import ChatMemberStatus
        member = await _bot.get_chat_member(
            chat_id=settings.CHANNEL_USERNAME, user_id=user.id
        )
        log.info("check-sub user=%s status=%r type=%s", user.id, member.status, type(member).__name__)
        subscribed = member.status in (
            ChatMemberStatus.CREATOR,
            ChatMemberStatus.ADMINISTRATOR,
            ChatMemberStatus.MEMBER,
            ChatMemberStatus.RESTRICTED,
        )
    except Exception as e:
        log.warning("check-sub error for user=%s: %s — letting through", user.id, e)
        subscribed = True
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


# ─── FreеKassa ────────────────────────────────────────────────────────────────

def _fk_sign(merchant_id: str, amount: str, secret: str, currency: str, order_id: str) -> str:
    raw = f"{merchant_id}:{amount}:{secret}:{currency}:{order_id}"
    return hashlib.md5(raw.encode()).hexdigest()


class FKCreateRequest(BaseModel):
    amount_usd: float
    currency: str = "USD"


@app.post("/api/fk/create")
async def api_fk_create(body: FKCreateRequest, user: User = Depends(get_current_user)):
    if not settings.FREEKASSA_MERCHANT_ID:
        raise HTTPException(status_code=503, detail="Payments not configured")
    amount = round(body.amount_usd, 2)
    if amount < 0.5 or amount > 1000:
        raise HTTPException(status_code=400, detail="Invalid amount")
    currency = body.currency if body.currency in ("USD", "UAH", "RUB", "KZT") else "USD"

    from lemur_shop.db.models import FKOrder
    async with AsyncSessionLocal() as s:
        async with s.begin():
            order = FKOrder(user_id=user.id, amount_usd=Decimal(str(amount)), currency=currency)
            s.add(order)
            await s.flush()
            order_id = order.id

    amount_str = f"{amount:.2f}"
    sign = _fk_sign(settings.FREEKASSA_MERCHANT_ID, amount_str, settings.FREEKASSA_SECRET1, currency, str(order_id))
    url = (
        f"https://pay.freekassa.net/?m={settings.FREEKASSA_MERCHANT_ID}"
        f"&oa={amount_str}&currency={currency}&o={order_id}&s={sign}&lang=ru"
    )
    return {"url": url, "order_id": order_id}


@app.get("/api/freekassa/notify")
async def fk_notify(
    MERCHANT_ID: str = "",
    AMOUNT: str = "",
    MERCHANT_ORDER_ID: str = "",
    P_EMAIL: str = "",
    P_PHONE: str = "",
    CUR_ID: str = "",
    SIGN: str = "",
    payer_account: str = "",
    payment_id: str = "",
):
    expected = hashlib.md5(f"{settings.FREEKASSA_MERCHANT_ID}:{AMOUNT}:{settings.FREEKASSA_SECRET2}:{MERCHANT_ORDER_ID}".encode()).hexdigest()
    if SIGN != expected:
        log.warning("FK notify bad sign order=%s", MERCHANT_ORDER_ID)
        return Response(content="NO", media_type="text/plain")

    from lemur_shop.db.models import FKOrder
    try:
        fk_order_id = int(MERCHANT_ORDER_ID)
        amount_usd = Decimal(AMOUNT)
    except Exception:
        return Response(content="NO", media_type="text/plain")

    async with AsyncSessionLocal() as s:
        async with s.begin():
            fk_order = await s.get(FKOrder, fk_order_id)
            if not fk_order or fk_order.status == "paid":
                return Response(content="YES", media_type="text/plain")
            fk_order.status = "paid"
            fk_order.fk_payment_id = payment_id or payer_account

            user = await s.get(User, fk_order.user_id)
            if user:
                user.balance_usd = user.balance_usd + amount_usd
                s.add(TopUp(user_id=user.id, amount_usd=amount_usd, admin_id=0))

    log.info("FK paid: order=%s user=%s amount=%s", fk_order_id, fk_order.user_id, amount_usd)

    if _bot and settings.ADMIN_IDS and user:
        uname = f"@{user.username}" if user.username else f"ID:{user.id}"
        txt = (
            f"💳 <b>Поповнення через FreеKassa!</b>\n\n"
            f"👤 {uname} (<code>{user.id}</code>)\n"
            f"💰 Зараховано: <b>${float(amount_usd):.2f}</b>\n"
            f"🆔 Замовлення FK: {fk_order_id}"
        )
        for admin_id in settings.ADMIN_IDS:
            try:
                await _bot.send_message(admin_id, txt, parse_mode="HTML")
            except Exception:
                pass

        try:
            await _bot.send_message(
                user.id,
                f"✅ Баланс поповнено на <b>${float(amount_usd):.2f}</b>!\n"
                f"💰 Поточний баланс: <b>${float(user.balance_usd):.2f}</b>",
                parse_mode="HTML"
            )
        except Exception:
            pass

    return Response(content="YES", media_type="text/plain")


@app.get("/api/freekassa/success")
async def fk_success():
    index = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index):
        return FileResponse(index)
    return JSONResponse({"ok": True, "status": "paid"})


@app.get("/api/freekassa/fail")
async def fk_fail():
    index = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index):
        return FileResponse(index)
    return JSONResponse({"ok": False, "status": "failed"})


# ─── CryptoBot ────────────────────────────────────────────────────────────────

CRYPTOBOT_API = "https://pay.crypt.bot/api"


async def _cryptobot(method: str, **params) -> dict:
    headers = {"Crypto-Pay-API-Token": settings.CRYPTOBOT_TOKEN}
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.post(f"{CRYPTOBOT_API}/{method}", json=params, headers=headers)
    data = r.json()
    if not data.get("ok"):
        raise HTTPException(status_code=502, detail=data.get("error", {}).get("name", "CryptoBot error"))
    return data["result"]


class CryptoCreateRequest(BaseModel):
    amount_usd: float


@app.post("/api/crypto/create")
async def api_crypto_create(body: CryptoCreateRequest, user: User = Depends(get_current_user)):
    if not settings.CRYPTOBOT_TOKEN:
        raise HTTPException(status_code=503, detail="CryptoBot not configured")
    amount = round(body.amount_usd, 2)
    if amount < 0.5 or amount > 1000:
        raise HTTPException(status_code=400, detail="Invalid amount")

    result = await _cryptobot(
        "createInvoice",
        asset="USDT",
        amount=str(amount),
        payload=f"cryptotopup:{user.id}:{amount}",
        description=f"Поповнення балансу Lemur Shop ${amount:.2f}",
        allow_comments=False,
        allow_anonymous=True,
        expires_in=3600,
    )
    return {"url": result["bot_invoice_url"], "invoice_id": result["invoice_id"]}


@app.post("/api/crypto/notify")
async def crypto_notify(request: Request):
    body = await request.body()
    signature = request.headers.get("crypto-pay-api-signature", "")
    secret = hashlib.sha256(settings.CRYPTOBOT_TOKEN.encode()).digest()
    expected = hmac.new(secret, body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature):
        log.warning("CryptoBot bad signature")
        return Response(status_code=400)

    data = await request.json()
    if data.get("update_type") != "invoice_paid":
        return Response(content="ok")

    invoice = data.get("payload", {})
    raw_payload = invoice.get("payload", "")
    status = invoice.get("status", "")
    if status != "paid" or not raw_payload.startswith("cryptotopup:"):
        return Response(content="ok")

    try:
        _, user_id_str, amount_str = raw_payload.split(":")
        user_id = int(user_id_str)
        amount_usd = Decimal(amount_str)
    except Exception as e:
        log.error("CryptoBot bad payload %r: %s", raw_payload, e)
        return Response(content="ok")

    async with AsyncSessionLocal() as s:
        async with s.begin():
            user = await s.get(User, user_id)
            if not user:
                return Response(content="ok")
            user.balance_usd = user.balance_usd + amount_usd
            s.add(TopUp(user_id=user_id, amount_usd=amount_usd, admin_id=0))

    log.info("CryptoBot paid: user=%s amount=%s", user_id, amount_usd)

    if _bot:
        if settings.ADMIN_IDS:
            uname = f"@{user.username}" if user.username else f"ID:{user_id}"
            txt = (
                f"💎 <b>Поповнення через CryptoBot!</b>\n\n"
                f"👤 {uname} (<code>{user_id}</code>)\n"
                f"💰 Зараховано: <b>${float(amount_usd):.2f} USDT</b>"
            )
            for admin_id in settings.ADMIN_IDS:
                try:
                    await _bot.send_message(admin_id, txt, parse_mode="HTML")
                except Exception:
                    pass
        try:
            await _bot.send_message(
                user_id,
                f"✅ Баланс поповнено на <b>${float(amount_usd):.2f}</b>!\n"
                f"💰 Поточний баланс: <b>${float(user.balance_usd):.2f}</b>",
                parse_mode="HTML"
            )
        except Exception:
            pass

    return Response(content="ok")


# ─── SPA fallback ─────────────────────────────────────────────────────────────

@app.get("/{path:path}")
async def spa_fallback(path: str):
    index = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index):
        return FileResponse(index, headers={"Cache-Control": "no-cache, no-store, must-revalidate"})
    return JSONResponse({"ok": True})
