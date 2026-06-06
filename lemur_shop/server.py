from __future__ import annotations

import asyncio
import hashlib
from datetime import datetime, timezone, timedelta
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
from lemur_shop.db.models import BioPromo, Order, ReferralPayout, TopUp, User
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
_bio_promo_task: asyncio.Task | None = None


async def _check_bio_has_promo(user_id: int) -> bool:
    """Check if user's Telegram profile (bio, first_name, last_name) contains the channel username."""
    if not _bot:
        return False
    try:
        chat = await _bot.get_chat(user_id)
        needle = settings.CHANNEL_USERNAME.lower().lstrip("@")
        # Check bio + first/last name — bio can be hidden by Telegram privacy settings,
        # but names are always public; either field counts as visible promotion.
        bio        = (chat.bio        or "").lower()
        first_name = (chat.first_name or "").lower()
        last_name  = (getattr(chat, "last_name", None) or "").lower()
        combined   = f"{bio} {first_name} {last_name}"
        found = f"@{needle}" in combined or needle in combined
        log.info(
            "bio_check user=%s needle=%s bio=%r first=%r last=%r → %s",
            user_id, needle, chat.bio, chat.first_name,
            getattr(chat, "last_name", None), found,
        )
        return found
    except Exception as e:
        log.warning("bio check failed for %s: %s", user_id, e)
        return False


async def _bio_promo_daily_checker() -> None:
    """Background task: every hour check all participants, reward once per 24h."""
    from datetime import timedelta
    await asyncio.sleep(120)  # wait for bot init
    while True:
        try:
            now = datetime.utcnow()
            cutoff_check = now - timedelta(hours=23)
            async with AsyncSessionLocal() as s:
                result = await s.execute(
                    select(BioPromo).where(
                        (BioPromo.last_check_at == None) | (BioPromo.last_check_at < cutoff_check)
                    )
                )
                promos = result.scalars().all()

            log.info("bio_promo checker: processing %d participants", len(promos))
            for promo in promos:
                try:
                    has_bio = await _check_bio_has_promo(promo.user_id)
                    reward_given = False
                    async with AsyncSessionLocal() as s:
                        p = await s.get(BioPromo, promo.user_id)
                        if not p:
                            continue
                        p.is_active = has_bio
                        p.last_check_at = now
                        if has_bio and (p.last_rewarded_at is None or (now - p.last_rewarded_at).total_seconds() >= 86400):
                            user = await s.get(User, p.user_id)
                            if user and not user.is_banned:
                                user.balance_stars += 1
                                user.balance_usd += Decimal(str(settings.STAR_DISPLAY_USD))
                                p.last_rewarded_at = now
                                p.total_rewarded += 1
                                reward_given = True
                        await s.commit()
                    if reward_given and _bot:
                        try:
                            await _bot.send_message(
                                promo.user_id,
                                "⭐ <b>+1 зірка за промо!</b>\n\nВаш профіль містить @LEMUR_SHOP — вам нараховано 1 зірку.",
                            )
                        except Exception:
                            pass
                except Exception as e:
                    log.warning("bio_promo check error for user %s: %s", promo.user_id, e)
                await asyncio.sleep(0.5)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            log.warning("bio_promo_daily_checker error: %s", e)
        await asyncio.sleep(3600)


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

    from aiogram.types import BotCommand, BotCommandScopeAllPrivateChats, BotCommandScopeChat

    _public_commands = [
        BotCommand(command="start", description="🦎 Відкрити магазин"),
    ]
    _admin_commands = _public_commands + [
        BotCommand(command="balance",  description="💰 Баланс користувача"),
        BotCommand(command="topup",    description="➕ Поповнити баланс"),
        BotCommand(command="deduct",   description="➖ Списати зірки"),
        BotCommand(command="ban",      description="🚫 Заблокувати"),
        BotCommand(command="unban",    description="✅ Розблокувати"),
        BotCommand(command="stats",    description="📊 Статистика"),
        BotCommand(command="myid",     description="🪪 Мій ID"),
    ]

    try:
        await _bot.set_my_commands(_public_commands, scope=BotCommandScopeAllPrivateChats())
        for admin_id in settings.ADMIN_IDS:
            try:
                await _bot.set_my_commands(_admin_commands, scope=BotCommandScopeChat(chat_id=admin_id))
            except Exception as e:
                log.warning("set_my_commands for admin %s failed: %s", admin_id, e)
    except Exception as e:
        log.warning("set_my_commands failed: %s", e)

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

    _bio_promo_task = asyncio.create_task(_bio_promo_daily_checker())

    log.info("🦎 Лемур бот запущено (%s)", "webhook" if use_webhook else "polling")
    yield

    if _keepalive_task:
        _keepalive_task.cancel()
        try:
            await _keepalive_task
        except asyncio.CancelledError:
            pass
    if _bio_promo_task:
        _bio_promo_task.cancel()
        try:
            await _bio_promo_task
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
        "preview_mode":  settings.PREVIEW_MODE,
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
            "category":       cat,
            "flag":           info["flag"],
            "title":          info["title"],
            "price_usd":      info["price_usd"],
            "price_stars":    round(info["price_usd"] / settings.STAR_DISPLAY_USD),
            "discount_stars": info.get("discount_stars"),
        }
        for cat, info in CATEGORIES.items()
    ]


