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
from aiogram.types import LabeledPrice, Update
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
    global _bot, _dp, _polling_task, _BOT_USERNAME

    if not settings.BOT_TOKEN:
        log.error("BOT_TOKEN не задано")
        yield
        return

    log.info("Підключення до БД...")
    await create_tables()
    log.info("БД готова")

    _bot = Bot(token=settings.BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    _dp = Dispatcher(storage=MemoryStorage())
    try:
        bot_info = await _bot.get_me()
        _BOT_USERNAME = bot_info.username
    except Exception:
        pass

    from lemur_shop.handlers import admin, profile, shop, start
    _dp.include_router(start.router)
    _dp.include_router(shop.router)
    _dp.include_router(profile.router)
    _dp.include_router(admin.router)
    from lemur_shop.handlers import payments as _pay_handlers
    _dp.include_router(_pay_handlers.router)
    from lemur_shop.handlers import topup as _topup_handlers
    _dp.include_router(_topup_handlers.router)

    webapp_url = settings.WEBAPP_URL.rstrip("/") if settings.WEBAPP_URL else ""
    use_webhook = False

    if webapp_url.startswith("https://"):
        try:
            allowed = _dp.resolve_used_update_types()
            await _bot.set_webhook(
                webapp_url + "/webhook",
                drop_pending_updates=True,
                allowed_updates=allowed,
            )
            use_webhook = True
            log.info("Webhook: %s/webhook (updates: %s)", webapp_url, allowed)
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


@app.get("/api/me")
async def api_me(user: User = Depends(get_current_user)):
    uah = await get_rate("UAH")
    rub = await get_rate("RUB")
    async with AsyncSessionLocal() as s:
        orders_count = await s.scalar(select(func.count()).where(Order.user_id == user.id))
    lang = user.lang
    stars = user.balance_stars
    usd_display = round(stars * settings.STAR_DISPLAY_USD, 2)
    return {
        "id":            user.id,
        "name":          user.full_name or user.username or str(user.id),
        "username":      user.username,
        "lang":          lang,
        "balance_stars": stars,
        "balance_usd":   usd_display,
        "balance_uah":   round(usd_display * uah, 0),
        "balance_rub":   round(usd_display * rub, 0),
        "rate_uah":      uah,
        "rate_rub":      rub,
        "orders_count":  orders_count,
        "is_admin":      user.id in settings.ADMIN_IDS,
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
            "category":    cat,
            "flag":        info["flag"],
            "title":       info["title"],
            "price_usd":   info["price_usd"],
            "price_stars": round(info["price_usd"] / settings.STAR_DISPLAY_USD),
        }
        for cat, info in CATEGORIES.items()
    ]


