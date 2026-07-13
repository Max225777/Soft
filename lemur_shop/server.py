from __future__ import annotations

import asyncio
import base64
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
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from lemur_shop.api.lolz import LolzApiError
from lemur_shop.config import settings
from lemur_shop.db.init import create_tables
from lemur_shop.db.models import BioPromo, FortuneSpin, FortunePool, NftRental, NftUsername, Order, PartnerEarning, PartnerLink, PartnerPayout, PromoCode, PromoActivation, ReferralPayout, TopUp, User
from lemur_shop.db.session import AsyncSessionLocal
from decimal import Decimal

from lemur_shop.services.lolz_shop import CATEGORIES, auto_buy_category
from lemur_shop.utils.currency import get_rate

log = logging.getLogger(__name__)
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")

from zoneinfo import ZoneInfo
KYIV_TZ = ZoneInfo("Europe/Kyiv")


def today_start_utc() -> datetime:
    """Початок поточної доби за київським часом (UA/RU), як naive UTC datetime — для порівняння з created_at у БД."""
    start_kyiv = datetime.now(KYIV_TZ).replace(hour=0, minute=0, second=0, microsecond=0)
    return start_kyiv.astimezone(timezone.utc).replace(tzinfo=None)


def kyiv_date_bounds_utc(d) -> tuple[datetime, datetime]:
    """[start, end) для календарної дати d за київським часом, як naive UTC datetime."""
    from datetime import datetime as _dt, timedelta as _td
    start_kyiv = _dt(d.year, d.month, d.day, tzinfo=KYIV_TZ)
    start_utc = start_kyiv.astimezone(timezone.utc).replace(tzinfo=None)
    end_utc = (start_kyiv + _td(days=1)).astimezone(timezone.utc).replace(tzinfo=None)
    return start_utc, end_utc



# ─── Rate limiter (проста in-memory sliding-window, захист від DDoS/абузу API) ──
import time as _time
from collections import deque as _deque, defaultdict as _defaultdict


class _RateLimiter:
    def __init__(self) -> None:
        self._hits: dict[str, _deque] = _defaultdict(_deque)

    def allow(self, key: str, limit: int, window: float) -> bool:
        now = _time.monotonic()
        dq = self._hits[key]
        while dq and dq[0] <= now - window:
            dq.popleft()
        if len(dq) >= limit:
            return False
        dq.append(now)
        # Періодичне прибирання, щоб словник не ріс безмежно
        if len(self._hits) > 5000:
            for k in [k for k, v in self._hits.items() if not v]:
                self._hits.pop(k, None)
        return True


_rl = _RateLimiter()


def _client_ip(request: Request) -> str:
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else "?"


_API_DOCS_HTML = """<!doctype html>
<html lang="ru"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Lemur Shop — API для партнёров</title>
<style>
:root{--bg:#0a0a0f;--card:#14141c;--card2:#1c1c26;--bd:rgba(255,255,255,.09);--tx:#eef;--mut:#8a8fa3;--acc:#2e7cf6;--acc2:#2aabee;--ok:#33d07a;--warn:#f5b50a;--err:#e05656;--gold:#ffd166}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg);color:var(--tx);font:15px/1.6 -apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;padding:24px 16px 80px}
.wrap{max-width:820px;margin:0 auto}
h1{font-size:26px;font-weight:800;margin-bottom:4px}
h2{font-size:19px;font-weight:800;margin:32px 0 10px;padding-top:14px;border-top:1px solid var(--bd)}
h3{font-size:15px;font-weight:700;margin:18px 0 8px}
p{color:var(--tx);margin-bottom:10px}.mut{color:var(--mut)}
code{background:var(--card2);border:1px solid var(--bd);border-radius:6px;padding:2px 7px;font-family:'SF Mono',Consolas,monospace;font-size:13px;color:var(--gold)}
pre{background:var(--card);border:1px solid var(--bd);border-radius:12px;padding:14px 16px;overflow-x:auto;margin:10px 0}
pre code{background:none;border:none;padding:0;color:#cfe3ff;font-size:13px;line-height:1.55;white-space:pre}
.ep{display:flex;align-items:center;gap:10px;background:var(--card);border:1px solid var(--bd);border-radius:12px;padding:11px 14px;margin:12px 0 6px}
.m{font-weight:800;font-size:12px;padding:3px 9px;border-radius:7px;flex-shrink:0}
.get{background:rgba(51,208,122,.15);color:var(--ok);border:1px solid rgba(51,208,122,.3)}
.post{background:rgba(46,124,246,.15);color:#7db4ff;border:1px solid rgba(46,124,246,.3)}
.path{font-family:'SF Mono',Consolas,monospace;font-size:14px;color:var(--tx)}
table{width:100%;border-collapse:collapse;margin:10px 0;font-size:14px}
th,td{text-align:left;padding:9px 12px;border-bottom:1px solid var(--bd)}
th{color:var(--mut);font-weight:700;font-size:12px;letter-spacing:.5px;text-transform:uppercase}
td code{font-size:12px}
.note{background:rgba(245,181,10,.08);border:1px solid rgba(245,181,10,.28);border-radius:12px;padding:12px 16px;margin:14px 0;color:#ffe0a0}
.ok-note{background:rgba(46,124,246,.08);border:1px solid rgba(46,124,246,.28);border-radius:12px;padding:12px 16px;margin:14px 0;color:#bcd7ff}
.badge{display:inline-block;background:var(--card2);border:1px solid var(--bd);border-radius:20px;padding:3px 11px;font-size:12px;color:var(--mut);margin-right:6px}
a{color:var(--acc2)}
</style></head><body><div class="wrap">

<h1>🦎 Lemur Shop — API для партнёров</h1>
<p class="mut">Программная покупка Telegram-аккаунтов. Базовый URL: <code>{{BASE}}/api/v1</code></p>

<div class="note">🔑 <b>Как получить ключ:</b> откройте бота → раздел <b>«Партнёрка»</b> → блок <b>«API для разработчиков»</b> → «Сгенерировать ключ». Ключ доступен только партнёрам.</div>

<h2>Авторизация</h2>
<p>Передавайте ключ в заголовке каждого запроса — любым из двух способов:</p>
<pre><code>Authorization: Bearer lemur_xxxxxxxxxxxxxxxxxxxx
# или
X-API-Key: lemur_xxxxxxxxxxxxxxxxxxxx</code></pre>
<div class="ok-note">ℹ️ Покупки через API списывают звёзды с вашего баланса. <b>Партнёрская комиссия и реферальные бонусы на API-покупки не начисляются.</b></div>

<h2>Лимиты (защита от DDoS)</h2>
<table><tr><th>Область</th><th>Лимит</th></tr>
<tr><td>Все запросы по ключу</td><td>90 / мин</td></tr>
<tr><td>Покупка аккаунта</td><td>15 / мин</td></tr>
<tr><td>Получение кода</td><td>40 / мин</td></tr>
<tr><td>По IP-адресу</td><td>150 / мин</td></tr></table>
<p class="mut">При превышении — ответ <code>429</code> с <code>{"detail":"rate_limited"}</code>.</p>

<h2>Эндпоинты</h2>

<div class="ep"><span class="m get">GET</span><span class="path">/api/v1/categories</span></div>
<p>Список доступных стран и цен (в звёздах).</p>
<pre><code>curl -H "X-API-Key: $KEY" {{BASE}}/api/v1/categories</code></pre>

<div class="ep"><span class="m get">GET</span><span class="path">/api/v1/balance</span></div>
<p>Текущий баланс.</p>
<pre><code>{ "balance_stars": 1500, "balance_usd": 19.5 }</code></pre>

<div class="ep"><span class="m post">POST</span><span class="path">/api/v1/accounts/buy</span></div>
<p>Купить аккаунт выбранной категории. Возвращает <code>item_id</code> и номер — по <code>item_id</code> потом запрашивается код.</p>
<pre><code>curl -X POST -H "X-API-Key: $KEY" -H "Content-Type: application/json" \\
  -d '{"category":"us"}' {{BASE}}/api/v1/accounts/buy

# ответ:
{
  "ok": true,
  "order_id": 1234,
  "item_id": 987654,
  "phone": "+19412345678",
  "category": "us",
  "price_stars": 25,
  "balance_stars": 1475
}</code></pre>

<div class="ep"><span class="m post">POST</span><span class="path">/api/v1/accounts/code</span></div>
<p>Получить код входа для купленного аккаунта. Работает только если <code>item_id</code> принадлежит вашей покупке.</p>
<pre><code>curl -X POST -H "X-API-Key: $KEY" -H "Content-Type: application/json" \\
  -d '{"item_id":987654}' {{BASE}}/api/v1/accounts/code

# ответ:
{ "ok": true, "item_id": 987654, "code": "12345" }</code></pre>
<div class="note">⚠️ Если код не выдаётся (аккаунт «разлогинен» на стороне поставщика) — вернётся <code>409 session_invalid</code>. Повторите запрос позже или обратитесь в поддержку.</div>

<div class="ep"><span class="m get">GET</span><span class="path">/api/v1/orders</span></div>
<p>Последние 50 покупок, сделанных через API.</p>

<h2>Коды ошибок</h2>
<table><tr><th>HTTP</th><th>detail</th><th>Значение</th></tr>
<tr><td>401</td><td><code>missing_api_key</code></td><td>Не передан ключ</td></tr>
<tr><td>401</td><td><code>invalid_api_key</code></td><td>Ключ неверный</td></tr>
<tr><td>403</td><td><code>not_a_partner</code></td><td>Аккаунт не партнёр</td></tr>
<tr><td>402</td><td><code>insufficient_balance</code></td><td>Не хватает звёзд на балансе</td></tr>
<tr><td>400</td><td><code>unknown_category</code></td><td>Нет такой категории</td></tr>
<tr><td>502</td><td><code>no_accounts</code></td><td>Нет аккаунтов в наличии</td></tr>
<tr><td>502</td><td><code>service_unavailable</code></td><td>Поставщик временно недоступен</td></tr>
<tr><td>502</td><td><code>timeout</code></td><td>Таймаут поставщика</td></tr>
<tr><td>502</td><td><code>buy_failed</code></td><td>Покупка не удалась</td></tr>
<tr><td>404</td><td><code>account_not_found</code></td><td>item_id не принадлежит вам</td></tr>
<tr><td>409</td><td><code>session_invalid</code></td><td>Код недоступен / сессия аккаунта недействительна</td></tr>
<tr><td>429</td><td><code>rate_limited</code></td><td>Превышен лимит запросов</td></tr></table>

<p class="mut" style="margin-top:30px">Поддержка: напишите менеджеру в боте. Все суммы — в Telegram Stars (⭐).</p>
</div></body></html>"""


_bot: Bot | None = None
_dp: Dispatcher | None = None
_polling_task: asyncio.Task | None = None
_BOT_USERNAME: str = "LEMUR_SHOP_BOT"
_keepalive_task: asyncio.Task | None = None
_bio_promo_task: asyncio.Task | None = None
_bio_promo_midnight_task: asyncio.Task | None = None


import re as _re

def _normalize(text: str) -> str:
    """Strip all non-alphanumeric chars and lowercase — for fuzzy channel name matching."""
    return _re.sub(r"[^a-z0-9а-яёіїєґ]", "", text.lower())


async def _run_bio_promo_migration() -> None:
    """Add reward_tier column if it doesn't exist (idempotent)."""
    from sqlalchemy import text as _text
    async with AsyncSessionLocal() as s:
        try:
            await s.execute(_text(
                "ALTER TABLE bio_promos ADD COLUMN IF NOT EXISTS reward_tier INTEGER NOT NULL DEFAULT 1"
            ))
            await s.commit()
        except Exception as e:
            log.warning("bio_promo migration: %s", e)


async def _check_bio_tier(user_id: int) -> tuple[bool, int]:
    """Check bio and return (found: bool, tier: int).

    Tier 2 (2 stars/day) — bio contains the full promo phrase keyword + channel name.
    Tier 1 (1 star/day)  — bio contains only the channel name.
    Tier 0               — not found.

    Retries up to 3 times with 2 s delay to bypass Bot API response cache.
    """
    if not _bot:
        return False, 0
    needle      = _normalize(settings.CHANNEL_USERNAME.lstrip("@"))   # "lemurshop"
    phrase_kws  = [_normalize(kw) for kw in settings.BIO_PROMO_PHRASE_KEYWORDS]  # ["накрутка","cheap"]
    last_err: Exception | None = None
    for attempt in range(3):
        try:
            if attempt:
                await asyncio.sleep(2)
            chat = await _bot.get_chat(user_id)
            bio        = chat.bio or ""
            first_name = chat.first_name or ""
            last_name  = getattr(chat, "last_name", None) or ""
            combined_norm = _normalize(f"{bio} {first_name} {last_name}")
            found     = needle in combined_norm
            has_phrase = any(kw in combined_norm for kw in phrase_kws)
            tier      = 2 if (found and has_phrase) else (1 if found else 0)
            log.info(
                "bio_check attempt=%d user=%s needle=%r phrase_kws=%r norm=%r → found=%s tier=%d",
                attempt + 1, user_id, needle, phrase_kws, combined_norm, found, tier,
            )
            if found:
                return True, tier
        except Exception as e:
            last_err = e
            log.warning("bio check attempt=%d failed for %s: %s", attempt + 1, user_id, e)
    if last_err:
        log.warning("bio check exhausted retries for %s: %s", user_id, last_err)
    return False, 0


# Backward-compat alias used by hourly checker and check endpoint
async def _check_bio_has_promo(user_id: int) -> bool:
    found, _ = await _check_bio_tier(user_id)
    return found


def _hours_until_midnight() -> int:
    from datetime import timedelta
    now = datetime.utcnow()
    tomorrow = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return max(0, round((tomorrow - now).total_seconds() / 3600))


async def _bio_promo_hourly_checker() -> None:
    """Every hour: update is_active + reward_tier for all participants. No rewards here."""
    from datetime import timedelta
    await asyncio.sleep(120)
    while True:
        try:
            now = datetime.utcnow()
            cutoff = now - timedelta(hours=1)
            async with AsyncSessionLocal() as s:
                promos = (await s.execute(
                    select(BioPromo).where(
                        (BioPromo.last_check_at == None) | (BioPromo.last_check_at < cutoff)
                    )
                )).scalars().all()
            log.info("bio_promo hourly check: %d participants", len(promos))
            for promo in promos:
                try:
                    has_bio, tier = await _check_bio_tier(promo.user_id)
                    async with AsyncSessionLocal() as s:
                        p = await s.get(BioPromo, promo.user_id)
                        if p:
                            p.is_active = has_bio
                            p.reward_tier = tier if tier >= 2 else (2 if has_bio else p.reward_tier)
                            p.last_check_at = now
                            await s.commit()
                except Exception as e:
                    log.warning("bio_promo hourly check error user=%s: %s", promo.user_id, e)
                await asyncio.sleep(0.5)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            log.warning("bio_promo_hourly_checker error: %s", e)
        await asyncio.sleep(3600)