@app.post("/api/buy")
async def api_buy(body: BuyRequest, user: User = Depends(get_current_user)):
    cat_info = CATEGORIES.get(body.category)
    if not cat_info:
        raise HTTPException(status_code=400, detail="Unknown category")

    base_price_usd = cat_info["price_usd"]
    discount_stars = cat_info.get("discount_stars")
    if discount_stars:
        shop_price_stars = discount_stars
    else:
        shop_price_stars = round(base_price_usd / settings.STAR_DISPLAY_USD)
    # price_usd завжди = реальна зірочна оплата, а не прайсова ціна
    shop_price_usd = Decimal(str(round(shop_price_stars * settings.STAR_DISPLAY_USD, 4)))

    if user.balance_stars < shop_price_stars:
        raise HTTPException(status_code=402, detail="insufficient_balance")

    # Захист від подвійного натискання: блокуємо повторне замовлення тієї ж категорії протягом 30 сек
    async with AsyncSessionLocal() as s:
        recent = await s.scalar(
            select(Order.id).where(
                Order.user_id == user.id,
                Order.category == body.category,
                Order.created_at >= datetime.utcnow() - timedelta(seconds=30),
            ).limit(1)
        )
    if recent:
        raise HTTPException(status_code=429, detail="duplicate_order")

    try:
        phone, lolz_item_id, lolz_price = await auto_buy_category(body.category)
    except (LolzApiError, ValueError, httpx.TimeoutException) as e:
        err = str(e).lower()
        if "no accounts available" in err or "no purchasable" in err:
            detail = "no_accounts"
        elif "margin too low" in err:
            detail = "service_unavailable"
        elif any(k in err for k in ("timeout", "timed out", "connection")):
            detail = "timeout"
        else:
            detail = "buy_failed"
        log.warning("auto_buy_category failed for %s: %s", body.category, e)
        raise HTTPException(status_code=502, detail=detail)

    lolz_cost = Decimal(str(round(lolz_price, 2)))

    async with AsyncSessionLocal() as s:
        async with s.begin():
            u = await s.get(User, user.id)
            bal_before = u.balance_stars
            u.balance_stars = u.balance_stars - shop_price_stars
            u.balance_usd   = u.balance_usd - shop_price_usd
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
            log.info("BUY: user=%s category=%s item=#%s price=⭐%s balance %s→%s",
                     user.id, body.category, lolz_item_id, shop_price_stars, bal_before, u.balance_stars)

    # Нотифікація адміну
    if _bot and settings.ADMIN_IDS:
        from lemur_shop.services.lolz_shop import CATEGORIES as _CATS
        cat_info = _CATS.get(body.category, {})
        profit = shop_price_usd - lolz_cost
        uname = f"@{user.username}" if user.username else f"ID:{user.id}"
        flag = cat_info.get("flag", "")
        title = cat_info.get("title", body.category.upper())
        stars_usd_val = shop_price_stars * settings.STAR_DISPLAY_USD
        txt = (
            f"🛒 <b>Нова покупка!</b>\n\n"
            f"👤 {uname} (<code>{user.id}</code>)\n"
            f"📦 {flag} Telegram {title}\n"
            f"💫 Ціна: <b>⭐{shop_price_stars}</b> (~${stars_usd_val:.2f})\n"
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

    # Нотифікація юзеру
    if _bot:
        lang = getattr(user, "lang", "ru")
        stars_usd_val = shop_price_stars * settings.STAR_DISPLAY_USD
        if lang == "ua":
            user_buy_txt = (
                f"✅ <b>Акаунт придбано!</b>\n\n"
                f"📦 {flag} Telegram {title}\n"
                f"💫 Списано: <b>⭐{shop_price_stars}</b> (~${stars_usd_val:.2f})\n"
                f"📱 Номер: <code>{phone}</code>\n\n"
                f"⬇️ Натисніть «Отримати код» у застосунку."
            )
        elif lang == "en":
            user_buy_txt = (
                f"✅ <b>Account purchased!</b>\n\n"
                f"📦 {flag} Telegram {title}\n"
                f"💫 Charged: <b>⭐{shop_price_stars}</b> (~${stars_usd_val:.2f})\n"
                f"📱 Number: <code>{phone}</code>\n\n"
                f"⬇️ Tap «Get Code» in the app."
            )
        else:
            user_buy_txt = (
                f"✅ <b>Аккаунт куплен!</b>\n\n"
                f"📦 {flag} Telegram {title}\n"
                f"💫 Списано: <b>⭐{shop_price_stars}</b> (~${stars_usd_val:.2f})\n"
                f"📱 Номер: <code>{phone}</code>\n\n"
                f"⬇️ Нажмите «Получить код» в приложении."
            )
        try:
            await _bot.send_message(user.id, user_buy_txt, parse_mode="HTML")
        except Exception:
            pass

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
    if amount < 0.1 or amount > 1000:
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
    crypto_invoice_id = str(invoice.get("invoice_id", ""))

    if status != "paid" or not raw_payload.startswith("cryptotopup:"):
        return Response(content="ok")

    try:
        _, user_id_str, amount_str = raw_payload.split(":")
        user_id = int(user_id_str)
        amount_usd = Decimal(amount_str)
    except Exception as e:
        log.error("CryptoBot bad payload %r: %s", raw_payload, e)
        return Response(content="ok")

    # Idempotency: перевіряємо по унікальному invoice_id від CryptoBot
    async with AsyncSessionLocal() as s:
        already = await s.scalar(
            select(TopUp.id).where(TopUp.charge_id == f"crypto:{crypto_invoice_id}").limit(1)
        )
    if already:
        log.warning("CryptoBot duplicate invoice_id=%s user=%s — skip", crypto_invoice_id, user_id)
        return Response(content="ok")

    async with AsyncSessionLocal() as s:
        async with s.begin():
            user = await s.get(User, user_id)
            if not user:
                log.error("CryptoBot payment for unknown user=%s", user_id)
                return Response(content="ok")
            stars_credited = round(float(amount_usd) / settings.STAR_DISPLAY_USD)
            bal_before = user.balance_stars
            user.balance_usd   = user.balance_usd + amount_usd
            user.balance_stars = user.balance_stars + stars_credited
            s.add(TopUp(
                user_id=user_id, amount_usd=amount_usd,
                amount_stars=stars_credited, admin_id=-1,
                method="crypto",
                charge_id=f"crypto:{crypto_invoice_id}",
            ))
            log.info("CryptoBot paid: invoice=%s user=%s amount=%s stars=%s balance %s→%s",
                     crypto_invoice_id, user_id, amount_usd, stars_credited, bal_before, user.balance_stars)

    if _bot:
        if settings.ADMIN_IDS:
            uname = f"@{user.username}" if user.username else f"ID:{user_id}"
            txt = (
                f"💎 <b>Поповнення через CryptoBot!</b>\n\n"
                f"👤 {uname} (<code>{user_id}</code>)\n"
                f"💰 Зараховано: <b>${float(amount_usd):.2f} USDT = ⭐{stars_credited}</b>\n"
                f"💫 Баланс: <b>⭐{user.balance_stars}</b>"
            )
            for admin_id in settings.ADMIN_IDS:
                try:
                    await _bot.send_message(admin_id, txt, parse_mode="HTML")
                except Exception:
                    pass
        try:
            await _bot.send_message(
                user_id,
                f"✅ Баланс поповнено!\n\n"
                f"💰 +${float(amount_usd):.2f} USDT = ⭐+{stars_credited}\n"
                f"💫 Новий баланс: <b>⭐{user.balance_stars}</b>",
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
            u.balance_usd   = u.balance_usd - Decimal(str(round(price_stars * settings.STAR_DISPLAY_USD, 4)))

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
                f"💫 Списано з балансу: <b>⭐{price_stars}</b>\n\n"
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


@app.get("/api/admin/check-bio")
async def api_admin_check_bio(user_id: int, admin: User = Depends(require_admin)):
    """Debug: show raw getChat response for a user to diagnose bio check issues."""
    if not _bot:
        raise HTTPException(503, "Bot not ready")
    try:
        chat = await _bot.get_chat(user_id)
        raw = chat.model_dump() if hasattr(chat, "model_dump") else vars(chat)
        needle = settings.CHANNEL_USERNAME.lower().lstrip("@")
        bio        = (chat.bio        or "").lower()
        first_name = (chat.first_name or "").lower()
        last_name  = (getattr(chat, "last_name", None) or "").lower()
        combined   = f"{bio} {first_name} {last_name}"
        return {
            "user_id":    user_id,
            "bio":        chat.bio,
            "first_name": chat.first_name,
            "last_name":  getattr(chat, "last_name", None),
            "username":   getattr(chat, "username", None),
            "needle":     needle,
            "combined":   combined.strip(),
            "found":      f"@{needle}" in combined or needle in combined,
            "raw_fields": {k: str(v) for k, v in raw.items() if v is not None},
        }
    except Exception as e:
        return {"error": str(e), "type": type(e).__name__}


@app.get("/api/admin/smm-services-raw")
async def api_admin_smm_services_raw(admin: User = Depends(require_admin)):
    """Повертає всі smmway сервіси де є слово 'реакц' або 'reaction' в назві/категорії."""
    import httpx as _httpx
    from lemur_shop.services.smm import SMM_API_URL
    r = await _httpx.AsyncClient(timeout=30).get(
        SMM_API_URL,
        params={"key": settings.SMMWAY_API_KEY, "action": "services"},
    )
    all_services = r.json()
    if not isinstance(all_services, list):
        return {"error": str(all_services)}
    keywords = ("реакц", "reaction", "react")
    filtered = [
        {
            "id": s.get("service"),
            "name": s.get("name", ""),
            "type": s.get("type", ""),
            "category": s.get("category", ""),
            "min": s.get("min"),
            "max": s.get("max"),
            "rate": s.get("rate"),
        }
        for s in all_services
        if any(k in s.get("name", "").lower() or k in str(s.get("category", "")).lower() for k in keywords)
    ]
    return filtered

@app.get("/api/admin/stats")
async def api_admin_stats(
    admin: User = Depends(require_admin),
    date_from: str | None = None,
    date_to: str | None = None,
):
    from datetime import date, datetime as dt
    from sqlalchemy import distinct

    # Parse date range
    today = date.today()
    try:
        df = dt.strptime(date_from, "%Y-%m-%d").date() if date_from else None
        dt2 = dt.strptime(date_to, "%Y-%m-%d").date() if date_to else None
    except ValueError:
        df = dt2 = None

    def order_date_filter(col):
        filters = [Order.status == "delivered"]
        if df:
            filters.append(func.date(col) >= df)
        if dt2:
            filters.append(func.date(col) <= dt2)
        return filters

    async with AsyncSessionLocal() as s:
        total_users        = await s.scalar(select(func.count(User.id))) or 0
        total_stars_balance = await s.scalar(select(func.sum(User.balance_stars))) or 0
        users_with_balance = await s.scalar(select(func.count(User.id)).where(User.balance_stars > 0)) or 0

        # Orders in selected range
        ord_filters = order_date_filter(Order.created_at)
        total_orders  = await s.scalar(select(func.count(Order.id)).where(*ord_filters)) or 0
        total_rev_usd = await s.scalar(select(func.sum(Order.price_usd)).where(*ord_filters)) or 0
        total_cost_usd = await s.scalar(select(func.sum(Order.cost_usd)).where(*ord_filters)) or 0
        unique_buyers = await s.scalar(select(func.count(distinct(Order.user_id))).where(*ord_filters)) or 0

        # Topups in selected range
        top_filters = []
        if df:
            top_filters.append(func.date(TopUp.created_at) >= df)
        if dt2:
            top_filters.append(func.date(TopUp.created_at) <= dt2)
        total_topups = await s.scalar(select(func.sum(TopUp.amount_usd)).where(*top_filters)) or 0

        # Bio promo stats
        bio_promo_total  = await s.scalar(select(func.count(BioPromo.user_id))) or 0
        bio_promo_active = await s.scalar(select(func.count(BioPromo.user_id)).where(BioPromo.is_active == True)) or 0
        bio_promo_stars  = await s.scalar(select(func.sum(BioPromo.total_rewarded))) or 0

        # Today stats (always)
        new_users_today = await s.scalar(select(func.count(User.id)).where(func.date(User.created_at) == today)) or 0
        orders_today    = await s.scalar(select(func.count(Order.id)).where(Order.status == "delivered", func.date(Order.created_at) == today)) or 0
        revenue_today   = await s.scalar(select(func.sum(Order.price_usd)).where(Order.status == "delivered", func.date(Order.created_at) == today)) or 0
        cost_today      = await s.scalar(select(func.sum(Order.cost_usd)).where(Order.status == "delivered", func.date(Order.created_at) == today)) or 0
        topups_today    = await s.scalar(select(func.sum(TopUp.amount_usd)).where(func.date(TopUp.created_at) == today)) or 0

        cat_rows = (await s.execute(
            select(
                Order.category,
                func.count(Order.id),
                func.sum(Order.price_usd),
                func.sum(Order.cost_usd),
                func.sum(Order.smm_quantity),
            )
            .where(*ord_filters)
            .group_by(Order.category)
            .order_by(func.count(Order.id).desc())
        )).all()

    ACCOUNT_CATS = {"us", "ua", "kz"}

    def _row(r) -> dict:
        rev  = float(r[2] or 0)
        cost = float(r[3] or 0)
        cat  = r[0] or "?"
        return {
            "category":    cat,
            "group":       "account" if cat in ACCOUNT_CATS else "smm",
            "count":       r[1],
            "smm_quantity": int(r[4] or 0),
            "revenue_usd": rev,
            "cost_usd":    cost,
            "profit_usd":  round(rev - cost, 2),
        }

    categories = [_row(r) for r in cat_rows]

    def _sum(rows, key): return round(sum(r[key] for r in rows), 2)

    acct_rows = [c for c in categories if c["group"] == "account"]
    smm_rows  = [c for c in categories if c["group"] == "smm"]

    conversion_pct = round(unique_buyers / total_users * 100, 1) if total_users else 0.0
    avg_order_usd  = float(total_rev_usd) / total_orders if total_orders else 0.0
    total_profit   = float(total_rev_usd) - float(total_cost_usd)
    profit_today   = float(revenue_today) - float(cost_today)

    return {
        "total_users":         total_users,
        "unique_buyers":       unique_buyers,
        "users_with_balance":  users_with_balance,
        "conversion_pct":      conversion_pct,
        "total_orders":        total_orders,
        "avg_order_usd":       round(avg_order_usd, 2),
        "total_revenue_usd":   float(total_rev_usd),
        "total_cost_usd":      float(total_cost_usd),
        "total_profit_usd":    round(total_profit, 2),
        "total_topups_usd":    float(total_topups),
        "total_stars_balance": total_stars_balance,
        "new_users_today":     new_users_today,
        "orders_today":        orders_today,
        "revenue_today":       float(revenue_today),
        "cost_today":          float(cost_today),
        "profit_today":        round(profit_today, 2),
        "topups_today":        float(topups_today),
        "bio_promo_total":     bio_promo_total,
        "bio_promo_active":    bio_promo_active,
        "bio_promo_stars":     int(bio_promo_stars),
        "categories":          categories,
        "accounts": {
            "count":        sum(c["count"] for c in acct_rows),
            "smm_quantity": 0,
            "revenue_usd":  _sum(acct_rows, "revenue_usd"),
            "cost_usd":     _sum(acct_rows, "cost_usd"),
            "profit_usd":   _sum(acct_rows, "profit_usd"),
            "rows":         acct_rows,
        },
        "smm": {
            "count":        sum(c["count"] for c in smm_rows),
            "smm_quantity": sum(c["smm_quantity"] for c in smm_rows),
            "revenue_usd":  _sum(smm_rows, "revenue_usd"),
            "cost_usd":     _sum(smm_rows, "cost_usd"),
            "profit_usd":   _sum(smm_rows, "profit_usd"),
            "rows":         smm_rows,
        },
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
    async with AsyncSessionLocal() as s:
        async with s.begin():
            await s.execute(delete(TopUp))
            await s.execute(delete(Order))
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


# ---------------------------------------------------------------------------
# Wheel of Fortune — real multiplayer lobby
#
# Players choose stake (10/25/50/100) + room size (2/5/10).
# Everyone pays same stake. Winner takes 75 % of pool; house keeps 25 %.
# Rooms auto-fill with bots after ROOM_TIMEOUT seconds.
# ---------------------------------------------------------------------------

from sqlalchemy import text as _text
from lemur_shop.db.models import WheelRoom, WheelParticipant

WHEEL_CUT    = 0.25          # house keeps 25 %
ROOM_TIMEOUT = 90            # seconds before bots fill remaining slots
VALID_STAKES = {10, 25, 50, 100}
VALID_SIZES  = {2, 5, 10}
_WLOCK       = asyncio.Lock()

_BOT_NAMES = [
    'Олексій','Марія','Дмитро','Катя','Іван','Аня','Микола','Настя',
    'Вова','Юля','Сашко','Оля','Петро','Таня','Сергій','Ліза',
    'Артем','Віка','Богдан','Соня','Андрій','Даша','Павло','Ірина',
]
_BOT_FLAGS = ['🇺🇦','🇺🇦','🇺🇦','🇷🇺','🇵🇱','🇩🇪','🇧🇾','🇰🇿']


async def _spin_room(room_id: int) -> None:
    """Select winner, credit payout, mark room done. Must be called under _WLOCK."""
    async with AsyncSessionLocal() as s:
        async with s.begin():
            room = await s.get(WheelRoom, room_id)
            if not room or room.status != 'waiting':
                return
            parts = (await s.execute(
                select(WheelParticipant).where(WheelParticipant.room_id == room_id)
            )).scalars().all()
            if not parts:
                room.status = 'done'
                return
            winner = _random.choice(parts)
            payout = round(room.stake * room.max_players * (1 - WHEEL_CUT))
            room.status         = 'done'
            room.winner_user_id = winner.user_id
            room.winner_name    = winner.name
            room.payout         = payout
            if winner.user_id:
                u = await s.get(User, winner.user_id)
                if u:
                    u.balance_stars += payout


async def _wheel_bot_filler() -> None:
    """Background task: fill stale rooms with bots every 15 s."""
    while True:
        await asyncio.sleep(15)
        try:
            cutoff = datetime.now(timezone.utc).replace(tzinfo=None)
            from datetime import timedelta
            cutoff -= timedelta(seconds=ROOM_TIMEOUT)
            async with AsyncSessionLocal() as s:
                stale = (await s.execute(
                    select(WheelRoom)
                    .where(WheelRoom.status == 'waiting')
                    .where(WheelRoom.created_at < cutoff)
                )).scalars().all()
                stale_ids = [r.id for r in stale]

            for rid in stale_ids:
                async with _WLOCK:
                    async with AsyncSessionLocal() as s:
                        room = await s.get(WheelRoom, rid)
                        if not room or room.status != 'waiting':
                            continue
                        count = (await s.scalar(
                            select(func.count(WheelParticipant.id))
                            .where(WheelParticipant.room_id == rid)
                        )) or 0
                        needed = room.max_players - count
                        if needed > 0:
                            async with s.begin():
                                for _ in range(needed):
                                    flag = _random.choice(_BOT_FLAGS)
                                    name = f"{flag} {_random.choice(_BOT_NAMES)}"
                                    s.add(WheelParticipant(
                                        room_id=rid, user_id=None,
                                        name=name, is_bot=True,
                                    ))
                    await _spin_room(rid)
        except Exception as e:
            log.warning("wheel bot filler: %s", e)


class WheelJoinRequest(BaseModel):
    stake: int
    max_players: int


def _room_view(room: WheelRoom, parts: list, my_user_id: int) -> dict:
    return {
        "id":          room.id,
        "stake":       room.stake,
        "max_players": room.max_players,
        "status":      room.status,
        "participants": [
            {"name": p.name, "is_you": p.user_id == my_user_id, "is_bot": p.is_bot}
            for p in parts
        ],
        "winner_name":  room.winner_name,
        "winner_is_you": room.winner_user_id == my_user_id if room.winner_user_id else False,
        "payout":      room.payout,
    }


@app.get("/api/wheel/lobby")
async def api_wheel_lobby(user: User = Depends(get_current_user)):
    """Return waiting count per (stake, max_players) combination."""
    async with AsyncSessionLocal() as s:
        rows = (await s.execute(
            select(
                WheelRoom.stake,
                WheelRoom.max_players,
                func.count(WheelParticipant.id).label("cnt"),
            )
            .outerjoin(WheelParticipant, WheelParticipant.room_id == WheelRoom.id)
            .where(WheelRoom.status == 'waiting')
            .group_by(WheelRoom.id, WheelRoom.stake, WheelRoom.max_players)
            .order_by(WheelRoom.stake, WheelRoom.max_players)
        )).all()

    # Best open room per (stake, size)
    best: dict[tuple, dict] = {}
    for stake, max_p, cnt in rows:
        key = (stake, max_p)
        if key not in best or cnt > best[key]["waiting"]:
            best[key] = {"waiting": int(cnt)}
    return [
        {"stake": k[0], "max_players": k[1], "waiting": v["waiting"]}
        for k, v in best.items()
    ]


@app.post("/api/wheel/join")
async def api_wheel_join(body: WheelJoinRequest, user: User = Depends(get_current_user)):
    if body.stake not in VALID_STAKES:
        raise HTTPException(400, "invalid_stake")
    if body.max_players not in VALID_SIZES:
        raise HTTPException(400, "invalid_size")

    async with _WLOCK:
        # Check user not already in an active room
        async with AsyncSessionLocal() as s:
            existing = await s.scalar(
                select(WheelParticipant.room_id)
                .join(WheelRoom, WheelRoom.id == WheelParticipant.room_id)
                .where(WheelParticipant.user_id == user.id)
                .where(WheelRoom.status == 'waiting')
            )
        if existing:
            raise HTTPException(409, "already_in_room")

        # Deduct stake
        async with AsyncSessionLocal() as s:
            async with s.begin():
                u = await s.get(User, user.id)
                if not u or u.balance_stars < body.stake:
                    raise HTTPException(402, "insufficient_balance")
                u.balance_stars -= body.stake
                display_name = (u.username and f"@{u.username}") or u.full_name or "Гравець"

        # Find open room or create one
        async with AsyncSessionLocal() as s:
            room_row = await s.scalar(
                select(WheelRoom)
                .where(WheelRoom.status == 'waiting')
                .where(WheelRoom.stake == body.stake)
                .where(WheelRoom.max_players == body.max_players)
                .order_by(WheelRoom.created_at)
            )
            if room_row:
                room_id = room_row.id
            else:
                async with s.begin():
                    new_room = WheelRoom(stake=body.stake, max_players=body.max_players)
                    s.add(new_room)
                    await s.flush()
                    room_id = new_room.id

        # Add participant
        async with AsyncSessionLocal() as s:
            async with s.begin():
                s.add(WheelParticipant(
                    room_id=room_id, user_id=user.id,
                    name=display_name, is_bot=False,
                ))

        # Check if room is now full
        async with AsyncSessionLocal() as s:
            count = (await s.scalar(
                select(func.count(WheelParticipant.id))
                .where(WheelParticipant.room_id == room_id)
            )) or 0

        if count >= body.max_players:
            await _spin_room(room_id)

    return {"room_id": room_id}


@app.get("/api/wheel/room/{room_id}")
async def api_wheel_room(room_id: int, user: User = Depends(get_current_user)):
    async with AsyncSessionLocal() as s:
        room = await s.get(WheelRoom, room_id)
        if not room:
            raise HTTPException(404, "room_not_found")
        parts = (await s.execute(
            select(WheelParticipant)
            .where(WheelParticipant.room_id == room_id)
            .order_by(WheelParticipant.joined_at)
        )).scalars().all()
    new_balance = user.balance_stars
    return {**_room_view(room, parts, user.id), "new_balance": new_balance}



@app.get("/api/bio-promo/status")
async def bio_promo_status(user: User = Depends(get_current_user)):
    async with AsyncSessionLocal() as s:
        promo = await s.get(BioPromo, user.id)
    if not promo:
        return {"joined": False, "is_active": False, "total_rewarded": 0, "hours_until_next": None}
    now = datetime.utcnow()
    hours_until_next: int | None = None
    if promo.last_rewarded_at:
        delta = 24 - (now - promo.last_rewarded_at).total_seconds() / 3600
        hours_until_next = max(0, round(delta))
    return {
        "joined": True,
        "is_active": promo.is_active,
        "total_rewarded": promo.total_rewarded,
        "last_rewarded_at": promo.last_rewarded_at.isoformat() if promo.last_rewarded_at else None,
        "hours_until_next": hours_until_next,
    }


@app.post("/api/bio-promo/check")
async def bio_promo_check(user: User = Depends(get_current_user)):
    """User-triggered check. Joins the promo if not joined, verifies bio, rewards if eligible."""
    from sqlalchemy import select as _sel
    now = datetime.utcnow()

    # Bio check happens outside the transaction (external API call)
    has_bio = await _check_bio_has_promo(user.id)

    rewarded = False
    async with AsyncSessionLocal() as s:
        async with s.begin():
            # Lock the row to prevent concurrent double-reward (background task + manual check)
            promo = (await s.execute(
                _sel(BioPromo).where(BioPromo.user_id == user.id).with_for_update()
            )).scalar_one_or_none()
            if not promo:
                promo = BioPromo(user_id=user.id)
                s.add(promo)

            promo.is_active = has_bio
            promo.last_check_at = now

            if has_bio and (promo.last_rewarded_at is None or (now - promo.last_rewarded_at).total_seconds() >= 86400):
                u = await s.get(User, user.id)
                if u and not u.is_banned:
                    u.balance_stars += 1
                    u.balance_usd += Decimal(str(settings.STAR_DISPLAY_USD))
                    promo.last_rewarded_at = now
                    promo.total_rewarded += 1
                    rewarded = True

    hours_until_next: int | None = None
    if has_bio and promo.last_rewarded_at:
        delta = 24 - (now - promo.last_rewarded_at).total_seconds() / 3600
        hours_until_next = max(0, round(delta))

    return {
        "joined": True,
        "is_active": has_bio,
        "rewarded": rewarded,
        "total_rewarded": promo.total_rewarded,
        "hours_until_next": hours_until_next,
    }


@app.get("/api/smm/services")
async def api_smm_services(user: User = Depends(get_current_user)):
    from lemur_shop.services.smm import SMM_SERVICES
    return [{"key": k, **v} for k, v in SMM_SERVICES.items()]


class SmmOrderRequest(BaseModel):
    service_key: str
    link: str
    quantity: int


BLOCKED_SMM_CHANNELS = {"lemur_shop", "LEMUR_SHOP"}


@app.post("/api/smm/order")
async def api_smm_order(body: SmmOrderRequest, user: User = Depends(get_current_user)):
    from lemur_shop.services.smm import SMM_SERVICES, SmmApiError, place_order, normalize_tg_link
    svc = SMM_SERVICES.get(body.service_key)
    if not svc:
        raise HTTPException(400, "Unknown service")
    if body.quantity < svc["min"] or body.quantity > svc["max"]:
        raise HTTPException(400, f"Quantity must be {svc['min']}–{svc['max']}")

    # Блокуємо накрутку на власний канал магазину
    # Посилання може бути t.me/LEMUR_SHOP або t.me/LEMUR_SHOP/123 (пост)
    link_lower = body.link.lower()
    if any(c.lower() in link_lower for c in BLOCKED_SMM_CHANNELS):
        raise HTTPException(400, "blocked_channel")

    price_stars = max(1, round(body.quantity / 100 * svc["price_per_100_stars"]))
    if user.balance_stars < price_stars:
        raise HTTPException(402, "insufficient_balance")

    try:
        order_id = await place_order(svc["service_id"], body.link, body.quantity, svc.get("api_type", "link"))
    except SmmApiError as e:
        log.error("smmway error for user=%s service=%s link=%r qty=%d: %s",
                  user.id, body.service_key, body.link, body.quantity, e)
        raise HTTPException(502, str(e))

    from lemur_shop.services.smm import smm_cost_usd
    price_usd_val = Decimal(str(round(price_stars * settings.STAR_DISPLAY_USD, 4)))
    cost_usd_val  = Decimal(str(smm_cost_usd(body.service_key, body.quantity)))
    async with AsyncSessionLocal() as s:
        async with s.begin():
            u = await s.get(User, user.id)
            bal_before = u.balance_stars
            u.balance_stars = u.balance_stars - price_stars
            u.balance_usd   = u.balance_usd - price_usd_val
            smm_order_rec = Order(
                user_id=user.id,
                product_id=0,
                price_usd=price_usd_val,
                cost_usd=cost_usd_val,
                category=body.service_key,
                status="delivered",
                delivered_data=str(order_id),
                smm_quantity=body.quantity,
            )
            s.add(smm_order_rec)

    log.info("SMM order #%s: user=%s service=%s qty=%d stars=-%d balance %s→%s",
             order_id, user.id, body.service_key, body.quantity, price_stars, bal_before, u.balance_stars)

    # ── Admin notification ──────────────────────────────────────────────────
    if _bot and settings.ADMIN_IDS:
        uname = f"@{user.username}" if user.username else f"ID:{user.id}"
        svc_flag = svc.get("flag", "🔥")
        svc_name = svc.get("title", body.service_key)
        stars_usd = price_stars * 0.013
        txt = (
            f"📊 <b>SMM замовлення!</b>\n\n"
            f"👤 {uname} (<code>{user.id}</code>)\n"
            f"{svc_flag} {svc_name}\n"
            f"🔢 Кількість: <b>{body.quantity}</b>\n"
            f"🔗 Посилання: <code>{body.link}</code>\n"
            f"💫 Списано: <b>⭐{price_stars}</b> (~${stars_usd:.2f})\n"
            f"🆔 smmway order: <code>{order_id}</code>"
        )
        for admin_id in settings.ADMIN_IDS:
            try:
                await _bot.send_message(admin_id, txt, parse_mode="HTML")
            except Exception:
                pass

    # ── User notification ───────────────────────────────────────────────────
    if _bot:
        lang = getattr(user, "lang", "ru")
        svc_flag = svc.get("flag", "🔥")
        if lang == "ua":
            user_txt = (
                f"{svc_flag} <b>Замовлення прийнято!</b>\n\n"
                f"🔢 Кількість: <b>{body.quantity}</b>\n"
                f"💫 Списано: <b>⭐{price_stars}</b>\n"
                f"🆔 Замовлення: <code>#{order_id}</code>\n\n"
                f"⏳ Виконання розпочнеться найближчим часом."
            )
        elif lang == "en":
            user_txt = (
                f"{svc_flag} <b>Order accepted!</b>\n\n"
                f"🔢 Quantity: <b>{body.quantity}</b>\n"
                f"💫 Charged: <b>⭐{price_stars}</b>\n"
                f"🆔 Order: <code>#{order_id}</code>\n\n"
                f"⏳ Fulfillment will start shortly."
            )
        else:
            user_txt = (
                f"{svc_flag} <b>Заказ принят!</b>\n\n"
                f"🔢 Количество: <b>{body.quantity}</b>\n"
                f"💫 Списано: <b>⭐{price_stars}</b>\n"
                f"🆔 Заказ: <code>#{order_id}</code>\n\n"
                f"⏳ Выполнение начнётся в ближайшее время."
            )
        try:
            await _bot.send_message(user.id, user_txt, parse_mode="HTML")
        except Exception:
            pass

    return {"order_id": order_id, "stars_spent": price_stars}


@app.get("/api/smm/status/{order_id}")
async def api_smm_status(order_id: int, user: User = Depends(get_current_user)):
    from lemur_shop.services.smm import get_order_status, SmmApiError
    try:
        return await get_order_status(order_id)
    except SmmApiError as e:
        raise HTTPException(502, str(e))


@app.get("/{path:path}")
async def spa_fallback(path: str):
    static_file = os.path.join(STATIC_DIR, path)
    if os.path.isfile(static_file):
        return FileResponse(static_file)
    index = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index):
        return FileResponse(index, headers={"Cache-Control": "no-cache, no-store, must-revalidate"})
    return JSONResponse({"ok": True})