@app.post("/api/buy")
async def api_buy(body: BuyRequest, user: User = Depends(get_current_user)):
    cat_info = CATEGORIES.get(body.category)
    if not cat_info:
        raise HTTPException(status_code=400, detail="Unknown category")

    base_price_usd = cat_info["price_usd"]
    shop_price_stars = round(base_price_usd / settings.STAR_DISPLAY_USD)
    shop_price_usd = Decimal(str(round(float(base_price_usd), 2)))

    if user.balance_stars < shop_price_stars:
        raise HTTPException(status_code=402, detail="insufficient_balance")

    try:
        phone, lolz_item_id, lolz_price = await auto_buy_category(body.category)
    except (LolzApiError, ValueError, httpx.TimeoutException) as e:
        raise HTTPException(status_code=502, detail=str(e))

    lolz_cost = Decimal(str(round(lolz_price, 2)))

    async with AsyncSessionLocal() as s:
        async with s.begin():
            u = await s.get(User, user.id)
            u.balance_stars = u.balance_stars - shop_price_stars
            order = Order(
                user_id=user.id,
                product_id=0,
                lolz_item_id=lolz_item_id,
                price_usd=shop_price_usd,
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
        profit = shop_price_usd - lolz_cost
        uname = f"@{user.username}" if user.username else f"ID:{user.id}"
        flag = cat_info.get("flag", "")
        title = cat_info.get("title", body.category.upper())
        txt = (
            f"🛒 <b>Нова покупка!</b>\n\n"
            f"👤 {uname} (<code>{user.id}</code>)\n"
            f"📦 {flag} Telegram {title}\n"
            f"💫 Ціна: <b>⭐{shop_price_stars}</b> (${float(shop_price_usd):.2f})\n"
            f"💸 Витрати (Lolz): ${float(lolz_cost):.2f}\n"
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
    amount_usd = round(body.amount_usd, 2)
    if amount_usd < 0.5 or amount_usd > 1000:
        raise HTTPException(status_code=400, detail="Invalid amount")

    rub_rate = await get_rate("RUB")
    amount_rub = round(amount_usd * rub_rate)
    currency = "RUB"

    from lemur_shop.db.models import FKOrder
    async with AsyncSessionLocal() as s:
        async with s.begin():
            order = FKOrder(user_id=user.id, amount_usd=Decimal(str(amount_usd)), currency=currency)
            s.add(order)
            await s.flush()
            order_id = order.id

    amount_str = str(amount_rub)
    sign = _fk_sign(settings.FREEKASSA_MERCHANT_ID, amount_str, settings.FREEKASSA_SECRET1, "RUB", str(order_id))
    url = (
        f"https://pay.fk.money/?m={settings.FREEKASSA_MERCHANT_ID}"
        f"&oa={amount_str}&currency=RUB&o={order_id}&s={sign}&lang=ru"
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
    except Exception:
        return Response(content="NO", media_type="text/plain")

    async with AsyncSessionLocal() as s:
        async with s.begin():
            fk_order = await s.get(FKOrder, fk_order_id)
            if not fk_order or fk_order.status == "paid":
                return Response(content="YES", media_type="text/plain")
            fk_order.status = "paid"
            fk_order.fk_payment_id = payment_id or payer_account
            amount_usd = fk_order.amount_usd

            user = await s.get(User, fk_order.user_id)
            if user:
                user.balance_usd = user.balance_usd + amount_usd
                s.add(TopUp(user_id=user.id, amount_usd=amount_usd, admin_id=0))

    log.info("FK paid: order=%s user=%s amount_usd=%s", fk_order_id, fk_order.user_id, amount_usd)

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


_PAYMENT_PAGE = """<!DOCTYPE html>
<html><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
body{{margin:0;min-height:100vh;display:flex;align-items:center;justify-content:center;
background:#0C0C10;font-family:sans-serif;color:#fff;text-align:center;padding:24px;box-sizing:border-box}}
.icon{{font-size:64px;margin-bottom:16px}}
h2{{margin:0 0 8px;font-size:22px}}
p{{margin:0 0 28px;color:#888;font-size:14px}}
a{{display:inline-block;background:linear-gradient(135deg,#FF6B2B,#e05520);color:#fff;
text-decoration:none;border-radius:14px;padding:14px 32px;font-weight:700;font-size:15px}}
</style></head><body>
<div><div class="icon">{icon}</div>
<h2>{title}</h2><p>{desc}</p>
<a href="https://t.me/{bot}">Повернутись в Telegram</a>
</div></body></html>"""

_BOT_USERNAME: str | None = None

@app.get("/api/freekassa/success")
async def fk_success():
    from fastapi.responses import HTMLResponse
    bot_name = _BOT_USERNAME or "LemurShopBot"
    html = _PAYMENT_PAGE.format(
        icon="✅", title="Оплата успішна!",
        desc="Баланс поповнено. Поверніться в бот.",
        bot=bot_name,
    )
    return HTMLResponse(html)


@app.get("/api/freekassa/fail")
async def fk_fail():
    from fastapi.responses import HTMLResponse
    bot_name = _BOT_USERNAME or "LemurShopBot"
    html = _PAYMENT_PAGE.format(
        icon="❌", title="Оплата не пройшла",
        desc="Спробуйте ще раз або оберіть інший спосіб оплати.",
        bot=bot_name,
    )
    return HTMLResponse(html)


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


# ─── Telegram Stars ───────────────────────────────────────────────────────────

@app.get("/api/stars/rate")
async def api_stars_rate():
    return {"stars_per_usd": settings.STARS_PER_USD}


class StarsInvoiceRequest(BaseModel):
    stars: int

class StarsBuyRequest(BaseModel):
    stars: int
    amount_usd: float


@app.post("/api/stars/invoice")
async def api_stars_invoice(body: StarsInvoiceRequest, user: User = Depends(get_current_user)):
    if _bot is None:
        raise HTTPException(status_code=503, detail="Bot not ready")
    stars = body.stars
    if stars < 1 or stars > 100000:
        raise HTTPException(status_code=400, detail="Invalid amount")
    amount_usd = round(stars / settings.STARS_PER_USD, 4)
    link = await _bot.create_invoice_link(
        title="Поповнення балансу Лемур",
        description=f"Поповнення на ⭐{stars}",
        payload=f"stars_topup:{user.id}:{amount_usd}",
        currency="XTR",
        prices=[LabeledPrice(label="Telegram Stars", amount=stars)],
    )
    return {"invoice_url": link, "stars": stars, "amount_usd": amount_usd}


@app.post("/api/stars/buy")
async def api_stars_buy(body: StarsBuyRequest, user: User = Depends(get_current_user)):
    if body.stars < 1:
        raise HTTPException(status_code=400, detail="Invalid amount")
    price_stars = round(body.amount_usd / settings.STAR_DISPLAY_USD)
    async with AsyncSessionLocal() as s:
        async with s.begin():
            u = await s.get(User, user.id)
            if not u or u.balance_stars < price_stars:
                raise HTTPException(status_code=400, detail="Insufficient balance")
            u.balance_stars = u.balance_stars - price_stars

    if _bot and settings.ADMIN_IDS:
        uname = f"@{user.username}" if user.username else f"ID:{user.id}"
        txt = (
            f"⭐ <b>Замовлення Stars!</b>\n\n"
            f"👤 {uname} (<code>{user.id}</code>)\n"
            f"⭐ Зірок до відправки: <b>{body.stars}</b>\n"
            f"💫 Списано з балансу: <b>⭐{price_stars}</b>\n\n"
            f"<i>Відправте зірки через Fragment або бот</i>"
        )
        for admin_id in settings.ADMIN_IDS:
            try:
                await _bot.send_message(admin_id, txt, parse_mode="HTML")
            except Exception:
                pass
    try:
        if _bot:
            await _bot.send_message(
                user.id,
                f"⭐ Замовлення на <b>{body.stars} Stars</b> прийнято!\n"
                f"💰 Списано: <b>${float(amount_usd):.2f}</b>\n\n"
                f"Зірки будуть відправлені протягом 10 хвилин.",
                parse_mode="HTML"
            )
    except Exception:
        pass
    return {"ok": True}


# ─── Admin API ────────────────────────────────────────────────────────────────

def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.id not in settings.ADMIN_IDS:
        raise HTTPException(status_code=403, detail="Forbidden")
    return user


@app.get("/api/admin/stats")
async def api_admin_stats(admin: User = Depends(require_admin)):
    from math import ceil
    from datetime import date
    async with AsyncSessionLocal() as s:
        total_users   = await s.scalar(select(func.count(User.id))) or 0
        total_orders  = await s.scalar(select(func.count(Order.id))) or 0
        total_rev_usd = await s.scalar(select(func.sum(Order.price_usd))) or 0
        total_topups  = await s.scalar(select(func.sum(TopUp.amount_usd))) or 0

        today = date.today()
        new_users_today  = await s.scalar(select(func.count(User.id)).where(func.date(User.created_at) == today)) or 0
        orders_today     = await s.scalar(select(func.count(Order.id)).where(func.date(Order.created_at) == today)) or 0
        revenue_today    = await s.scalar(select(func.sum(Order.price_usd)).where(func.date(Order.created_at) == today)) or 0
        topups_today     = await s.scalar(select(func.sum(TopUp.amount_usd)).where(func.date(TopUp.created_at) == today)) or 0

        cat_rows = (await s.execute(
            select(Order.category, func.count(Order.id), func.sum(Order.price_usd))
            .group_by(Order.category)
            .order_by(func.count(Order.id).desc())
        )).all()

        total_stars_balance = await s.scalar(select(func.sum(User.balance_stars))) or 0

        from sqlalchemy import distinct
        unique_buyers      = await s.scalar(select(func.count(distinct(Order.user_id)))) or 0
        users_with_balance = await s.scalar(select(func.count(User.id)).where(User.balance_stars > 0)) or 0
        conversion_pct     = round(unique_buyers / total_users * 100, 1) if total_users else 0.0

        # avg order value
        avg_order_usd = float(total_rev_usd) / total_orders if total_orders else 0.0

    return {
        "total_users":        total_users,
        "unique_buyers":      unique_buyers,
        "users_with_balance": users_with_balance,
        "conversion_pct":     conversion_pct,
        "total_orders":       total_orders,
        "avg_order_usd":      round(avg_order_usd, 2),
        "total_revenue_usd":  float(total_rev_usd),
        "total_topups_usd":   float(total_topups),
        "total_stars_balance": total_stars_balance,
        "new_users_today":    new_users_today,
        "orders_today":       orders_today,
        "revenue_today":      float(revenue_today),
        "topups_today":       float(topups_today),
        "categories": [
            {"category": r[0] or "?", "count": r[1], "revenue_usd": float(r[2] or 0)}
            for r in cat_rows
        ],
    }


@app.get("/api/admin/users")
async def api_admin_users(
    page: int = 1, limit: int = 20, search: str = "",
    admin: User = Depends(require_admin),
):
    from math import ceil
    from sqlalchemy import or_, cast, String as SAString
    async with AsyncSessionLocal() as s:
        q = select(User).order_by(User.created_at.desc())
        if search:
            q = q.where(
                or_(
                    User.username.ilike(f"%{search}%"),
                    User.full_name.ilike(f"%{search}%"),
                    cast(User.id, SAString) == search,
                )
            )
        total = await s.scalar(select(func.count()).select_from(q.subquery())) or 0
        users = (await s.execute(q.offset((page - 1) * limit).limit(limit))).scalars().all()

        result = []
        for u in users:
            order_count = await s.scalar(select(func.count(Order.id)).where(Order.user_id == u.id)) or 0
            topup_sum   = await s.scalar(select(func.sum(TopUp.amount_usd)).where(TopUp.user_id == u.id)) or 0
            result.append({
                "id":           u.id,
                "name":         u.full_name,
                "username":     u.username,
                "balance_stars": u.balance_stars,
                "orders_count": order_count,
                "topups_usd":   float(topup_sum),
                "is_admin":     u.id in settings.ADMIN_IDS,
                "is_banned":    u.is_banned,
                "created_at":   u.created_at.isoformat(),
            })

    return {"total": total, "page": page, "pages": ceil(total / limit) if total else 1, "users": result}


@app.get("/api/admin/user/{uid}")
async def api_admin_user_detail(uid: int, admin: User = Depends(require_admin)):
    async with AsyncSessionLocal() as s:
        u = await s.get(User, uid)
        if not u:
            raise HTTPException(404, "User not found")
        orders = (await s.execute(
            select(Order).where(Order.user_id == uid).order_by(Order.created_at.desc())
        )).scalars().all()
        topups = (await s.execute(
            select(TopUp).where(TopUp.user_id == uid).order_by(TopUp.created_at.desc())
        )).scalars().all()

    return {
        "id":           u.id,
        "name":         u.full_name,
        "username":     u.username,
        "balance_stars": u.balance_stars,
        "balance_usd":  float(u.balance_usd),
        "is_banned":    u.is_banned,
        "created_at":   u.created_at.isoformat(),
        "referred_by_id": u.referred_by_id,
        "orders": [
            {
                "id":           o.id,
                "category":     o.category,
                "price_usd":    float(o.price_usd),
                "status":       o.status,
                "delivered_data": o.delivered_data,
                "created_at":   o.created_at.isoformat(),
            }
            for o in orders
        ],
        "topups": [
            {
                "id":         t.id,
                "amount_usd": float(t.amount_usd),
                "created_at": t.created_at.isoformat(),
            }
            for t in topups
        ],
    }


@app.get("/api/admin/orders")
async def api_admin_orders(page: int = 1, limit: int = 30, admin: User = Depends(require_admin)):
    from math import ceil
    async with AsyncSessionLocal() as s:
        total  = await s.scalar(select(func.count(Order.id))) or 0
        orders = (await s.execute(
            select(Order).order_by(Order.created_at.desc())
            .offset((page - 1) * limit).limit(limit)
        )).scalars().all()

        result = []
        for o in orders:
            u = await s.get(User, o.user_id)
            result.append({
                "id":        o.id,
                "user_id":   o.user_id,
                "username":  u.username if u else None,
                "user_name": u.full_name if u else "?",
                "category":  o.category,
                "price_usd": float(o.price_usd),
                "status":    o.status,
                "created_at": o.created_at.isoformat(),
            })

    return {"total": total, "page": page, "pages": ceil(total / limit) if total else 1, "orders": result}


@app.get("/api/admin/topups")
async def api_admin_topups(page: int = 1, limit: int = 30, admin: User = Depends(require_admin)):
    from math import ceil
    async with AsyncSessionLocal() as s:
        total  = await s.scalar(select(func.count(TopUp.id))) or 0
        topups = (await s.execute(
            select(TopUp).order_by(TopUp.created_at.desc())
            .offset((page - 1) * limit).limit(limit)
        )).scalars().all()

        result = []
        for t in topups:
            u = await s.get(User, t.user_id)
            result.append({
                "id":         t.id,
                "user_id":    t.user_id,
                "username":   u.username if u else None,
                "user_name":  u.full_name if u else "?",
                "amount_usd": float(t.amount_usd),
                "amount_stars": t.amount_stars if t.amount_stars else round(float(t.amount_usd) / settings.STAR_DISPLAY_USD),
                "created_at": t.created_at.isoformat(),
            })

    return {"total": total, "page": page, "pages": ceil(total / limit) if total else 1, "topups": result}


# ─── Broadcast ────────────────────────────────────────────────────────────────

_broadcast_status: dict = {"running": False, "sent": 0, "failed": 0, "total": 0, "text": ""}


async def _run_broadcast(text: str, parse_mode: str) -> None:
    global _broadcast_status
    async with AsyncSessionLocal() as s:
        user_ids = (await s.execute(
            select(User.id).where(User.is_banned == False)
        )).scalars().all()

    _broadcast_status.update(running=True, sent=0, failed=0, total=len(user_ids), text=text)

    for uid in user_ids:
        if not _bot:
            break
        try:
            await _bot.send_message(uid, text, parse_mode=parse_mode)
            _broadcast_status["sent"] += 1
        except Exception:
            _broadcast_status["failed"] += 1
        await asyncio.sleep(0.05)  # 20 msg/s

    _broadcast_status["running"] = False


class BroadcastRequest(BaseModel):
    text: str
    parse_mode: str = "HTML"


@app.post("/api/admin/broadcast")
async def api_admin_broadcast(
    body: BroadcastRequest,
    admin: User = Depends(require_admin),
):
    if _broadcast_status["running"]:
        raise HTTPException(409, "Розсилка вже виконується")
    if not body.text.strip():
        raise HTTPException(400, "Порожній текст")
    if not _bot:
        raise HTTPException(503, "Бот не запущено")

    asyncio.create_task(_run_broadcast(body.text, body.parse_mode))
    return {"ok": True, "total": 0}


@app.get("/api/admin/broadcast/status")
async def api_admin_broadcast_status(admin: User = Depends(require_admin)):
    return _broadcast_status


@app.post("/api/admin/reset-stats")
async def api_admin_reset_stats(admin: User = Depends(require_admin)):
    from sqlalchemy import delete
    from lemur_shop.db.models import FKOrder
    async with AsyncSessionLocal() as s:
        async with s.begin():
            await s.execute(delete(TopUp))
            await s.execute(delete(Order))
            await s.execute(delete(FKOrder))
            await s.execute(
                    __import__('sqlalchemy').text(
                        "UPDATE users SET balance_stars = 0, balance_usd = 0"
                    )
                )
    return {"ok": True}


import uuid as _uuid
import random as _random

_game_sessions: dict[str, dict] = {}

class GameStartRequest(BaseModel):
    bet: int = 10  # Stars to stake

class GameFinishRequest(BaseModel):
    token: str
    score: int

# Multiplier tiers: (min_score, multiplier_x10) — x10 to avoid floats
GAME_TIERS = [(2000, 50), (1000, 30), (500, 20), (200, 15)]  # descending

# ---------------------------------------------------------------------------
# House edge: ~75 % RTP (25 % margin).
# At game start the server secretly draws a max achievable score for this
# session.  The client plays a real game but effective_score = min(client, cap).
# Distribution:
#   65 % → cap 0–150   (below all tiers  → guaranteed loss)
#   17.5 % → cap 200–480  (1.5 × tier)
#   8.75 % → cap 500–950  (2 ×  tier)
#   5.25 % → cap 1000–1900 (3 ×  tier)
#   3.5  % → cap 2000–4500 (5 ×  tier)
# Expected payout = 0.175×1.5 + 0.0875×2 + 0.0525×3 + 0.035×5 ≈ 0.75
# ---------------------------------------------------------------------------
def _house_cap() -> int:
    r = _random.random()
    if r < 0.65:
        return _random.randint(0, 150)
    r -= 0.65
    if r < 0.175:
        return _random.randint(200, 480)
    r -= 0.175
    if r < 0.0875:
        return _random.randint(500, 950)
    r -= 0.0875
    if r < 0.0525:
        return _random.randint(1000, 1900)
    return _random.randint(2000, 4500)

@app.get("/api/game/status")
async def api_game_status(user: User = Depends(get_current_user)):
    from datetime import date as _date
    from lemur_shop.db.models import GamePlay
    async with AsyncSessionLocal() as s:
        free_today = await s.scalar(
            select(func.count(GamePlay.id))
            .where(GamePlay.user_id == user.id)
            .where(GamePlay.is_free == True)
            .where(func.date(GamePlay.created_at) == _date.today())
        ) or 0
    return {
        "can_play_free": free_today == 0,
        "min_bet": 10,
        "balance_stars": user.balance_stars,
    }

@app.post("/api/game/start")
async def api_game_start(body: GameStartRequest, user: User = Depends(get_current_user)):
    from datetime import date as _date
    from lemur_shop.db.models import GamePlay
    bet = max(10, min(body.bet, user.balance_stars))

    async with AsyncSessionLocal() as s:
        free_today = await s.scalar(
            select(func.count(GamePlay.id))
            .where(GamePlay.user_id == user.id)
            .where(GamePlay.is_free == True)
            .where(func.date(GamePlay.created_at) == _date.today())
        ) or 0

    is_free = free_today == 0
    # Always deduct bet upfront; free play uses 10 Stars as stake
    actual_bet = 10 if is_free else bet
    async with AsyncSessionLocal() as s:
        async with s.begin():
            u = await s.get(User, user.id)
            if not u or u.balance_stars < actual_bet:
                raise HTTPException(402, "insufficient_balance")
            u.balance_stars -= actual_bet

    token = str(_uuid.uuid4())
    _game_sessions[token] = {
        "user_id": user.id,
        "is_free": is_free,
        "bet": actual_bet,
        "created_at": datetime.now(timezone.utc),
        "cap": _house_cap(),  # server-predetermined max effective score
    }
    return {"token": token, "is_free": is_free, "bet": actual_bet}

@app.post("/api/game/finish")
async def api_game_finish(body: GameFinishRequest, user: User = Depends(get_current_user)):
    from lemur_shop.db.models import GamePlay
    session = _game_sessions.pop(body.token, None)
    if not session or session["user_id"] != user.id:
        raise HTTPException(400, "Invalid session")
    elapsed = (datetime.now(timezone.utc) - session["created_at"]).total_seconds()
    if elapsed > 600:
        raise HTTPException(400, "Session expired")

    # Cap client score: anti-cheat (5000 hard limit) + house edge cap
    raw_score = max(0, min(int(body.score), 5000))
    score = min(raw_score, session["cap"])  # house determines max outcome
    bet = session["bet"]

    # Determine multiplier (x10 internally)
    mult_x10 = 0
    for min_score, m in GAME_TIERS:
        if score >= min_score:
            mult_x10 = m
            break

    stars_won = round(bet * mult_x10 / 10) if mult_x10 else 0
    net = stars_won - bet  # can be negative (lost bet) or positive

    async with AsyncSessionLocal() as s:
        async with s.begin():
            u = await s.get(User, user.id)
            u.balance_stars = u.balance_stars + stars_won
            new_balance = u.balance_stars
            s.add(GamePlay(
                user_id=user.id,
                score=score,
                stars_earned=stars_won,
                is_free=session["is_free"],
            ))

    return {
        "score": score,
        "bet": bet,
        "multiplier": mult_x10 / 10,
        "stars_won": stars_won,
        "net": net,
        "new_balance": new_balance,
    }


@app.get("/{path:path}")
async def spa_fallback(path: str):
    static_file = os.path.join(STATIC_DIR, path)
    if os.path.isfile(static_file):
        return FileResponse(static_file)
    index = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index):
        return FileResponse(index, headers={"Cache-Control": "no-cache, no-store, must-revalidate"})
    return JSONResponse({"ok": True})