async def _bio_promo_midnight_rewarder() -> None:
    """Once per UTC calendar day: reward ⭐ to every user whose bio is active.
    Polls every 60 s so server restarts never miss a day (no long sleep until midnight).
    """
    from datetime import date as _date
    _last_run_date: _date | None = None
    await asyncio.sleep(90)  # wait for DB / bot to be ready
    while True:
        try:
            now = datetime.utcnow()
            today = now.date()

            if today != _last_run_date:
                today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

                async with AsyncSessionLocal() as s:
                    promos = (await s.execute(
                        select(BioPromo).where(BioPromo.is_active == True)
                    )).scalars().all()

                log.info("bio_promo daily reward: %d active participants (date=%s)", len(promos), today)

                _DAILY_REWARD_MSG = {
                    "ru": "⭐ <b>+{stars}⭐!</b>\n\nЕжедневная награда за фразу в профиле.",
                    "ua": "⭐ <b>+{stars}⭐!</b>\n\nДобова нагорода за фразу в профілі.",
                    "en": "⭐ <b>+{stars}⭐!</b>\n\nDaily reward for the phrase in your profile.",
                }

                for promo in promos:
                    user_lang = "ru"
                    try:
                        async with AsyncSessionLocal() as s:
                            async with s.begin():
                                p = (await s.execute(
                                    select(BioPromo).where(BioPromo.user_id == promo.user_id).with_for_update()
                                )).scalar_one_or_none()
                                if not p or not p.is_active:
                                    continue
                                # Skip if already rewarded today
                                if p.last_rewarded_at and p.last_rewarded_at >= today_start:
                                    continue
                                user = await s.get(User, p.user_id)
                                if not user or user.is_banned:
                                    continue
                                stars = 1  # фіксована добова нагорода — 1⭐/день
                                user.balance_stars += stars
                                user.balance_usd += Decimal(str(settings.STAR_DISPLAY_USD)) * stars
                                p.last_rewarded_at = now
                                p.total_rewarded += stars
                                user_lang = user.lang or "ru"
                        if _bot:
                            stars_given = 1
                            txt = _DAILY_REWARD_MSG.get(user_lang, _DAILY_REWARD_MSG["ua"]).format(stars=stars_given)
                            try:
                                await _bot.send_message(promo.user_id, txt, parse_mode="HTML")
                            except Exception:
                                pass
                    except Exception as e:
                        log.warning("bio_promo daily reward error user=%s: %s", promo.user_id, e)
                    await asyncio.sleep(0.3)

                _last_run_date = today
                log.info("bio_promo daily reward done for %s", today)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            log.warning("bio_promo_midnight_rewarder error: %s", e)
        await asyncio.sleep(60)  # poll every minute


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

    await _run_bio_promo_migration()
    try:
        await _revert_partner_referral_payouts()
    except Exception as e:
        log.warning("partner ref-payout revert failed: %s", e)
    try:
        await _backfill_referral_payouts()
    except Exception as e:
        log.warning("referral backfill failed: %s", e)
    _bio_promo_task = asyncio.create_task(_bio_promo_hourly_checker())
    _bio_promo_midnight_task = asyncio.create_task(_bio_promo_midnight_rewarder())

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
    if _bio_promo_midnight_task:
        _bio_promo_midnight_task.cancel()
        try:
            await _bio_promo_midnight_task
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


@app.middleware("http")
async def _asset_cache_headers(request: Request, call_next):
    """Хешовані ассети (/assets/index-XXXX.js) незмінні — кешуємо надовго,
    щоб не перекачувати бандл при кожному відкритті (важливо для слабкого
    з'єднання). index.html лишається no-cache (див. spa_fallback)."""
    response = await call_next(request)
    if request.url.path.startswith("/assets/"):
        response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
    return response


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
        # expunge щоб атрибути залишились доступні після закриття сесії
        s.expunge(user)
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.id not in settings.ADMIN_IDS:
        raise HTTPException(status_code=403, detail="Forbidden")
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
        "is_partner":    bool(user.is_partner),
        "preview_mode":  settings.PREVIEW_MODE,
        "bot_username":  _BOT_USERNAME or "",
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
            "title_ru":       info.get("title_ru", info["title"]),
            "title_ua":       info.get("title_ua", info["title"]),
            "phone_prefix":   info.get("phone_prefix", ""),
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
        log.warning("auto_buy_category failed for %s: %s (%s)", body.category, type(e).__name__, e)
        if _bot and settings.ADMIN_IDS:
            cat_label = body.category.upper()
            err_txt = (
                f"⚠️ <b>Помилка покупки акаунту!</b>\n\n"
                f"👤 Покупець: <code>{user.id}</code>"
                + (f" (@{user.username})" if user.username else "") + "\n"
                f"🌍 Категорія: <b>{cat_label}</b>\n"
                f"❌ Помилка: <code>{str(e)[:300]}</code>"
            )
            for admin_id in settings.ADMIN_IDS:
                try:
                    await _bot.send_message(admin_id, err_txt, parse_mode="HTML")
                except Exception:
                    pass
        raise HTTPException(status_code=502, detail=detail)

    lolz_cost = Decimal(str(round(lolz_price, 2)))

    async with AsyncSessionLocal() as s:
        async with s.begin():
            u = await s.get(User, user.id, with_for_update=True)
            if u.balance_stars < shop_price_stars:
                raise HTTPException(status_code=402, detail="insufficient_balance")
            bal_before = u.balance_stars
            u.balance_stars = u.balance_stars - shop_price_stars
            u.balance_usd   = max(Decimal(0), u.balance_usd - shop_price_usd)
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

    # Партнёр (пріоритет) або звичайний 25⭐ реф-бонус
    partner_cut, ref_bonus_stars = await credit_partner_or_referral(user, order_id, shop_price_usd, lolz_cost, body.category)
    ref_bonus_usd = Decimal(str(round(ref_bonus_stars * settings.STAR_DISPLAY_USD, 4)))

    # Нотифікація адміну (об'єднана: покупка + реф/партнёр + чистий прибуток)
    if _bot and settings.ADMIN_IDS:
        from lemur_shop.services.lolz_shop import CATEGORIES as _CATS
        cat_info = _CATS.get(body.category, {})
        profit = shop_price_usd - lolz_cost
        net_after = profit - partner_cut - ref_bonus_usd
        uname = f"@{user.username}" if user.username else f"ID:{user.id}"
        flag = cat_info.get("flag", "")
        title = cat_info.get("title", body.category.upper())
        stars_usd_val = shop_price_stars * settings.STAR_DISPLAY_USD
        deduction_line = ""
        if partner_cut > 0:
            # хто пригласив + скільки днів таймера лишилось у реферала
            async with AsyncSessionLocal() as _s:
                _ref = await _s.get(User, user.referred_by_id)
            p_name = (f"@{_ref.username}" if _ref and _ref.username else f"ID:{user.referred_by_id}")
            days_left = _partner_days_left(user.created_at)
            deduction_line += (
                f"🤝 <b>Партнёрская система</b>\n"
                f"   Пригласил: {p_name}\n"
                f"   Партнёру ({int(PARTNER_PCT*100)}%): <b>-${float(partner_cut):.2f}</b>\n"
                f"   ⏳ Таймер реферала: осталось {days_left} дн.\n"
            )
        if ref_bonus_stars > 0:
            deduction_line += (
                f"🎁 <b>Реферальная система</b>\n"
                f"   Реф-бонус: <b>-⭐{ref_bonus_stars}</b> (-${float(ref_bonus_usd):.2f})\n"
            )
        if deduction_line:
            deduction_line += f"💰 Чистий (після виплат): <b>${float(net_after):.2f}</b>\n"
        txt = (
            f"🛒 <b>Нова покупка!</b>\n\n"
            f"👤 {uname} (<code>{user.id}</code>)\n"
            f"📦 {flag} {title}\n"
            f"💫 Ціна: <b>⭐{shop_price_stars}</b> (~${stars_usd_val:.2f})\n"
            f"💸 Витрати: ${float(lolz_cost):.2f}\n"
            f"💰 Прибуток: <b>${float(profit):.2f}</b>\n"
            f"{deduction_line}\n"
            f"📱 Номер: <code>{phone}</code>\n"
            f"🆔 ID: <code>{lolz_item_id}</code>"
        )
        for admin_id in settings.ADMIN_IDS:
            try:
                await _bot.send_message(admin_id, txt, parse_mode="HTML")
            except Exception as e:
                log.warning("Admin notify failed for %s: %s", admin_id, e)

    # Публічний пост у канал-вітрину (соц-докз). Без прибутку/витрат — лише
    # хто, що і за скільки. Номер замаскований до перших 3 цифр.
    if _bot and settings.SELL_CHANNEL_USERNAME:
        try:
            from lemur_shop.services.lolz_shop import CATEGORIES as _CATS
            _info = _CATS.get(body.category, {})
            _flag = _info.get("flag", "📱")
            _title = _info.get("title_ru") or _info.get("title") or (body.category or "").upper()
            _buyer = f"@{user.username}" if user.username else (user.full_name or "Покупатель")
            sell_txt = (
                f"🛒 <b>Новая покупка!</b>\n\n"
                f"👤 {_buyer}\n"
                f"{_flag} <b>{_title}</b>\n"
                f"📱 <code>{_mask_phone(phone)}</code>\n"
                f"💫 Сумма: <b>⭐{shop_price_stars}</b>\n\n"
                f"@{_BOT_USERNAME}"
            )
            await _bot.send_message(settings.SELL_CHANNEL_USERNAME, sell_txt, parse_mode="HTML")
        except Exception as e:
            log.warning("Sell-channel post failed: %s", e)

    return {"order_id": order_id, "phone": phone, "created_at": created_at.isoformat()}


# ═══════════════════════════════════════════════════════════════════════════════
#  ПАРТНЁРСЬКИЙ API  (програмні покупки TG-акаунтів за API-ключем)
#  – автентифікація за ключем (Authorization: Bearer <key> або X-API-Key)
#  – rate-limiting per-key і per-IP (захист від DDoS/абузу)
#  – НЕ нараховує партнёрські комісії й реферальні бонуси
#  – кожна покупка позначається via_api=True для окремої адмін-статистики
# ═══════════════════════════════════════════════════════════════════════════════

def _gen_api_key() -> str:
    import secrets
    return "lemur_" + secrets.token_hex(20)   # 6 + 40 = 46 символів (влазить у VARCHAR(48))


async def get_api_partner(request: Request,
                          authorization: str | None = Header(None),
                          x_api_key: str | None = Header(None)) -> User:
    """Автентифікація партнёра за API-ключем + базовий захист від DDoS."""
    ip = _client_ip(request)
    # Глобальний throttle по IP — навіть до перевірки ключа (проти брутфорсу/флуду)
    if not _rl.allow(f"api_ip:{ip}", 150, 60):
        raise HTTPException(status_code=429, detail="rate_limited")

    key = x_api_key
    if not key and authorization and authorization.lower().startswith("bearer "):
        key = authorization[7:].strip()
    if not key:
        raise HTTPException(status_code=401, detail="missing_api_key")

    async with AsyncSessionLocal() as s:
        partner = (await s.execute(select(User).where(User.api_key == key))).scalar_one_or_none()
        if partner:
            s.expunge(partner)
    if not partner:
        # штраф за неправильний ключ — жорсткіший ліміт на IP
        _rl.allow(f"api_bad:{ip}", 20, 60)
        raise HTTPException(status_code=401, detail="invalid_api_key")
    if partner.is_banned:
        raise HTTPException(status_code=403, detail="banned")
    if not partner.is_partner:
        raise HTTPException(status_code=403, detail="not_a_partner")
    # Загальний ліміт по ключу
    if not _rl.allow(f"api_key:{key}", 90, 60):
        raise HTTPException(status_code=429, detail="rate_limited")
    return partner


class ApiBuyRequest(BaseModel):
    category: str


@app.get("/api/v1/categories")
async def api_v1_categories(partner: User = Depends(get_api_partner)):
    return [
        {
            "category":     cat,
            "flag":         info["flag"],
            "title":        info.get("title_ru", info["title"]),
            "phone_prefix": info.get("phone_prefix", ""),
            "price_stars":  info.get("discount_stars") or round(info["price_usd"] / settings.STAR_DISPLAY_USD),
        }
        for cat, info in CATEGORIES.items()
    ]


@app.get("/api/v1/balance")
async def api_v1_balance(partner: User = Depends(get_api_partner)):
    return {
        "balance_stars": partner.balance_stars,
        "balance_usd":   round(partner.balance_stars * settings.STAR_DISPLAY_USD, 2),
    }


@app.post("/api/v1/accounts/buy")
async def api_v1_buy(body: ApiBuyRequest, request: Request, partner: User = Depends(get_api_partner)):
    # Окремий, жорсткіший ліміт саме на покупки
    if not _rl.allow(f"api_buy:{partner.api_key}", 15, 60):
        raise HTTPException(status_code=429, detail="rate_limited")

    cat_info = CATEGORIES.get(body.category)
    if not cat_info:
        raise HTTPException(status_code=400, detail="unknown_category")

    discount_stars = cat_info.get("discount_stars")
    price_stars = discount_stars or round(cat_info["price_usd"] / settings.STAR_DISPLAY_USD)
    price_usd = Decimal(str(round(price_stars * settings.STAR_DISPLAY_USD, 4)))

    if partner.balance_stars < price_stars:
        raise HTTPException(status_code=402, detail="insufficient_balance")

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
        log.warning("API buy failed partner=%s cat=%s: %s (%s)", partner.id, body.category, type(e).__name__, e)
        raise HTTPException(status_code=502, detail=detail)

    lolz_cost = Decimal(str(round(lolz_price, 2)))
    async with AsyncSessionLocal() as s:
        async with s.begin():
            u = await s.get(User, partner.id, with_for_update=True)
            if u.balance_stars < price_stars:
                raise HTTPException(status_code=402, detail="insufficient_balance")
            bal_before = u.balance_stars
            u.balance_stars -= price_stars
            u.balance_usd = max(Decimal(0), u.balance_usd - price_usd)
            order = Order(
                user_id=partner.id, product_id=0, lolz_item_id=lolz_item_id,
                price_usd=price_usd, cost_usd=lolz_cost, category=body.category,
                status="delivered", delivered_data=phone, resend_count=0, via_api=True,
            )
            s.add(order)
            await s.flush()
            order_id = order.id
    log.info("API BUY: partner=%s cat=%s item=#%s stars=-%d balance %s→%s",
             partner.id, body.category, lolz_item_id, price_stars, bal_before, u.balance_stars)

    # НЕ нараховуємо партнёрку/рефералку для API-покупок (за вимогою)
    return {
        "ok": True,
        "order_id": order_id,
        "item_id": lolz_item_id,
        "phone": phone,
        "category": body.category,
        "price_stars": price_stars,
        "balance_stars": u.balance_stars,
    }


