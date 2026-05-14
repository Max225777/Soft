from __future__ import annotations

import hashlib
import hmac
import json
from urllib.parse import parse_qsl, unquote

from fastapi import Depends, FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy import func, select

from lemur_shop.api.lolz import LolzApiError
from lemur_shop.config import settings
from lemur_shop.db.models import Order, ReferralPayout, User
from lemur_shop.db.session import AsyncSessionLocal
from lemur_shop.services.lolz_shop import auto_buy, search_accounts
from lemur_shop.utils.currency import format_balance, get_rate

app = FastAPI(title="Lemur Shop API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Telegram initData auth ───────────────────────────────────────────────────

def _validate_init_data(init_data: str) -> dict:
    """Перевіряє підпис Telegram initData. Повертає user dict."""
    pairs = dict(parse_qsl(init_data, keep_blank_values=True))
    hash_val = pairs.pop("hash", "")

    data_check = "\n".join(f"{k}={v}" for k, v in sorted(pairs.items()))
    secret = hmac.new(b"WebAppData", settings.BOT_TOKEN.encode(), hashlib.sha256).digest()
    expected = hmac.new(secret, data_check.encode(), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(expected, hash_val):
        raise HTTPException(status_code=401, detail="Invalid initData")

    user_json = pairs.get("user", "{}")
    return json.loads(unquote(user_json))


async def get_current_user(x_init_data: str = Header(...)) -> User:
    tg_user = _validate_init_data(x_init_data)
    tg_id = int(tg_user["id"])
    async with AsyncSessionLocal() as s:
        user = await s.get(User, tg_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found. Start bot first.")
    return user


# ─── Schemas ──────────────────────────────────────────────────────────────────

class BuyRequest(BaseModel):
    item_id: int
    price: float
    category: str


# ─── Routes ───────────────────────────────────────────────────────────────────

@app.get("/api/me")
async def api_me(user: User = Depends(get_current_user)):
    uah = await get_rate("UAH")
    rub = await get_rate("RUB")
    async with AsyncSessionLocal() as s:
        orders_count = await s.scalar(select(func.count()).where(Order.user_id == user.id))
    return {
        "id":           user.id,
        "name":         user.full_name or user.username or str(user.id),
        "username":     user.username,
        "lang":         user.lang,
        "balance_usd":  float(user.balance_usd),
        "balance_uah":  round(float(user.balance_usd) * uah, 0),
        "balance_rub":  round(float(user.balance_usd) * rub, 0),
        "orders_count": orders_count,
        "is_admin":     user.id in settings.ADMIN_IDS,
    }


@app.get("/api/shop/{category}")
async def api_shop(category: str, user: User = Depends(get_current_user)):
    items = await search_accounts(category)
    return [
        {
            "item_id": item.get("item_id") or item.get("id"),
            "title":   item.get("item_origin") or f"TG аккаунт",
            "price":   float(item.get("price") or item.get("price_usd") or 0),
            "reg_date": item.get("reg_date") or "",
        }
        for item in items
    ]


@app.post("/api/buy")
async def api_buy(body: BuyRequest, user: User = Depends(get_current_user)):
    try:
        phone, code = await auto_buy(body.item_id, body.price)
    except (LolzApiError, ValueError) as e:
        raise HTTPException(status_code=502, detail=str(e))

    async with AsyncSessionLocal() as s:
        async with s.begin():
            order = Order(
                user_id=user.id,
                product_id=0,
                lolz_item_id=body.item_id,
                price_usd=body.price,
                status="delivered",
                delivered_data=f"{phone}\n{code}",
                resend_count=1,
            )
            s.add(order)
            await s.flush()
            order_id = order.id

    return {"order_id": order_id, "phone": phone, "code": code}


@app.get("/api/orders")
async def api_orders(user: User = Depends(get_current_user)):
    async with AsyncSessionLocal() as s:
        result = await s.execute(
            select(Order)
            .where(Order.user_id == user.id)
            .order_by(Order.created_at.desc())
            .limit(20)
        )
        orders = result.scalars().all()
    return [
        {
            "id":        o.id,
            "price_usd": float(o.price_usd),
            "status":    o.status,
            "created_at": o.created_at.isoformat(),
        }
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