class ApiCodeRequest(BaseModel):
    item_id: int


@app.post("/api/v1/accounts/code")
async def api_v1_code(body: ApiCodeRequest, partner: User = Depends(get_api_partner)):
    if not _rl.allow(f"api_code:{partner.api_key}", 40, 60):
        raise HTTPException(status_code=429, detail="rate_limited")
    # Код видаємо лише якщо цей акаунт (item_id) належить замовленню партнёра
    async with AsyncSessionLocal() as s:
        order = (await s.execute(
            select(Order).where(Order.lolz_item_id == body.item_id, Order.user_id == partner.id)
            .order_by(Order.created_at.desc())
        )).scalars().first()
    if not order:
        raise HTTPException(status_code=404, detail="account_not_found")

    from lemur_shop.api.lolz import lolz as lolz_client
    try:
        code = await lolz_client.get_telegram_code(body.item_id)
    except (LolzApiError, httpx.TimeoutException) as e:
        err = str(e).lower()
        if any(k in err for k in ("timeout", "timed out", "connection")):
            raise HTTPException(status_code=502, detail="timeout")
        # lolz віддав помилку по акаунту — вважаємо сесію недійсною
        raise HTTPException(status_code=409, detail="session_invalid")
    if not code:
        # Код не видається — сесія акаунта недійсна / вхід недоступний
        raise HTTPException(status_code=409, detail="session_invalid")
    return {"ok": True, "item_id": body.item_id, "code": code}


@app.get("/api/v1/orders")
async def api_v1_orders(partner: User = Depends(get_api_partner)):
    async with AsyncSessionLocal() as s:
        rows = (await s.execute(
            select(Order).where(Order.user_id == partner.id, Order.via_api == True)
            .order_by(Order.created_at.desc()).limit(50)
        )).scalars().all()
    return [
        {
            "order_id":    o.id,
            "item_id":     o.lolz_item_id,
            "category":    o.category,
            "phone":       o.delivered_data,
            "price_stars": round(float(o.price_usd or 0) / settings.STAR_DISPLAY_USD),
            "created_at":  o.created_at.isoformat(),
        }
        for o in rows
    ]


# ─── Керування ключем із міні-аппа (Telegram-автентифікація) ───────────────────

@app.get("/api/partner/api-key")
async def api_partner_get_key(user: User = Depends(get_current_user)):
    if not (user.is_partner or user.id in settings.ADMIN_IDS):
        raise HTTPException(status_code=403, detail="not_a_partner")
    return {"api_key": user.api_key}


@app.post("/api/partner/api-key/regenerate")
async def api_partner_regen_key(user: User = Depends(get_current_user)):
    if not (user.is_partner or user.id in settings.ADMIN_IDS):
        raise HTTPException(status_code=403, detail="not_a_partner")
    new_key = _gen_api_key()
    async with AsyncSessionLocal() as s:
        async with s.begin():
            u = await s.get(User, user.id, with_for_update=True)
            u.api_key = new_key
    return {"api_key": new_key}


# ─── Окрема адмін-статистика по API-покупках ───────────────────────────────────

@app.get("/api/admin/api-stats")
async def api_admin_api_stats(admin: User = Depends(require_admin)):
    star = settings.STAR_DISPLAY_USD
    today0 = today_start_utc()
    async with AsyncSessionLocal() as s:
        total_cnt = await s.scalar(select(func.count()).where(Order.via_api == True)) or 0
        total_rev = await s.scalar(select(func.coalesce(func.sum(Order.price_usd), 0)).where(Order.via_api == True)) or 0
        total_cost = await s.scalar(select(func.coalesce(func.sum(Order.cost_usd), 0)).where(Order.via_api == True)) or 0
        today_cnt = await s.scalar(select(func.count()).where(Order.via_api == True, Order.created_at >= today0)) or 0
        today_rev = await s.scalar(select(func.coalesce(func.sum(Order.price_usd), 0)).where(Order.via_api == True, Order.created_at >= today0)) or 0
        partners_cnt = await s.scalar(select(func.count()).where(User.api_key.isnot(None))) or 0
        # ТОП партнёрів за API-покупками
        top_rows = (await s.execute(
            select(User.id, User.username, User.full_name,
                   func.count(Order.id).label("cnt"),
                   func.coalesce(func.sum(Order.price_usd), 0).label("rev"))
            .join(Order, Order.user_id == User.id)
            .where(Order.via_api == True)
            .group_by(User.id, User.username, User.full_name)
            .order_by(func.count(Order.id).desc())
            .limit(10)
        )).all()
    total_rev_f = float(total_rev)
    total_cost_f = float(total_cost)
    return {
        "total_orders":   int(total_cnt),
        "total_revenue_stars": round(total_rev_f / star),
        "total_revenue_usd":   round(total_rev_f, 2),
        "total_cost_usd":      round(total_cost_f, 2),
        "total_profit_usd":    round(total_rev_f - total_cost_f, 2),
        "today_orders":   int(today_cnt),
        "today_revenue_stars": round(float(today_rev) / star),
        "api_keys_issued": int(partners_cnt),
        "top_partners": [
            {
                "user_id": r.id,
                "name": r.username or r.full_name or f"ID {r.id}",
                "orders": int(r.cnt),
                "revenue_stars": round(float(r.rev) / star),
            }
            for r in top_rows
        ],
    }


# ─── Публічна документація партнёрського API (RU) ──────────────────────────────

@app.get("/api-docs", response_class=HTMLResponse)
async def api_docs_page(request: Request):
    base = str(request.base_url).rstrip("/")
    return HTMLResponse(_API_DOCS_HTML.replace("{{BASE}}", base))


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
         "category": o.category, "smm_quantity": o.smm_quantity,
         "created_at": o.created_at.isoformat(), "delivered_data": o.delivered_data}
        for o in orders
    ]


def _mask_phone(raw: str | None) -> str:
    """Залишає видимими перші 3 цифри номера, решту ховає під зірочками.
    '+959123456789' → '+959*********'. Плюс/код країни зберігаємо."""
    if not raw:
        return "***"
    plus = raw.strip().startswith("+")
    digits = "".join(ch for ch in raw if ch.isdigit())
    if not digits:
        return "***"
    head = digits[:3]
    stars = "*" * max(3, len(digits) - 3)
    return ("+" if plus else "") + head + stars


@app.get("/api/leaderboard")
async def api_leaderboard(user: User = Depends(get_current_user), period: str = "all"):
    async with AsyncSessionLocal() as s:
        q = (
            select(
                User.id,
                User.full_name,
                User.username,
                func.count(Order.id).label("orders_count"),
                func.sum(Order.price_usd).label("total_usd"),
            )
            .join(Order, Order.user_id == User.id)
            .where(Order.status == "delivered")
        )
        if period == "today":
            q = q.where(Order.created_at >= today_start_utc())
        rows = await s.execute(
            q.group_by(User.id, User.full_name, User.username)
            .order_by(func.sum(Order.price_usd).desc())
            .limit(20)
        )
        leaders = rows.all()
    result = []
    for i, row in enumerate(leaders):
        name = row.full_name or row.username or f"User {row.id}"
        result.append({
            "rank": i + 1,
            "name": name,
            "username": row.username,
            "orders_count": row.orders_count,
            "total_stars": round(float(row.total_usd or 0) / 0.013),
            "is_me": row.id == user.id,
        })
    return result


@app.get("/api/leaderboard/referrals")
async def api_leaderboard_referrals(user: User = Depends(get_current_user), period: str = "all"):
    async with AsyncSessionLocal() as s:
        # кількість запрошених по referrer_id
        invited_q = select(User.referred_by_id, func.count(User.id).label("invited_count")).where(User.referred_by_id.isnot(None))
        earned_q = select(ReferralPayout.referrer_id, func.sum(ReferralPayout.amount_stars).label("earned_stars"))
        if period == "today":
            today_start = today_start_utc()
            invited_q = invited_q.where(User.created_at >= today_start)
            earned_q = earned_q.where(ReferralPayout.created_at >= today_start)
        invited_sub = invited_q.group_by(User.referred_by_id).subquery()
        earned_sub = earned_q.group_by(ReferralPayout.referrer_id).subquery()
        rows = await s.execute(
            select(
                User.id, User.full_name, User.username,
                func.coalesce(invited_sub.c.invited_count, 0).label("invited_count"),
                func.coalesce(earned_sub.c.earned_stars, 0).label("earned_stars"),
            )
            .join(invited_sub, invited_sub.c.referred_by_id == User.id)
            .outerjoin(earned_sub, earned_sub.c.referrer_id == User.id)
            .order_by(func.coalesce(invited_sub.c.invited_count, 0).desc())
            .limit(20)
        )
        leaders = rows.all()
    result = []
    for i, row in enumerate(leaders):
        result.append({
            "rank": i + 1,
            "name": row.full_name or row.username or f"User {row.id}",
            "username": row.username,
            "invited_count": int(row.invited_count or 0),
            "earned_stars": int(row.earned_stars or 0),
            "is_me": row.id == user.id,
        })
    return result


class PromoRedeemRequest(BaseModel):
    code: str

@app.post("/api/promo/redeem")
async def api_promo_redeem(body: PromoRedeemRequest, user: User = Depends(get_current_user)):
    code_str = body.code.strip()
    async with AsyncSessionLocal() as s:
        async with s.begin():
            promo = await s.scalar(
                select(PromoCode).where(func.lower(PromoCode.code) == func.lower(code_str)).with_for_update()
            )
            if not promo or not promo.is_active:
                raise HTTPException(404, "promo_not_found")
            if promo.activations >= promo.max_activations:
                raise HTTPException(409, "promo_limit_reached")
            exists = await s.scalar(
                select(PromoActivation.id).where(
                    PromoActivation.code_id == promo.id,
                    PromoActivation.user_id == user.id,
                )
            )
            if exists:
                raise HTTPException(409, "promo_already_used")
            promo.activations += 1
            u = await s.get(User, user.id, with_for_update=True)
            u.balance_stars += promo.reward_stars
            s.add(PromoActivation(code_id=promo.id, user_id=user.id))
    return {"ok": True, "stars": promo.reward_stars}


class PromoCreateRequest(BaseModel):
    code: str
    reward_stars: int
    max_activations: int = 1

@app.post("/api/admin/promo/create")
async def api_admin_promo_create(body: PromoCreateRequest, admin: User = Depends(require_admin)):
    code_str = body.code.strip()
    async with AsyncSessionLocal() as s:
        async with s.begin():
            existing = await s.scalar(
                select(PromoCode).where(func.lower(PromoCode.code) == func.lower(code_str))
            )
            if existing:
                raise HTTPException(409, "code_exists")
            promo = PromoCode(
                code=code_str,
                reward_stars=body.reward_stars,
                max_activations=body.max_activations,
                created_by=admin.id,
            )
            s.add(promo)
    return {"ok": True}

@app.get("/api/admin/promo/list")
async def api_admin_promo_list(admin: User = Depends(require_admin)):
    async with AsyncSessionLocal() as s:
        rows = await s.execute(select(PromoCode).order_by(PromoCode.created_at.desc()).limit(50))
        promos = rows.scalars().all()
    return [
        {
            "id": p.id, "code": p.code, "reward_stars": p.reward_stars,
            "max_activations": p.max_activations, "activations": p.activations,
            "is_active": p.is_active, "created_at": p.created_at.isoformat(),
        }
        for p in promos
    ]

@app.get("/api/admin/promo/{promo_id}/activations")
async def api_admin_promo_activations(promo_id: int, admin: User = Depends(require_admin)):
    async with AsyncSessionLocal() as s:
        rows = (await s.execute(
            select(PromoActivation, User.full_name, User.username)
            .join(User, User.id == PromoActivation.user_id)
            .where(PromoActivation.code_id == promo_id)
            .order_by(PromoActivation.activated_at.desc())
        )).all()
    return [
        {
            "user_id":      act.user_id,
            "name":         full_name or str(act.user_id),
            "username":     username,
            "activated_at": act.activated_at.isoformat(),
        }
        for act, full_name, username in rows
    ]


@app.post("/api/admin/promo/{promo_id}/toggle")
async def api_admin_promo_toggle(promo_id: int, admin: User = Depends(require_admin)):
    async with AsyncSessionLocal() as s:
        async with s.begin():
            promo = await s.get(PromoCode, promo_id)
            if not promo:
                raise HTTPException(404, "not_found")
            promo.is_active = not promo.is_active
    return {"ok": True, "is_active": promo.is_active}


REFERRAL_BONUS_STARS = 25  # зірок за кожну покупку рефералу

# Партнёрська програма: таймер на реферала + % з ЧИСТОГО прибутку (ціна − собівартість)
# усіх його покупок TG-акаунтів у межах вікна.
PARTNER_WINDOW_DAYS = 30   # скільки днів після приєднання реферал «годує» партнёра
PARTNER_PCT = 0.40         # 40% чистого прибутку з кожної покупки TG-акка у вікні


def _partner_days_left(referred_created_at) -> int:
    """Скільки днів таймера лишилось у реферала (0 = вікно закрите)."""
    if not referred_created_at:
        return 0
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    elapsed = (now - referred_created_at).days
    return max(0, PARTNER_WINDOW_DAYS - elapsed)


async def credit_partner_or_referral(
    user: User, order_id: int, price_usd, cost_usd, category_label: str
) -> tuple[Decimal, int]:
    """Повертає (партнёрська_комісія_usd, реф_бонус_зірок).

    Якщо реферер — партнёр і таймер реферала ще активний: нараховуємо
    PARTNER_PCT (40%) чистого прибутку з кожної покупки TG-акка → (commission, 0).
    Партнёр з простроченим таймером → (0, 0). Звичайний реферер → (0, 25).
    Викликається лише з покупки TG-акаунтів (накрутка партнёрку не годує)."""
    if not user.referred_by_id:
        return Decimal("0"), 0
    async with AsyncSessionLocal() as s:
        referrer = await s.get(User, user.referred_by_id)
    is_partner = bool(referrer and referrer.is_partner and not referrer.is_banned)
    if not is_partner:
        ref_stars = await credit_referral_bonus(user, order_id, category_label)
        return Decimal("0"), ref_stars

    # Таймер реферала (від дати приєднання). Прострочено — партнёру нічого.
    if _partner_days_left(user.created_at) <= 0:
        return Decimal("0"), 0

    net = Decimal(str(price_usd)) - Decimal(str(cost_usd))
    if net < 0:
        net = Decimal("0")
    commission = Decimal("0")
    try:
        async with AsyncSessionLocal() as s:
            async with s.begin():
                if await s.scalar(select(func.count()).where(PartnerEarning.order_id == order_id)):
                    return Decimal("0"), 0
                commission = (net * Decimal(str(PARTNER_PCT))).quantize(Decimal("0.0001"))
                partner = await s.get(User, user.referred_by_id, with_for_update=True)
                partner.partner_balance_usd = (partner.partner_balance_usd or Decimal("0")) + commission
                s.add(PartnerEarning(
                    partner_id=partner.id, link_id=user.partner_link_id,
                    referred_id=user.id, order_id=order_id,
                    amount_usd=commission, net_usd=net, is_first=False,
                ))
                log.info("PARTNER EARN: partner=%s referred=%s order=%s +$%s",
                         partner.id, user.id, order_id, commission)
    except IntegrityError:
        return Decimal("0"), 0

    if _bot and commission > 0:
        try:
            days = _partner_days_left(user.created_at)
            await _bot.send_message(
                user.referred_by_id,
                f"🤝 <b>Партнёрская комиссия!</b>\n\n"
                f"💰 +${float(commission):.2f} на партнёрский баланс\n"
                f"🛍 Покупка вашего реферала\n"
                f"⏳ Таймер реферала: осталось {days} дн.",
                parse_mode="HTML",
            )
        except Exception:
            pass
    return commission, 0


async def credit_referral_bonus(user: User, order_id: int, category_label: str) -> int:
    """Реферальна виплата — 25⭐ рефереру за ПЕРШУ покупку рефералу (одноразово).
    Повертає кількість нарахованих зірок (0, якщо не платили). Сповіщення адміну
    НЕ надсилає — його формує викликач (об'єднане повідомлення з покупкою)."""
    if not user.referred_by_id:
        return 0
    paid_stars = 0
    try:
        async with AsyncSessionLocal() as s:
            async with s.begin():
                # Вже платили за цього реферала? (будь-який попередній ордер)
                already_paid = await s.scalar(
                    select(func.count()).where(ReferralPayout.referred_id == user.id)
                )
                if already_paid:
                    return 0
                referrer = await s.get(User, user.referred_by_id, with_for_update=True)
                # Партнёр ніколи не отримує реферальний бонус 25⭐ — його покупці
                # годують партнёрську комісію (PartnerEarning), а не referral_payouts.
                # Без цієї перевірки стартовий backfill дораховував партнёрам бонуси
                # за кожного їхнього покупця при кожному рестарті сервера.
                if not referrer or referrer.is_banned or referrer.is_partner:
                    return 0
                bonus_stars = REFERRAL_BONUS_STARS
                bonus_usd   = Decimal(str(round(bonus_stars * settings.STAR_DISPLAY_USD, 4)))
                referrer.balance_stars += bonus_stars
                referrer.balance_usd   += bonus_usd
                s.add(ReferralPayout(
                    referrer_id=referrer.id,
                    referred_id=user.id,
                    order_id=order_id,
                    bonus_usd=bonus_usd,
                    amount_stars=bonus_stars,
                ))
                log.info("REF PAYOUT: referrer=%s referred=%s order=%s +⭐%s",
                         referrer.id, user.id, order_id, bonus_stars)
                paid_stars = bonus_stars
                if _bot:
                    try:
                        ref_lang = referrer.lang or "ru"
                        ref_msgs = {
                            "ru": f"🛍 <b>Ваш реферал сделал покупку!</b>\n\n⭐ <b>+{bonus_stars} звёзд</b> зачислено на ваш баланс.",
                            "ua": f"🛍 <b>Ваш реферал зробив покупку!</b>\n\n⭐ <b>+{bonus_stars} зірок</b> зараховано на ваш баланс.",
                            "en": f"🛍 <b>Your referral made a purchase!</b>\n\n⭐ <b>+{bonus_stars} stars</b> added to your balance.",
                        }
                        await _bot.send_message(
                            referrer.id,
                            ref_msgs.get(ref_lang, ref_msgs["ru"]),
                            parse_mode="HTML",
                        )
                    except Exception:
                        pass
    except IntegrityError:
        pass  # race: два ордери одночасно — другий програє
    except Exception as e:
        log.warning("REF PAYOUT error order=%s: %s", order_id, e)
        if _bot and settings.ADMIN_IDS:
            for admin_id in settings.ADMIN_IDS:
                try:
                    await _bot.send_message(
                        admin_id,
                        f"⚠️ <b>Реферальна виплата НЕ пройшла!</b>\n\n"
                        f"👤 Реферал: <code>{user.id}</code>\n"
                        f"📦 Замовлення: <code>{order_id}</code>\n"
                        f"❌ Помилка: <code>{str(e)[:300]}</code>",
                        parse_mode="HTML",
                    )
                except Exception:
                    pass
    return paid_stars


async def _revert_partner_referral_payouts() -> None:
    """Одноразовий відкат: до фікса стартовий backfill помилково нараховував
    партнёрам реферальні бонуси 25⭐ за кожного їхнього покупця. Тут знаходимо
    всі referral_payouts, де реферер — партнёр, знімаємо ці зірки з балансу і
    видаляємо записи. Ідемпотентно: після першого запуску рядків не лишається,
    нові не з'являються (credit_referral_bonus виключає партнёрів)."""
    reverted: list[tuple[int, int]] = []
    async with AsyncSessionLocal() as s:
        async with s.begin():
            rows = (await s.execute(
                select(ReferralPayout)
                .join(User, User.id == ReferralPayout.referrer_id)
                .where(User.is_partner.is_(True))
            )).scalars().all()
            if not rows:
                return
            by_referrer: dict[int, list[ReferralPayout]] = {}
            for rp in rows:
                by_referrer.setdefault(rp.referrer_id, []).append(rp)
            for referrer_id, payouts in by_referrer.items():
                partner = await s.get(User, referrer_id, with_for_update=True)
                if not partner:
                    continue
                stars = sum(p.amount_stars or 0 for p in payouts)
                usd = sum((p.bonus_usd for p in payouts), Decimal("0"))
                partner.balance_stars = max(0, (partner.balance_stars or 0) - stars)
                partner.balance_usd = max(Decimal("0"), (partner.balance_usd or Decimal("0")) - usd)
                for p in payouts:
                    await s.delete(p)
                reverted.append((referrer_id, stars))
                log.info("PARTNER REF-PAYOUT REVERT: partner=%s -⭐%s (%s payouts)",
                         referrer_id, stars, len(payouts))
    if _bot and settings.ADMIN_IDS and reverted:
        text = "🧹 <b>Откат ошибочных реф-бонусов партнёрам</b>\n\n" + "\n".join(
            f"👤 Партнёр <code>{pid}</code>: <b>-⭐{stars}</b>" for pid, stars in reverted
        ) + "\n\nЭти бонусы были начислены по ошибке при рестартах сервера. Больше не повторится."
        for admin_id in settings.ADMIN_IDS:
            try:
                await _bot.send_message(admin_id, text, parse_mode="HTML")
            except Exception:
                pass


async def _backfill_referral_payouts() -> None:
    """Ідемпотентний добір: рахує бонус рефереру за вже доставлені покупки
    TG-акаунтів, якщо з якоїсь причини (збій під час самої покупки) виплата
    тоді не пройшла. Запускається при кожному старті сервера, нічого не
    зробить для тих, хто вже отримав бонус (перевірка всередині credit_referral_bonus)."""
    async with AsyncSessionLocal() as s:
        rows = (await s.execute(
            select(Order.id, Order.category, Order.created_at, User)
            .join(User, User.id == Order.user_id)
            .where(
                Order.status == "delivered",
                Order.category.in_(list(CATEGORIES.keys())),
                User.referred_by_id.isnot(None),
            )
            .order_by(Order.created_at.asc())
        )).all()
        s.expunge_all()

    first_order: dict[int, tuple[int, str]] = {}
    buyer_objs: dict[int, User] = {}
    for order_id, category, _created_at, buyer in rows:
        if buyer.id not in first_order:
            first_order[buyer.id] = (order_id, category)
            buyer_objs[buyer.id] = buyer

    for buyer_id, (order_id, category) in first_order.items():
        await credit_referral_bonus(buyer_objs[buyer_id], order_id, category)


@app.get("/api/referral")
async def api_referral(user: User = Depends(get_current_user)):
    async with AsyncSessionLocal() as s:
        # загальна статистика
        ref_count = await s.scalar(
            select(func.count()).where(User.referred_by_id == user.id)
        ) or 0
        # «Покупець» = купив TG-АКАУНТ (за накрутку реф-бонусу немає, тож і не рахуємо)
        _acc_cats = list(CATEGORIES.keys())
        buyers_count = await s.scalar(
            select(func.count(func.distinct(Order.user_id)))
            .join(User, User.id == Order.user_id)
            .where(User.referred_by_id == user.id, Order.status == "delivered",
                   Order.category.in_(_acc_cats))
        ) or 0
        earned_stars = await s.scalar(
            select(func.coalesce(func.sum(ReferralPayout.amount_stars), 0))
            .where(ReferralPayout.referrer_id == user.id)
        ) or 0

        # список рефералів з позначкою is_buyer
        refs_result = await s.execute(
            select(User).where(User.referred_by_id == user.id)
            .order_by(User.created_at.desc()).limit(100)
        )
        refs = refs_result.scalars().all()

        # id тих, хто купив хоч раз
        buyer_ids: set[int] = set()
        if refs:
            rows = await s.execute(
                select(func.distinct(Order.user_id))
                .where(Order.user_id.in_([r.id for r in refs]), Order.status == "delivered",
                       Order.category.in_(_acc_cats))
            )
            buyer_ids = {row[0] for row in rows}

        referrals_list = [
            {
                "name":     r.full_name or r.username or str(r.id),
                "username": r.username,
                "is_buyer": r.id in buyer_ids,
            }
            for r in refs
        ]

    return {
        "referral_code":   user.referral_code,
        "ref_count":       ref_count,
        "buyers_count":    buyers_count,
        "earned_stars":    int(earned_stars),
        "referrals":       referrals_list,
    }


# ─── Партнёрська програма ───────────────────────────────────────────────────────

PARTNER_MIN_WITHDRAW_USD = 1.0


async def _make_partner_code(s) -> str:
    for _ in range(15):
        code = _uuid.uuid4().hex[:8].upper()
        u = await s.scalar(select(func.count()).where(User.referral_code == code))
        l = await s.scalar(select(func.count()).where(PartnerLink.code == code))
        if not u and not l:
            return code
    raise HTTPException(500, "code gen failed")


@app.get("/api/partner")
async def api_partner(user: User = Depends(get_current_user)):
    if not user.is_partner:
        raise HTTPException(403, "not_partner")
    bot_un = _BOT_USERNAME or "bot"
    async with AsyncSessionLocal() as s:
        links = (await s.execute(
            select(PartnerLink).where(PartnerLink.partner_id == user.id).order_by(PartnerLink.created_at.asc())
        )).scalars().all()

        # статистика по кожній лінці
        link_rows = []
        for lk in links:
            invited = await s.scalar(select(func.count()).where(User.partner_link_id == lk.id)) or 0
            earned = await s.scalar(
                select(func.coalesce(func.sum(PartnerEarning.amount_usd), 0)).where(PartnerEarning.link_id == lk.id)
            ) or 0
            link_rows.append({
                "id": lk.id, "title": lk.title, "code": lk.code,
                "url": f"https://t.me/{bot_un}?start={lk.code}",
                "invited": int(invited), "earned_usd": round(float(earned), 2),
            })

        total_invited = await s.scalar(select(func.count()).where(User.referred_by_id == user.id)) or 0
        total_earned = await s.scalar(
            select(func.coalesce(func.sum(PartnerEarning.amount_usd), 0)).where(PartnerEarning.partner_id == user.id)
        ) or 0
        pending = (await s.execute(
            select(PartnerPayout).where(PartnerPayout.partner_id == user.id, PartnerPayout.status == "requested")
        )).scalars().first()

        recent = (await s.execute(
            select(PartnerEarning.amount_usd, PartnerEarning.created_at)
            .where(PartnerEarning.partner_id == user.id)
            .order_by(PartnerEarning.created_at.desc()).limit(20)
        )).all()

        # Список рефералів з заробітком і залишком таймера
        ref_users = (await s.execute(
            select(User.id, User.username, User.full_name, User.created_at)
            .where(User.referred_by_id == user.id)
        )).all()
        earned_by_ref: dict[int, float] = {}
        if ref_users:
            for rid, amt in (await s.execute(
                select(PartnerEarning.referred_id, func.sum(PartnerEarning.amount_usd))
                .where(PartnerEarning.partner_id == user.id)
                .group_by(PartnerEarning.referred_id)
            )).all():
                earned_by_ref[rid] = float(amt or 0)
        referrals = []
        for rid, uname, fname, created in ref_users:
            days_left = _partner_days_left(created)
            referrals.append({
                "name": (f"@{uname}" if uname else (fname or str(rid))),
                "earned_usd": round(earned_by_ref.get(rid, 0.0), 2),
                "days_left": days_left,
                "active": days_left > 0,
            })

    return {
        "is_partner": True,
        "balance_usd": round(float(user.partner_balance_usd or 0), 2),
        "paid_usd": round(float(user.partner_paid_usd or 0), 2),
        "total_earned_usd": round(float(total_earned), 2),
        "total_invited": int(total_invited),
        "min_withdraw_usd": PARTNER_MIN_WITHDRAW_USD,
        "pct": int(PARTNER_PCT * 100),
        "window_days": PARTNER_WINDOW_DAYS,
        "has_pending_payout": pending is not None,
        "links": link_rows,
        "referrals": referrals,
        "recent": [
            {"amount_usd": round(float(a), 2), "created_at": c.isoformat() if c else None}
            for a, c in recent
        ],
    }


class PartnerLinkCreate(BaseModel):
    title: str = ""


@app.post("/api/partner/link/create")
async def api_partner_link_create(body: PartnerLinkCreate, user: User = Depends(get_current_user)):
    if not user.is_partner:
        raise HTTPException(403, "not_partner")
    title = (body.title or "").strip()[:64]
    async with AsyncSessionLocal() as s:
        async with s.begin():
            cnt = await s.scalar(select(func.count()).where(PartnerLink.partner_id == user.id)) or 0
            if cnt >= 20:
                raise HTTPException(400, "too_many_links")
            code = await _make_partner_code(s)
            link = PartnerLink(partner_id=user.id, code=code, title=title or f"Ссылка {cnt + 1}")
            s.add(link)
            await s.flush()
            lid = link.id
    bot_un = _BOT_USERNAME or "bot"
    return {"ok": True, "id": lid, "code": code, "url": f"https://t.me/{bot_un}?start={code}"}


@app.post("/api/partner/withdraw")
async def api_partner_withdraw(user: User = Depends(get_current_user)):
    if not user.is_partner:
        raise HTTPException(403, "not_partner")
    async with AsyncSessionLocal() as s:
        async with s.begin():
            u = await s.get(User, user.id, with_for_update=True)
            bal = u.partner_balance_usd or Decimal("0")
            if float(bal) < PARTNER_MIN_WITHDRAW_USD:
                raise HTTPException(400, "below_min")
            pending = await s.scalar(select(func.count()).where(
                PartnerPayout.partner_id == user.id, PartnerPayout.status == "requested"))
            if pending:
                raise HTTPException(409, "already_requested")
            s.add(PartnerPayout(partner_id=user.id, amount_usd=bal, status="requested"))
            u.partner_balance_usd = Decimal("0")
    if _bot and settings.ADMIN_IDS:
        uname = f"@{user.username}" if user.username else f"ID:{user.id}"
        for aid in settings.ADMIN_IDS:
            try:
                await _bot.send_message(
                    aid,
                    f"💸 <b>Заявка на вывод (партнёрка)</b>\n\n"
                    f"👤 {uname} (<code>{user.id}</code>)\n"
                    f"💰 Сумма: <b>${float(bal):.2f}</b>\n\n"
                    f"Отметь выплату в админ-панели (вкладка «Партнёры»).",
                    parse_mode="HTML",
                )
            except Exception:
                pass
    return {"ok": True, "amount_usd": round(float(bal), 2)}


@app.get("/api/admin/partners")
async def api_admin_partners(admin: User = Depends(require_admin)):
    async with AsyncSessionLocal() as s:
        partners = (await s.execute(
            select(User).where(User.is_partner == True).order_by(User.partner_balance_usd.desc())
        )).scalars().all()
        rows = []
        for p in partners:
            invited = await s.scalar(select(func.count()).where(User.referred_by_id == p.id)) or 0
            earned = await s.scalar(
                select(func.coalesce(func.sum(PartnerEarning.amount_usd), 0)).where(PartnerEarning.partner_id == p.id)
            ) or 0
            pending = await s.scalar(select(func.count()).where(
                PartnerPayout.partner_id == p.id, PartnerPayout.status == "requested")) or 0
            rows.append({
                "id": p.id, "name": p.full_name or p.username or str(p.id), "username": p.username,
                "balance_usd": round(float(p.partner_balance_usd or 0), 2),
                "paid_usd": round(float(p.partner_paid_usd or 0), 2),
                "earned_usd": round(float(earned), 2),
                "invited": int(invited), "has_pending": bool(pending),
            })
        payouts = (await s.execute(
            select(PartnerPayout, User)
            .join(User, User.id == PartnerPayout.partner_id)
            .where(PartnerPayout.status == "requested")
            .order_by(PartnerPayout.created_at.asc())
        )).all()
        payout_rows = [{
            "id": po.id, "partner_id": po.partner_id,
            "name": u.full_name or u.username or str(u.id), "username": u.username,
            "amount_usd": round(float(po.amount_usd), 2),
            "created_at": po.created_at.isoformat() if po.created_at else None,
        } for po, u in payouts]
    # Лідерборд: сортуємо партнёрів за загальним заробітком
    rows.sort(key=lambda r: r["earned_usd"], reverse=True)
    return {"partners": rows, "payouts": payout_rows}


class AdminPartnerStatus(BaseModel):
    user_id: int
    is_partner: bool


@app.post("/api/admin/partner/status")
async def api_admin_partner_status(body: AdminPartnerStatus, admin: User = Depends(require_admin)):
    async with AsyncSessionLocal() as s:
        async with s.begin():
            u = await s.get(User, body.user_id, with_for_update=True)
            if not u:
                raise HTTPException(404, "user_not_found")
            u.is_partner = bool(body.is_partner)
    return {"ok": True, "user_id": body.user_id, "is_partner": bool(body.is_partner)}


class AdminPartnerAdjust(BaseModel):
    user_id: int
    amount_usd: float  # може бути від'ємним


@app.post("/api/admin/partner/adjust")
async def api_admin_partner_adjust(body: AdminPartnerAdjust, admin: User = Depends(require_admin)):
    async with AsyncSessionLocal() as s:
        async with s.begin():
            u = await s.get(User, body.user_id, with_for_update=True)
            if not u:
                raise HTTPException(404, "user_not_found")
            new_bal = (u.partner_balance_usd or Decimal("0")) + Decimal(str(round(body.amount_usd, 4)))
            if new_bal < 0:
                new_bal = Decimal("0")
            u.partner_balance_usd = new_bal
    return {"ok": True, "balance_usd": round(float(new_bal), 2)}


@app.post("/api/admin/partner/payout/{payout_id}/paid")
async def api_admin_partner_payout_paid(payout_id: int, admin: User = Depends(require_admin)):
    async with AsyncSessionLocal() as s:
        async with s.begin():
            po = await s.get(PartnerPayout, payout_id, with_for_update=True)
            if not po or po.status != "requested":
                raise HTTPException(404, "payout_not_found")
            po.status = "paid"
            po.processed_at = datetime.now(timezone.utc).replace(tzinfo=None)
            u = await s.get(User, po.partner_id, with_for_update=True)
            if u:
                u.partner_paid_usd = (u.partner_paid_usd or Decimal("0")) + po.amount_usd
            partner_id, amount = po.partner_id, po.amount_usd
    if _bot:
        try:
            await _bot.send_message(
                partner_id,
                f"✅ <b>Вывод выполнен!</b>\n\n💰 ${float(amount):.2f} отправлено.",
                parse_mode="HTML",
            )
        except Exception:
            pass
    return {"ok": True}


@app.post("/api/admin/partner/payout/{payout_id}/reject")
async def api_admin_partner_payout_reject(payout_id: int, admin: User = Depends(require_admin)):
    async with AsyncSessionLocal() as s:
        async with s.begin():
            po = await s.get(PartnerPayout, payout_id, with_for_update=True)
            if not po or po.status != "requested":
                raise HTTPException(404, "payout_not_found")
            po.status = "rejected"
            po.processed_at = datetime.now(timezone.utc).replace(tzinfo=None)
            u = await s.get(User, po.partner_id, with_for_update=True)
            if u:  # повертаємо суму на баланс
                u.partner_balance_usd = (u.partner_balance_usd or Decimal("0")) + po.amount_usd
    return {"ok": True}


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

    # Idempotency: перевірка + запис в ОДНІЙ транзакції.
    # UNIQUE constraint на charge_id гарантує exactly-once через IntegrityError.
    stars_credited = 0
    bal_before = 0
    try:
        async with AsyncSessionLocal() as s:
            async with s.begin():
                user = await s.get(User, user_id, with_for_update=True)
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
    except IntegrityError:
        log.warning("CryptoBot DUPLICATE invoice_id=%s user=%s — skip", crypto_invoice_id, user_id)
        return Response(content="ok")

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


# ─── Heleket (crypto, ex-Cryptomus) ─────────────────────────────────────────────

HELEKET_API = "https://api.heleket.com/v1"


def _heleket_sign(body_str: str) -> str:
    """md5( base64(json_body) + API_KEY ) — підпис як у Cryptomus/Heleket."""
    raw = base64.b64encode(body_str.encode()).decode() + settings.HELEKET_API_KEY
    return hashlib.md5(raw.encode()).hexdigest()


async def _heleket(method: str, payload: dict) -> dict:
    body_str = json.dumps(payload, separators=(",", ":"))
    headers = {
        "merchant": settings.HELEKET_MERCHANT_ID,
        "sign": _heleket_sign(body_str),
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient(timeout=20) as c:
        r = await c.post(f"{HELEKET_API}/{method}", content=body_str, headers=headers)
    data = r.json()
    if data.get("state") != 0:
        log.warning("Heleket API error: %s", data)
        raise HTTPException(status_code=502, detail="Heleket error")
    return data["result"]


class HeleketCreateRequest(BaseModel):
    amount_usd: float


@app.post("/api/heleket/create")
async def api_heleket_create(body: HeleketCreateRequest, user: User = Depends(get_current_user)):
    if not settings.HELEKET_MERCHANT_ID or not settings.HELEKET_API_KEY:
        raise HTTPException(status_code=503, detail="Heleket not configured")
    amount = round(body.amount_usd, 2)
    if amount < 0.1 or amount > 1000:
        raise HTTPException(status_code=400, detail="Invalid amount")

    # order_id несе user_id + суму (в центах) + нонс; парситься у вебхуку
    order_id = f"topup_{user.id}_{int(round(amount * 100))}_{_uuid.uuid4().hex[:10]}"
    callback = f"{settings.WEBAPP_URL.rstrip('/')}/api/heleket/notify"
    result = await _heleket("payment", {
        "amount": f"{amount:.2f}",
        "currency": "USD",
        "order_id": order_id,
        "url_callback": callback,
        "lifetime": 3600,
    })
    return {"url": result["url"], "uuid": result.get("uuid", "")}


@app.post("/api/heleket/notify")
async def heleket_notify(request: Request):
    raw = await request.body()
    try:
        data = json.loads(raw)
    except Exception:
        return Response(status_code=400)

    recv_sign = data.get("sign", "")
    check = {k: v for k, v in data.items() if k != "sign"}
    body_str = json.dumps(check, separators=(",", ":")).replace("/", "\\/")
    expected = _heleket_sign(body_str)
    if not hmac.compare_digest(expected, recv_sign):
        log.warning("Heleket bad signature")
        return Response(status_code=400)

    status = data.get("status", "")
    if status not in ("paid", "paid_over"):
        return Response(content="ok")

    order_id = str(data.get("order_id", ""))
    htk_uuid = str(data.get("uuid", ""))
    try:
        _, user_id_str, cents_str, _nonce = order_id.split("_", 3)
        user_id = int(user_id_str)
        amount_usd = Decimal(cents_str) / Decimal(100)
    except Exception as e:
        log.error("Heleket bad order_id %r: %s", order_id, e)
        return Response(content="ok")

    stars_credited = 0
    try:
        async with AsyncSessionLocal() as s:
            async with s.begin():
                user = await s.get(User, user_id, with_for_update=True)
                if not user:
                    log.error("Heleket payment for unknown user=%s", user_id)
                    return Response(content="ok")
                stars_credited = round(float(amount_usd) / settings.STAR_DISPLAY_USD)
                bal_before = user.balance_stars
                user.balance_usd = user.balance_usd + amount_usd
                user.balance_stars = user.balance_stars + stars_credited
                s.add(TopUp(
                    user_id=user_id, amount_usd=amount_usd,
                    amount_stars=stars_credited, admin_id=-1,
                    method="crypto",
                    charge_id=f"heleket:{htk_uuid}",
                ))
                log.info("Heleket paid: uuid=%s user=%s amount=%s stars=%s balance %s→%s",
                         htk_uuid, user_id, amount_usd, stars_credited, bal_before, user.balance_stars)
    except IntegrityError:
        log.warning("Heleket DUPLICATE uuid=%s user=%s — skip", htk_uuid, user_id)
        return Response(content="ok")

    if _bot:
        if settings.ADMIN_IDS:
            uname = f"@{user.username}" if user.username else f"ID:{user_id}"
            txt = (
                f"💎 <b>Поповнення через Heleket!</b>\n\n"
                f"👤 {uname} (<code>{user_id}</code>)\n"
                f"💰 Зараховано: <b>${float(amount_usd):.2f} = ⭐{stars_credited}</b>\n"
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
                f"💰 +${float(amount_usd):.2f} = ⭐+{stars_credited}\n"
                f"💫 Новий баланс: <b>⭐{user.balance_stars}</b>",
                parse_mode="HTML"
            )
        except Exception:
            pass

    return Response(content="ok")


# ─── Telegram Stars ───────────────────────────────────────────────────────────

# user_id → (created_at_ts, invoice_url, stars)
# Prevents duplicate invoices when user reloads page before paying
_pending_star_invoices: dict[int, tuple[float, str, int]] = {}
_INVOICE_TTL = 600  # seconds — invoice is valid 10 min, matches Telegram default


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

    import time as _time
    now = _time.monotonic()
    cached = _pending_star_invoices.get(user.id)
    if cached:
        ts, url, cached_stars = cached
        if cached_stars == stars and now - ts < _INVOICE_TTL:
            log.info("Stars invoice CACHED: user=%s stars=%s url=%s", user.id, stars, url)
            amount_usd = round(stars / settings.STARS_PER_USD, 4)
            return {"invoice_url": url, "stars": stars, "amount_usd": amount_usd}

    amount_usd = round(stars / settings.STARS_PER_USD, 4)
    link = await _bot.create_invoice_link(
        title="Поповнення балансу Лемур",
        description=f"Поповнення на ⭐{stars}",
        payload=f"stars_topup:{user.id}:{amount_usd}",
        currency="XTR",
        prices=[LabeledPrice(label="Telegram Stars", amount=stars)],
    )
    _pending_star_invoices[user.id] = (now, link, stars)
    log.info("Stars invoice CREATED: user=%s stars=%s", user.id, stars)
    return {"invoice_url": link, "stars": stars, "amount_usd": amount_usd}


@app.post("/api/stars/buy")
async def api_stars_buy(body: StarsBuyRequest, user: User = Depends(get_current_user)):
    if body.stars < 1:
        raise HTTPException(status_code=400, detail="Invalid amount")
    price_stars = round(body.amount_usd / settings.STAR_DISPLAY_USD)
    async with AsyncSessionLocal() as s:
        async with s.begin():
            u = await s.get(User, user.id, with_for_update=True)
            if not u or u.balance_stars < price_stars:
                raise HTTPException(status_code=400, detail="Insufficient balance")
            u.balance_stars = u.balance_stars - price_stars
            u.balance_usd   = max(Decimal(0), u.balance_usd - Decimal(str(round(price_stars * settings.STAR_DISPLAY_USD, 4))))

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

@app.get("/api/admin/check-bio")
async def api_admin_check_bio(user_id: int, admin: User = Depends(require_admin)):
    """Debug: show raw getChat response + normalized match result."""
    if not _bot:
        raise HTTPException(503, "Bot not ready")
    try:
        chat = await _bot.get_chat(user_id)
        raw = chat.model_dump() if hasattr(chat, "model_dump") else vars(chat)
        raw_name = settings.CHANNEL_USERNAME.lstrip("@")
        needle   = _normalize(raw_name)
        bio        = chat.bio or ""
        first_name = chat.first_name or ""
        last_name  = getattr(chat, "last_name", None) or ""
        combined_raw  = f"{bio} {first_name} {last_name}"
        combined_norm = _normalize(combined_raw)
        return {
            "user_id":      user_id,
            "bio":          bio,
            "first_name":   first_name,
            "last_name":    last_name or None,
            "username":     getattr(chat, "username", None),
            "needle":       needle,
            "combined_raw": combined_raw.strip(),
            "combined_norm":combined_norm,
            "found":        needle in combined_norm,
            "raw_fields":   {k: str(v) for k, v in raw.items() if v is not None},
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
    try:
        df = dt.strptime(date_from, "%Y-%m-%d").date() if date_from else None
        dt2 = dt.strptime(date_to, "%Y-%m-%d").date() if date_to else None
    except ValueError:
        df = dt2 = None

    # Межі діапазону за київською добою (а не UTC)
    range_start = kyiv_date_bounds_utc(df)[0] if df else None
    range_end   = kyiv_date_bounds_utc(dt2)[1] if dt2 else None

    def order_date_filter(col):
        filters = [Order.status == "delivered"]
        if range_start:
            filters.append(col >= range_start)
        if range_end:
            filters.append(col < range_end)
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
        if range_start:
            top_filters.append(TopUp.created_at >= range_start)
        if range_end:
            top_filters.append(TopUp.created_at < range_end)
        total_topups = await s.scalar(select(func.sum(TopUp.amount_usd)).where(*top_filters)) or 0

        # Bio promo stats
        bio_promo_total  = await s.scalar(select(func.count(BioPromo.user_id))) or 0
        bio_promo_active = await s.scalar(select(func.count(BioPromo.user_id)).where(BioPromo.is_active == True)) or 0
        bio_promo_stars  = await s.scalar(select(func.sum(BioPromo.total_rewarded))) or 0
        bio_promo_tier2  = await s.scalar(select(func.count(BioPromo.user_id)).where(BioPromo.is_active == True, BioPromo.reward_tier == 2)) or 0

        # Today stats (always) — доба за київським часом
        today_start = today_start_utc()
        new_users_today = await s.scalar(select(func.count(User.id)).where(User.created_at >= today_start)) or 0
        orders_today    = await s.scalar(select(func.count(Order.id)).where(Order.status == "delivered", Order.created_at >= today_start)) or 0
        revenue_today   = await s.scalar(select(func.sum(Order.price_usd)).where(Order.status == "delivered", Order.created_at >= today_start)) or 0
        cost_today      = await s.scalar(select(func.sum(Order.cost_usd)).where(Order.status == "delivered", Order.created_at >= today_start)) or 0
        topups_today    = await s.scalar(select(func.sum(TopUp.amount_usd)).where(TopUp.created_at >= today_start)) or 0

        # Партнёрські комісії (зменшують чистий прибуток)
        pe_filters = []
        if range_start:
            pe_filters.append(PartnerEarning.created_at >= range_start)
        if range_end:
            pe_filters.append(PartnerEarning.created_at < range_end)
        partner_cost_range = await s.scalar(select(func.coalesce(func.sum(PartnerEarning.amount_usd), 0)).where(*pe_filters)) or 0
        partner_cost_today = await s.scalar(select(func.coalesce(func.sum(PartnerEarning.amount_usd), 0)).where(PartnerEarning.created_at >= today_start)) or 0

        # Реферальні виплати (25⭐ бонуси) також зменшують чистий прибуток
        rp_filters = []
        if range_start:
            rp_filters.append(ReferralPayout.created_at >= range_start)
        if range_end:
            rp_filters.append(ReferralPayout.created_at < range_end)
        ref_cost_range = await s.scalar(select(func.coalesce(func.sum(ReferralPayout.bonus_usd), 0)).where(*rp_filters)) or 0
        ref_cost_today = await s.scalar(select(func.coalesce(func.sum(ReferralPayout.bonus_usd), 0)).where(ReferralPayout.created_at >= today_start)) or 0

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

    ACCOUNT_CATS = {"us", "ua", "kz", "de", "mm", "co"}

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
    total_profit   = float(total_rev_usd) - float(total_cost_usd) - float(partner_cost_range) - float(ref_cost_range)
    profit_today   = float(revenue_today) - float(cost_today) - float(partner_cost_today) - float(ref_cost_today)

    return {
        "total_users":         total_users,
        "unique_buyers":       unique_buyers,
        "users_with_balance":  users_with_balance,
        "conversion_pct":      conversion_pct,
        "total_orders":        total_orders,
        "avg_order_usd":       round(avg_order_usd, 2),
        "total_revenue_usd":   float(total_rev_usd),
        "total_cost_usd":      float(total_cost_usd),
        "partner_cost_usd":    round(float(partner_cost_range), 2),
        "referral_cost_usd":   round(float(ref_cost_range), 2),
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
        "bio_promo_tier2":     int(bio_promo_tier2),
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


@app.get("/api/admin/recent-purchases")
async def api_admin_recent_purchases(admin: User = Depends(require_admin), limit: int = 25):
    """Останні покупки TG-акаунтів з чистим прибутком (після собівартості та
    реф/партнёрських виплат по кожному замовленню)."""
    limit = max(1, min(limit, 100))
    acc_cats = list(CATEGORIES.keys())
    async with AsyncSessionLocal() as s:
        rows = (await s.execute(
            select(Order.id, Order.user_id, Order.category, Order.price_usd, Order.cost_usd,
                   Order.created_at, User.username, User.full_name)
            .join(User, User.id == Order.user_id)
            .where(Order.status == "delivered", Order.category.in_(acc_cats))
            .order_by(Order.created_at.desc()).limit(limit)
        )).all()
        oids = [r.id for r in rows]
        ref_map: dict[int, float] = {}
        part_map: dict[int, float] = {}
        if oids:
            for oid, amt in (await s.execute(
                select(ReferralPayout.order_id, ReferralPayout.bonus_usd).where(ReferralPayout.order_id.in_(oids))
            )).all():
                ref_map[oid] = float(amt or 0)
            for oid, amt in (await s.execute(
                select(PartnerEarning.order_id, PartnerEarning.amount_usd).where(PartnerEarning.order_id.in_(oids))
            )).all():
                part_map[oid] = float(amt or 0)
    from lemur_shop.services.lolz_shop import CATEGORIES as _CATS
    out = []
    for r in rows:
        price = float(r.price_usd or 0)
        cost = float(r.cost_usd or 0)
        ref = ref_map.get(r.id, 0.0)
        part = part_map.get(r.id, 0.0)
        cat_info = _CATS.get(r.category, {})
        out.append({
            "id": r.id,
            "user": ("@" + r.username) if r.username else (r.full_name or str(r.user_id)),
            "category": r.category,
            "flag": cat_info.get("flag", ""),
            "price_usd": round(price, 2),
            "cost_usd": round(cost, 2),
            "ref_usd": round(ref, 2),
            "partner_usd": round(part, 2),
            "net_usd": round(price - cost - ref - part, 2),
            "created_at": r.created_at.isoformat() if r.created_at else None,
        })
    return out


@app.get("/api/admin/earnings-chart")
async def api_admin_earnings_chart(
    admin: User = Depends(require_admin),
    date_from: str | None = None,
    date_to: str | None = None,
):
    """Графік заробітку по днях (за київською добою): поповнення по методах
    (зірки/крипта/вручну адміном) + прибуток з продажів за той самий день.
    Метод 'admin' часто означає роздачі/оплату за рекламу, а не реальний
    дохід — фронтенд дозволяє вимикати його з підсумкової суми."""
    from datetime import date as _date, datetime as dt, timedelta as _td

    try:
        df = dt.strptime(date_from, "%Y-%m-%d").date() if date_from else None
        dt2 = dt.strptime(date_to, "%Y-%m-%d").date() if date_to else None
    except ValueError:
        df = dt2 = None

    if not df and not dt2:
        dt2 = datetime.now(KYIV_TZ).date()
        df = dt2 - _td(days=29)
    elif df and not dt2:
        dt2 = df
    elif dt2 and not df:
        df = dt2

    if df > dt2:
        df, dt2 = dt2, df
    # Захист від занадто широкого діапазону
    if (dt2 - df).days > 365:
        df = dt2 - _td(days=365)

    range_start = kyiv_date_bounds_utc(df)[0]
    range_end   = kyiv_date_bounds_utc(dt2)[1]

    days: list[_date] = []
    d = df
    while d <= dt2:
        days.append(d)
        d += _td(days=1)

    def _day_of(ts: datetime) -> _date:
        return ts.replace(tzinfo=timezone.utc).astimezone(KYIV_TZ).date()

    async with AsyncSessionLocal() as s:
        topup_rows = (await s.execute(
            select(TopUp.created_at, TopUp.method, TopUp.amount_usd, TopUp.amount_stars)
            .where(TopUp.created_at >= range_start, TopUp.created_at < range_end)
        )).all()
        order_rows = (await s.execute(
            select(Order.created_at, Order.price_usd, Order.cost_usd)
            .where(Order.status == "delivered", Order.created_at >= range_start, Order.created_at < range_end)
        )).all()

    buckets: dict[_date, dict] = {
        d: {"stars_usd": 0.0, "stars_count": 0, "crypto_usd": 0.0, "crypto_count": 0,
            "admin_usd": 0.0, "admin_count": 0, "revenue_usd": 0.0, "cost_usd": 0.0}
        for d in days
    }
    for created_at, method, amount_usd, _amount_stars in topup_rows:
        b = buckets.get(_day_of(created_at))
        if b is None:
            continue
        key = method if method in ("stars", "crypto", "admin") else "admin"
        b[f"{key}_usd"] += float(amount_usd or 0)
        b[f"{key}_count"] += 1
    for created_at, price_usd, cost_usd in order_rows:
        b = buckets.get(_day_of(created_at))
        if b is None:
            continue
        b["revenue_usd"] += float(price_usd or 0)
        b["cost_usd"] += float(cost_usd or 0)

    rows = []
    for d in days:
        b = buckets[d]
        total_usd = b["stars_usd"] + b["crypto_usd"] + b["admin_usd"]
        rows.append({
            "date":          d.isoformat(),
            "stars_usd":     round(b["stars_usd"], 2),
            "stars_count":   b["stars_count"],
            "crypto_usd":    round(b["crypto_usd"], 2),
            "crypto_count":  b["crypto_count"],
            "admin_usd":     round(b["admin_usd"], 2),
            "admin_count":   b["admin_count"],
            "total_usd":     round(total_usd, 2),
            "revenue_usd":   round(b["revenue_usd"], 2),
            "cost_usd":      round(b["cost_usd"], 2),
            "profit_usd":    round(b["revenue_usd"] - b["cost_usd"], 2),
        })

    return {
        "date_from": df.isoformat(),
        "date_to":   dt2.isoformat(),
        "days":      rows,
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

    # ── основний список ──────────────────────────────────────────────────────
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
                "id":           t.id,
                "user_id":      t.user_id,
                "username":     u.username if u else None,
                "user_name":    u.full_name if u else "?",
                "amount_usd":   float(t.amount_usd),
                "amount_stars": t.amount_stars if t.amount_stars else round(float(t.amount_usd) / settings.STAR_DISPLAY_USD),
                "method":       t.method or "admin",
                "charge_id":    t.charge_id,
                "admin_id":     t.admin_id,
                "created_at":   t.created_at.isoformat(),
            })

    # ── статистика (окрема сесія, щоб помилка не ламала список) ─────────────
    method_stats: dict = {}
    total_stars = 0
    total_usd   = 0.0
    promo_stats: dict = {"count": 0, "stars": 0}
    try:
        async with AsyncSessionLocal() as s:
            method_rows = (await s.execute(
                select(
                    TopUp.method,
                    func.count(TopUp.id).label('cnt'),
                    func.coalesce(func.sum(TopUp.amount_stars), 0).label('stars'),
                    func.coalesce(func.sum(TopUp.amount_usd), 0).label('usd'),
                ).group_by(TopUp.method)
            )).all()
            for r in method_rows:
                key = r.method or 'admin'
                existing = method_stats.get(key, {"count": 0, "stars": 0, "usd": 0.0})
                method_stats[key] = {
                    "count": existing["count"] + int(r.cnt),
                    "stars": existing["stars"] + int(r.stars or 0),
                    "usd":   existing["usd"]   + float(r.usd or 0),
                }
            total_stars = sum(v["stars"] for v in method_stats.values())
            total_usd   = sum(v["usd"]   for v in method_stats.values())

            promo_row = (await s.execute(
                select(
                    func.count(PromoActivation.id).label('cnt'),
                    func.coalesce(func.sum(PromoCode.reward_stars), 0).label('stars'),
                ).select_from(PromoActivation)
                .join(PromoCode, PromoCode.id == PromoActivation.code_id)
            )).one()
            promo_stats = {
                "count": int(promo_row.cnt or 0),
                "stars": int(promo_row.stars or 0),
            }
    except Exception as e:
        import traceback
        log.warning("topup stats query failed: %s\n%s", e, traceback.format_exc())

    return {
        "total": total, "page": page, "pages": ceil(total / limit) if total else 1,
        "topups": result,
        "stats": {
            "by_method":   method_stats,
            "total_stars": total_stars,
            "total_usd":   round(total_usd, 2),
            "promo":       promo_stats,
        },
    }


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


@app.get("/api/admin/referrals")
async def api_admin_referrals(admin: User = Depends(require_admin)):
    async with AsyncSessionLocal() as s:
        today_start = today_start_utc()

        # Запрошені сьогодні (referred_by_id IS NOT NULL і created_at >= сьогодні)
        invited_today = await s.scalar(
            select(func.count()).where(
                User.referred_by_id.isnot(None),
                User.created_at >= today_start,
            )
        ) or 0

        # Всього запрошених через реф
        invited_total = await s.scalar(
            select(func.count()).where(User.referred_by_id.isnot(None))
        ) or 0

        # Статистика виплат реферальних нагород
        payouts_total_count = await s.scalar(select(func.count(ReferralPayout.id))) or 0
        payouts_total_stars = await s.scalar(
            select(func.coalesce(func.sum(ReferralPayout.amount_stars), 0))
        ) or 0
        payouts_today_count = await s.scalar(
            select(func.count(ReferralPayout.id)).where(ReferralPayout.created_at >= today_start)
        ) or 0
        payouts_today_stars = await s.scalar(
            select(func.coalesce(func.sum(ReferralPayout.amount_stars), 0))
            .where(ReferralPayout.created_at >= today_start)
        ) or 0

        # Топ реферерів: хто скільки запросив + скільки з них купили
        rows = await s.execute(
            select(
                User.referred_by_id,
                func.count(User.id).label("invited"),
            )
            .where(User.referred_by_id.isnot(None))
            .group_by(User.referred_by_id)
            .order_by(func.count(User.id).desc())
            .limit(50)
        )
        referrer_rows = rows.all()

        if not referrer_rows:
            return {
                "invited_today": invited_today, "invited_total": invited_total, "referrers": [],
                "payouts": {
                    "total_count": payouts_total_count, "total_stars": int(payouts_total_stars),
                    "today_count": payouts_today_count, "today_stars": int(payouts_today_stars),
                },
            }

        referrer_ids = [r.referred_by_id for r in referrer_rows]

        # Дані рефереров
        referrers_data = (await s.execute(
            select(User.id, User.full_name, User.username).where(User.id.in_(referrer_ids))
        )).all()
        referrer_map = {r.id: r for r in referrers_data}

        # Зароблені зірки кожним
        earned_rows = (await s.execute(
            select(ReferralPayout.referrer_id, func.sum(ReferralPayout.amount_stars).label("stars"))
            .where(ReferralPayout.referrer_id.in_(referrer_ids))
            .group_by(ReferralPayout.referrer_id)
        )).all()
        earned_map = {r.referrer_id: int(r.stars) for r in earned_rows}

        # Кількість покупців серед запрошених кожного
        buyers_rows = (await s.execute(
            select(User.referred_by_id, func.count(func.distinct(Order.user_id)).label("buyers"))
            .join(Order, Order.user_id == User.id)
            .where(User.referred_by_id.in_(referrer_ids), Order.status == "delivered")
            .group_by(User.referred_by_id)
        )).all()
        buyers_map = {r.referred_by_id: r.buyers for r in buyers_rows}

        result = []
        for row in referrer_rows:
            rid = row.referred_by_id
            ref = referrer_map.get(rid)
            result.append({
                "id":       rid,
                "name":     (ref.full_name or ref.username or str(rid)) if ref else str(rid),
                "username": ref.username if ref else None,
                "invited":  row.invited,
                "buyers":   buyers_map.get(rid, 0),
                "earned_stars": earned_map.get(rid, 0),
            })

    return {
        "invited_today": invited_today, "invited_total": invited_total, "referrers": result,
        "payouts": {
            "total_count": payouts_total_count, "total_stars": int(payouts_total_stars),
            "today_count": payouts_today_count, "today_stars": int(payouts_today_stars),
        },
    }


@app.get("/api/admin/referrals/{referrer_id}/invited")
async def api_admin_referral_invited(referrer_id: int, admin: User = Depends(require_admin)):
    async with AsyncSessionLocal() as s:
        rows = (await s.execute(
            select(User.id, User.full_name, User.username, User.created_at)
            .where(User.referred_by_id == referrer_id)
            .order_by(User.created_at.desc())
        )).all()
        if not rows:
            return []

        invited_ids = [r.id for r in rows]
        buyer_rows = (await s.execute(
            select(Order.user_id).distinct()
            .where(Order.user_id.in_(invited_ids), Order.status == "delivered",
                   Order.category.in_(list(CATEGORIES.keys())))
        )).all()
        buyer_ids = {r.user_id for r in buyer_rows}

    return [
        {
            "id": r.id,
            "name": r.full_name or r.username or str(r.id),
            "username": r.username,
            "joined_at": r.created_at.isoformat(),
            "is_buyer": r.id in buyer_ids,
        }
        for r in rows
    ]


@app.get("/api/admin/bio-promo")
async def api_admin_bio_promo_list(
    page: int = 1, limit: int = 30,
    admin: User = Depends(require_admin),
):
    from math import ceil
    offset = (page - 1) * limit
    async with AsyncSessionLocal() as s:
        total = await s.scalar(select(func.count(BioPromo.user_id))) or 0
        rows = (await s.execute(
            select(BioPromo, User.full_name, User.username)
            .join(User, User.id == BioPromo.user_id)
            .order_by(BioPromo.joined_at.desc())
            .offset(offset).limit(limit)
        )).all()
    items = []
    for promo, full_name, username in rows:
        items.append({
            "user_id":         promo.user_id,
            "name":            full_name or str(promo.user_id),
            "username":        username,
            "is_active":       promo.is_active,
            "reward_tier":     promo.reward_tier,
            "total_rewarded":  promo.total_rewarded,
            "joined_at":       promo.joined_at.isoformat() if promo.joined_at else None,
            "last_check_at":   promo.last_check_at.isoformat() if promo.last_check_at else None,
            "last_rewarded_at":promo.last_rewarded_at.isoformat() if promo.last_rewarded_at else None,
        })
    return {"items": items, "total": total, "page": page, "pages": max(1, ceil(total / limit))}


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
        return {"joined": False, "is_active": False, "reward_tier": 0, "total_rewarded": 0, "hours_until_next": None}
    return {
        "joined": True,
        "is_active": promo.is_active,
        "reward_tier": promo.reward_tier,
        "total_rewarded": promo.total_rewarded,
        "last_rewarded_at": promo.last_rewarded_at.isoformat() if promo.last_rewarded_at else None,
        "hours_until_next": _hours_until_midnight() if promo.is_active else None,
    }


@app.post("/api/bio-promo/check")
async def bio_promo_check(user: User = Depends(get_current_user)):
    """User-triggered check.
    - Tier 1 (username only): +1⭐ on connect (24h anti-abuse), +1⭐ at midnight.
    - Tier 2 (full phrase):   +2⭐ on connect (24h anti-abuse), +2⭐ at midnight.
    """
    from sqlalchemy import select as _sel
    now = datetime.utcnow()

    has_bio, tier = await _check_bio_tier(user.id)  # outside transaction
    stars_amount = tier  # 0, 1, or 2

    rewarded = False
    async with AsyncSessionLocal() as s:
        async with s.begin():
            promo = (await s.execute(
                _sel(BioPromo).where(BioPromo.user_id == user.id).with_for_update()
            )).scalar_one_or_none()
            if not promo:
                promo = BioPromo(user_id=user.id)
                s.add(promo)

            promo.is_active = has_bio
            promo.reward_tier = tier
            promo.last_check_at = now

            # Give instant stars on connect — protected by 24h anti-abuse window
            can_reward = has_bio and (
                promo.last_rewarded_at is None
                or (now - promo.last_rewarded_at).total_seconds() >= 86400
            )
            if can_reward:
                u = await s.get(User, user.id, with_for_update=True)
                if u and not u.is_banned:
                    u.balance_stars += stars_amount
                    u.balance_usd += Decimal(str(settings.STAR_DISPLAY_USD)) * stars_amount
                    promo.last_rewarded_at = now
                    promo.total_rewarded += stars_amount
                    rewarded = True

    return {
        "joined": True,
        "is_active": has_bio,
        "reward_tier": tier,
        "rewarded": rewarded,
        "stars_rewarded": stars_amount if rewarded else 0,
        "total_rewarded": promo.total_rewarded,
        "hours_until_next": _hours_until_midnight() if has_bio else None,
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
    # Швидка попередня перевірка (до зовнішнього API-виклику)
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
            u = await s.get(User, user.id, with_for_update=True)
            # Повторна перевірка всередині транзакції (захист від race condition)
            if u.balance_stars < price_stars:
                raise HTTPException(402, "insufficient_balance")
            bal_before = u.balance_stars
            u.balance_stars = u.balance_stars - price_stars
            u.balance_usd   = max(Decimal(0), u.balance_usd - price_usd_val)
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

    # ── Публічний пост у канал-вітрину (без посилання на канал клієнта) ──────
    if _bot and settings.SELL_CHANNEL_USERNAME:
        try:
            _buyer = f"@{user.username}" if user.username else (user.full_name or "Покупатель")
            _svc_flag = svc.get("flag", "🚀")
            _svc_name = svc.get("title", body.service_key)
            sell_txt = (
                f"🚀 <b>Новая накрутка!</b>\n\n"
                f"👤 {_buyer}\n"
                f"{_svc_flag} <b>{_svc_name}</b>\n"
                f"🔢 Количество: <b>{body.quantity}</b>\n"
                f"💫 Сумма: <b>⭐{price_stars}</b>\n\n"
                f"@{_BOT_USERNAME}"
            )
            await _bot.send_message(settings.SELL_CHANNEL_USERNAME, sell_txt, parse_mode="HTML")
        except Exception as e:
            log.warning("Sell-channel SMM post failed: %s", e)

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


# ─── NFT Username Rentals ────────────────────────────────────────────────────

@app.get("/api/nft/list")
async def api_nft_list(search: str = "", user: User = Depends(get_current_user)):
    now = datetime.utcnow()
    async with AsyncSessionLocal() as s:
        q = select(NftUsername).where(NftUsername.is_available == True)
        if search.strip():
            term = f"%{search.strip()}%"
            from sqlalchemy import or_
            q = q.where(or_(NftUsername.username.ilike(term), NftUsername.description.ilike(term)))
        rows = (await s.execute(q.order_by(NftUsername.id.asc()))).scalars().all()

        result = []
        for nft in rows:
            rental = (await s.execute(
                select(NftRental)
                .where(NftRental.nft_id == nft.id, NftRental.status == "active", NftRental.expires_at > now)
                .limit(1)
            )).scalar_one_or_none()
            result.append({
                "id": nft.id,
                "username": nft.username,
                "description": nft.description,
                "price_stars": nft.price_stars,
                "duration_days": nft.duration_days,
                "is_available": nft.is_available,
                "currently_rented": rental is not None,
                "expires_at": rental.expires_at.isoformat() if rental else None,
            })
    return result


class NftBuyRequest(BaseModel):
    nft_id: int


@app.post("/api/nft/buy")
async def api_nft_buy(body: NftBuyRequest, user: User = Depends(get_current_user)):
    now = datetime.utcnow()
    async with AsyncSessionLocal() as s:
        async with s.begin():
            nft = await s.get(NftUsername, body.nft_id, with_for_update=True)
            if not nft or not nft.is_available:
                raise HTTPException(404, "nft_not_found")

            # Check if currently rented
            rental_check = (await s.execute(
                select(NftRental)
                .where(NftRental.nft_id == nft.id, NftRental.status == "active", NftRental.expires_at > now)
                .limit(1)
            )).scalar_one_or_none()
            if rental_check:
                raise HTTPException(409, "currently_rented")

            # Check balance
            u = await s.get(User, user.id, with_for_update=True)
            if u.balance_stars < nft.price_stars:
                raise HTTPException(400, "insufficient_balance")

            u.balance_stars -= nft.price_stars
            price_usd = Decimal(str(round(nft.price_stars * settings.STAR_DISPLAY_USD, 6)))

            order = Order(
                user_id=u.id,
                product_id=0,
                price_usd=price_usd,
                cost_usd=Decimal("0"),
                category="nft_rental",
                status="delivered",
                delivered_data=f"@{nft.username}",
                smm_quantity=0,
            )
            s.add(order)
            await s.flush()

            expires_at = now + timedelta(days=nft.duration_days)
            rental = NftRental(
                nft_id=nft.id,
                user_id=u.id,
                order_id=order.id,
                started_at=now,
                expires_at=expires_at,
                status="active",
            )
            s.add(rental)
            order_id = order.id

    # Notify admin
    if _bot and settings.ADMIN_IDS:
        uname = f"@{user.username}" if user.username else f"ID:{user.id}"
        txt = (
            f"🔤 <b>NFT Username оренда!</b>\n\n"
            f"👤 {uname} (<code>{user.id}</code>)\n"
            f"📛 Юзернейм: <b>@{nft.username}</b>\n"
            f"⏳ Тривалість: <b>{nft.duration_days} днів</b>\n"
            f"📅 Закінчується: <b>{expires_at.strftime('%d.%m.%Y')}</b>\n"
            f"💫 Оплачено: <b>⭐{nft.price_stars}</b>\n"
            f"🆔 Замовлення: <code>#{order_id}</code>"
        )
        for admin_id in settings.ADMIN_IDS:
            try:
                await _bot.send_message(admin_id, txt, parse_mode="HTML")
            except Exception as e:
                log.warning("Admin NFT notify failed for %s: %s", admin_id, e)

    return {"order_id": order_id, "stars_spent": nft.price_stars, "expires_at": expires_at.isoformat()}


# ── Admin NFT endpoints ──────────────────────────────────────────────────────

@app.get("/api/admin/nft/list")
async def api_admin_nft_list(admin: User = Depends(require_admin)):
    now = datetime.utcnow()
    async with AsyncSessionLocal() as s:
        rows = (await s.execute(select(NftUsername).order_by(NftUsername.id.asc()))).scalars().all()
        result = []
        for nft in rows:
            rental = (await s.execute(
                select(NftRental)
                .where(NftRental.nft_id == nft.id, NftRental.status == "active", NftRental.expires_at > now)
                .limit(1)
            )).scalar_one_or_none()
            result.append({
                "id": nft.id,
                "username": nft.username,
                "description": nft.description,
                "price_stars": nft.price_stars,
                "duration_days": nft.duration_days,
                "is_available": nft.is_available,
                "currently_rented": rental is not None,
                "expires_at": rental.expires_at.isoformat() if rental else None,
                "added_by": nft.added_by,
                "created_at": nft.created_at.isoformat(),
            })
    return result


class NftAddRequest(BaseModel):
    username: str
    description: str = ""
    price_stars: int
    duration_days: int = 30


@app.post("/api/admin/nft/add")
async def api_admin_nft_add(body: NftAddRequest, admin: User = Depends(require_admin)):
    uname = body.username.lstrip("@").strip()
    if not uname:
        raise HTTPException(400, "invalid_username")
    async with AsyncSessionLocal() as s:
        async with s.begin():
            nft = NftUsername(
                username=uname,
                description=body.description.strip() or None,
                price_stars=body.price_stars,
                duration_days=body.duration_days,
                is_available=True,
                added_by=admin.id,
            )
            s.add(nft)
            await s.flush()
            nft_id = nft.id
    return {"ok": True, "id": nft_id}


class NftEditRequest(BaseModel):
    username: str | None = None
    description: str | None = None
    price_stars: int | None = None
    duration_days: int | None = None
    is_available: bool | None = None


@app.post("/api/admin/nft/{nft_id}/edit")
async def api_admin_nft_edit(nft_id: int, body: NftEditRequest, admin: User = Depends(require_admin)):
    async with AsyncSessionLocal() as s:
        async with s.begin():
            nft = await s.get(NftUsername, nft_id)
            if not nft:
                raise HTTPException(404, "not_found")
            if body.username is not None:
                nft.username = body.username.lstrip("@").strip()
            if body.description is not None:
                nft.description = body.description.strip() or None
            if body.price_stars is not None:
                nft.price_stars = body.price_stars
            if body.duration_days is not None:
                nft.duration_days = body.duration_days
            if body.is_available is not None:
                nft.is_available = body.is_available
    return {"ok": True}


@app.delete("/api/admin/nft/{nft_id}")
async def api_admin_nft_delete(nft_id: int, admin: User = Depends(require_admin)):
    now = datetime.utcnow()
    async with AsyncSessionLocal() as s:
        async with s.begin():
            nft = await s.get(NftUsername, nft_id)
            if not nft:
                raise HTTPException(404, "not_found")
            active = (await s.execute(
                select(NftRental)
                .where(NftRental.nft_id == nft_id, NftRental.status == "active", NftRental.expires_at > now)
                .limit(1)
            )).scalar_one_or_none()
            if active:
                raise HTTPException(409, "has_active_rental")
            await s.delete(nft)
    return {"ok": True}


@app.get("/api/admin/nft/rentals")
async def api_admin_nft_rentals(admin: User = Depends(require_admin)):
    now = datetime.utcnow()
    async with AsyncSessionLocal() as s:
        rows = (await s.execute(
            select(NftRental, NftUsername.username, User.full_name, User.username)
            .join(NftUsername, NftUsername.id == NftRental.nft_id)
            .join(User, User.id == NftRental.user_id)
            .order_by(NftRental.created_at.desc())
            .limit(50)
        )).all()
    result = []
    for rental, nft_uname, user_name, user_uname in rows:
        days_left = int((rental.expires_at - now).total_seconds() // 86400)
        result.append({
            "id": rental.id,
            "nft_id": rental.nft_id,
            "username": nft_uname,
            "user_id": rental.user_id,
            "user_name": user_name or str(rental.user_id),
            "user_username": user_uname,
            "started_at": rental.started_at.isoformat(),
            "expires_at": rental.expires_at.isoformat(),
            "status": rental.status,
            "days_left": days_left,
        })
    return result


# ─── Fortune Wheel (Pool-based) ────────────────────────────────────────────────

FORTUNE_SPIN_COST     = 100   # зірок за прокрут
FORTUNE_ADMIN_CUT_PCT = 0.20  # 20% від маржі прибутку → адміну, 80% → пул

# threshold = скільки зірок потрібно В ПУЛ щоб акк міг випасти
# = max(0, shop_stars - FORTUNE_SPIN_COST)
# MM/US/CO завжди виграють (прибуткові), DE/UA/KZ потребують пул
FORTUNE_CATS = [
    {"cat": "mm", "label": "🇲🇲 Myanmar",   "emoji": "🎁", "color": "#22c55e", "threshold": 0,   "shop_stars": 50,  "weight": 25, "seg": 0},
    {"cat": "us", "label": "🇺🇸 USA",        "emoji": "🎁", "color": "#3b82f6", "threshold": 0,   "shop_stars": 50,  "weight": 25, "seg": 1},
    {"cat": "co", "label": "🇨🇴 Colombia",   "emoji": "💫", "color": "#8b5cf6", "threshold": 0,   "shop_stars": 60,  "weight": 20, "seg": 2},
    {"cat": "de", "label": "🇩🇪 Germany",    "emoji": "💎", "color": "#f59e0b", "threshold": 50,  "shop_stars": 150, "weight": 15, "seg": 3},
    {"cat": "ua", "label": "🇺🇦 Ukraine",    "emoji": "🏆", "color": "#ef4444", "threshold": 150, "shop_stars": 250, "weight": 10, "seg": 4},
    {"cat": "kz", "label": "🇰🇿 Kazakhstan", "emoji": "🔥", "color": "#ec4899", "threshold": 150, "shop_stars": 250, "weight": 5,  "seg": 5},
]
_FORTUNE_FALLBACK = FORTUNE_CATS[0]  # мінімальний приз (MM) якщо пулу не вистачає
_FORTUNE_WEIGHTS = [c["weight"] for c in FORTUNE_CATS]


@app.get("/api/fortune/prizes")
async def api_fortune_prizes(user: User = Depends(get_current_user)):
    async with AsyncSessionLocal() as s:
        pool = await s.get(FortunePool, 1)
        pool_balance = pool.balance_stars if pool else 0
    return {
        "cats": [
            {
                "seg": c["seg"], "cat": c["cat"],
                "label": c["label"], "emoji": c["emoji"],
                "color": c["color"], "threshold": c["threshold"],
            }
            for c in FORTUNE_CATS
        ],
        "pool_balance": pool_balance,
        "spin_cost": FORTUNE_SPIN_COST,
    }


@app.get("/api/fortune/pool")
async def api_fortune_pool(user: User = Depends(get_current_user)):
    async with AsyncSessionLocal() as s:
        pool = await s.get(FortunePool, 1)
        if not pool:
            return {"balance_stars": 0, "total_spins": 0, "total_admin_profit_stars": 0,
                    "total_prizes_count": 0, "total_prizes_stars": 0}
        return {
            "balance_stars": pool.balance_stars,
            "total_spins": pool.total_spins,
            "total_admin_profit_stars": pool.total_admin_profit_stars,
            "total_prizes_count": pool.total_prizes_count,
            "total_prizes_stars": pool.total_prizes_stars,
        }


@app.get("/api/fortune/recent")
async def api_fortune_recent(user: User = Depends(get_current_user)):
    async with AsyncSessionLocal() as s:
        rows = (await s.execute(
            select(FortuneSpin.prize_label, FortuneSpin.created_at, User.full_name, User.username)
            .join(User, User.id == FortuneSpin.user_id)
            .where(FortuneSpin.prize_type == "account", FortuneSpin.claim_type.in_(["account", "stars"]))
            .order_by(FortuneSpin.created_at.desc())
            .limit(20)
        )).all()
    result = []
    for label, created_at, name, uname in rows:
        display = f"@{uname}" if uname else (name or "Гравець")[:12]
        result.append({
            "user_display": display,
            "prize_label": label,
            "created_at": created_at.isoformat() if created_at else None,
        })
    return result


@app.post("/api/fortune/spin")
async def api_fortune_spin(user: User = Depends(get_current_user)):
    import random as _rnd
    pool_balance_after = 0
    spin_id: int | None = None
    new_balance = 0
    admin_profit_this_spin = 0
    pick: dict | None = None

    async with AsyncSessionLocal() as s:
        async with s.begin():
            u = await s.get(User, user.id, with_for_update=True)
            if u.balance_stars < FORTUNE_SPIN_COST:
                raise HTTPException(402, "insufficient_balance")

            pool = await s.get(FortunePool, 1, with_for_update=True)
            if not pool:
                pool = FortunePool(id=1, balance_stars=0, total_spins=0,
                                   total_admin_profit_stars=0, total_prizes_count=0, total_prizes_stars=0)
                s.add(pool)
                await s.flush()

            u.balance_stars -= FORTUNE_SPIN_COST
            u.balance_usd = max(Decimal(0), u.balance_usd - Decimal(str(round(FORTUNE_SPIN_COST * settings.STAR_DISPLAY_USD, 4))))
            pool.total_spins += 1

            # Рулетка тільки з тих категорій, для яких пул достатній
            eligible = [c for c in FORTUNE_CATS if pool.balance_stars >= c["threshold"]]
            pick = _rnd.choices(eligible, weights=[c["weight"] for c in eligible], k=1)[0]

            shop_stars = pick["shop_stars"]
            margin = FORTUNE_SPIN_COST - shop_stars

            if margin > 0:
                admin_profit_this_spin = int(margin * FORTUNE_ADMIN_CUT_PCT)
                pool.balance_stars += margin - admin_profit_this_spin
                pool.total_admin_profit_stars += admin_profit_this_spin
            else:
                pool.balance_stars += margin  # дорогий акк — пул покриває різницю

            pool.total_prizes_count += 1
            pool.total_prizes_stars += shop_stars

            spin = FortuneSpin(
                user_id=user.id,
                prize_type="account",
                prize_stars=None,
                prize_category=pick["cat"],
                prize_stars_equiv=shop_stars,
                prize_label=pick["label"],
                prize_segment=pick["seg"],
                claim_type="pending",
            )
            s.add(spin)
            await s.flush()
            spin_id = spin.id
            pool_balance_after = pool.balance_stars
            new_balance = u.balance_stars

    stars_option = int(pick["shop_stars"] * 0.90)
    log.info("FORTUNE: user=%s spin=%s cat=%s pool=%s admin=%s",
             user.id, spin_id, pick["cat"], pool_balance_after, admin_profit_this_spin)

    # Сповіщення адміну
    if _bot and settings.ADMIN_IDS:
        uname_s = f"@{user.username}" if user.username else f"ID:{user.id}"
        notify_txt = (
            f"🎲 <b>Кейс — виграш (очікує вибір)</b>\n\n"
            f"👤 {uname_s} (<code>{user.id}</code>)\n"
            f"🏆 Приз: <b>{pick['label']}</b>\n"
            f"💰 Адм. прибуток: +⭐{admin_profit_this_spin}\n"
            f"🏦 Пул: ⭐{pool_balance_after}"
        )
        for aid in settings.ADMIN_IDS:
            try:
                await _bot.send_message(aid, notify_txt, parse_mode="HTML")
            except Exception:
                pass

    return {
        "spin_id":        spin_id,
        "won":            True,
        "prize_cat":      pick["cat"],
        "prize_seg":      pick["seg"],
        "prize_label":    pick["label"],
        "prize_emoji":    pick["emoji"],
        "prize_color":    pick["color"],
        "phone":          None,
        "order_id":       None,
        "pool_balance":   pool_balance_after,
        "pool_threshold": pick["threshold"],
        "was_downgraded": False,
        "rolled_label":   None,
        "new_balance":    new_balance,
        "stars_option":   stars_option,
    }


class FortuneClaim(BaseModel):
    spin_id: int
    choice: str  # "account" | "stars"


@app.post("/api/fortune/claim")
async def api_fortune_claim(body: FortuneClaim, user: User = Depends(get_current_user)):
    phone: str | None = None
    order_id: int | None = None
    stars_awarded: int | None = None

    async with AsyncSessionLocal() as s:
        async with s.begin():
            sp = await s.get(FortuneSpin, body.spin_id, with_for_update=True)
            if not sp or sp.user_id != user.id:
                raise HTTPException(404, "spin_not_found")
            if sp.claim_type != "pending":
                raise HTTPException(409, "already_claimed")
            if not sp.prize_category or not sp.prize_stars_equiv:
                raise HTTPException(400, "no_prize")

            if body.choice == "stars":
                _fc = next((c for c in FORTUNE_CATS if c["cat"] == sp.prize_category), None)
                _shop_stars = _fc["shop_stars"] if _fc else sp.prize_stars_equiv
                stars_awarded = int(_shop_stars * 0.90)
                u = await s.get(User, user.id, with_for_update=True)
                u.balance_stars += stars_awarded
                sp.claim_type = "stars"
                sp.prize_stars = stars_awarded

    if body.choice == "account":
        try:
            from lemur_shop.services.lolz_shop import auto_buy_category as _abc
            # Дохід з видачі акаунта = ціна акаунта в шопі + частка адміна з маржі прокрута.
            # (решта маржі — 80% — лишається в пулі й тут не рахується)
            _shop_stars = sp.prize_stars_equiv
            _margin = FORTUNE_SPIN_COST - _shop_stars
            _admin_cut = int(_margin * FORTUNE_ADMIN_CUT_PCT) if _margin > 0 else 0
            price_usd = Decimal(str(round((_shop_stars + _admin_cut) * settings.STAR_DISPLAY_USD, 4)))
            phone_val, lolz_item_id, lolz_price = await _abc(sp.prize_category)
            lolz_cost = Decimal(str(round(lolz_price, 6)))
            async with AsyncSessionLocal() as s:
                async with s.begin():
                    order = Order(
                        user_id=user.id, product_id=0,
                        lolz_item_id=lolz_item_id,
                        price_usd=price_usd, cost_usd=lolz_cost,
                        category=sp.prize_category, status="delivered",
                        delivered_data=phone_val, resend_count=0,
                    )
                    s.add(order)
                    await s.flush()
                    order_id = order.id
                    sp2 = await s.get(FortuneSpin, body.spin_id, with_for_update=True)
                    if sp2:
                        sp2.claim_type = "account"
                        sp2.order_id = order_id
            phone = phone_val
        except Exception as e:
            log.warning("FORTUNE claim account failed (%s), reverting", e)
            async with AsyncSessionLocal() as s:
                async with s.begin():
                    pool_r = await s.get(FortunePool, 1, with_for_update=True)
                    if pool_r:
                        pool_r.balance_stars += sp.prize_stars_equiv
                        pool_r.total_prizes_count = max(0, pool_r.total_prizes_count - 1)
                        pool_r.total_prizes_stars = max(0, pool_r.total_prizes_stars - sp.prize_stars_equiv)
                    sp3 = await s.get(FortuneSpin, body.spin_id, with_for_update=True)
                    if sp3:
                        sp3.prize_type = "none"
                        sp3.prize_category = None
                        sp3.claim_type = "none"
            if _bot and settings.ADMIN_IDS:
                uname_s = f"@{user.username}" if user.username else f"ID:{user.id}"
                for aid in settings.ADMIN_IDS:
                    try:
                        await _bot.send_message(
                            aid,
                            f"⚠️ <b>FORTUNE: помилка покупки!</b>\n👤 {uname_s}\n🎁 {sp.prize_label}\n❌ {e}",
                            parse_mode="HTML",
                        )
                    except Exception:
                        pass
            raise HTTPException(500, "purchase_failed")

    # Сповіщення адміну про вибір
    if _bot and settings.ADMIN_IDS:
        uname_s = f"@{user.username}" if user.username else f"ID:{user.id}"
        if body.choice == "account":
            n = (f"✅ <b>Фортуна — видано акаунт</b>\n👤 {uname_s}\n"
                 f"🏆 {sp.prize_label}\n📱 <code>{phone}</code>\n🆔 #{order_id}")
        else:
            n = (f"⭐ <b>Фортуна — вибрано зірки</b>\n👤 {uname_s}\n"
                 f"🏆 {sp.prize_label} → ⭐{stars_awarded}")
        for aid in settings.ADMIN_IDS:
            try:
                await _bot.send_message(aid, n, parse_mode="HTML")
            except Exception:
                pass

    # Гравцю в ЛС нічого не надсилаємо — результат показується у міні-аппі

    return {
        "ok":           True,
        "choice":       body.choice,
        "phone":        phone,
        "order_id":     order_id,
        "stars_awarded": stars_awarded,
    }


@app.get("/api/admin/fortune")
async def api_admin_fortune(user: User = Depends(get_current_user)):
    if user.id not in settings.ADMIN_IDS:
        raise HTTPException(403)
    async with AsyncSessionLocal() as s:
        pool = await s.get(FortunePool, 1)
        if not pool:
            return {"balance_stars": 0, "total_spins": 0, "total_admin_profit_stars": 0,
                    "total_prizes_count": 0, "total_prizes_stars": 0,
                    "acc_claims": 0, "acc_cost_usd": 0.0, "acc_value_stars": 0, "stars_claims": 0}

        # Дохід з ТГ-акаунтів, виданих через кейс (claim = account)
        acc_count, acc_cost, acc_value = (await s.execute(
            select(
                func.count(FortuneSpin.id),
                func.coalesce(func.sum(Order.cost_usd), 0),
                func.coalesce(func.sum(FortuneSpin.prize_stars_equiv), 0),
            )
            .join(Order, Order.id == FortuneSpin.order_id)
            .where(FortuneSpin.claim_type == "account")
        )).one()
        stars_claims = (await s.execute(
            select(func.count(FortuneSpin.id)).where(FortuneSpin.claim_type == "stars")
        )).scalar() or 0

        return {
            "balance_stars": pool.balance_stars,
            "total_spins": pool.total_spins,
            "total_admin_profit_stars": pool.total_admin_profit_stars,
            "total_prizes_count": pool.total_prizes_count,
            "total_prizes_stars": pool.total_prizes_stars,
            "acc_claims": int(acc_count or 0),
            "acc_cost_usd": float(acc_cost or 0),
            "acc_value_stars": int(acc_value or 0),
            "stars_claims": int(stars_claims),
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
