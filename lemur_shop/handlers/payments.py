from __future__ import annotations

import logging
from decimal import Decimal

from aiogram import F, Router
from aiogram.types import Message, PreCheckoutQuery

from lemur_shop.config import settings
from lemur_shop.db.models import TopUp, User
from lemur_shop.db.session import AsyncSessionLocal

log = logging.getLogger(__name__)
router = Router()


@router.pre_checkout_query()
async def pre_checkout(query: PreCheckoutQuery) -> None:
    await query.answer(ok=True)


@router.message(F.successful_payment)
async def successful_payment(message: Message) -> None:
    sp = message.successful_payment
    payload = sp.invoice_payload  # "stars_topup:{user_id}:{amount_usd}"
    stars = sp.total_amount       # кількість зірок (XTR amount)

    try:
        parts = payload.split(":")
        if parts[0] != "stars_topup":
            return
        user_id = int(parts[1])
        amount_usd = Decimal(parts[2])
    except Exception as e:
        log.error("Bad payment payload %r: %s", payload, e)
        return

    async with AsyncSessionLocal() as s:
        async with s.begin():
            user = await s.get(User, user_id)
            if not user:
                log.error("Payment for unknown user %s", user_id)
                return
            user.balance_usd = user.balance_usd + amount_usd
            s.add(TopUp(
                user_id=user_id,
                amount_usd=amount_usd,
                admin_id=0,  # 0 = Stars payment
            ))

    log.info("Stars topup: user=%s stars=%s usd=%s", user_id, stars, amount_usd)

    uname = f"@{user.username}" if user.username else f"ID:{user_id}"
    await message.answer(
        f"✅ Баланс поповнено!\n\n"
        f"⭐ {stars} зірок → <b>${float(amount_usd):.2f}</b>\n"
        f"💰 Новий баланс: <b>${float(user.balance_usd):.2f}</b>",
        parse_mode="HTML"
    )

    # Нотифікація адміну
    from lemur_shop.server import _bot
    if _bot and settings.ADMIN_IDS:
        txt = (
            f"⭐ <b>Поповнення через Stars!</b>\n\n"
            f"👤 {uname} (<code>{user_id}</code>)\n"
            f"⭐ Stars: {stars}\n"
            f"💰 Зараховано: <b>${float(amount_usd):.2f}</b>"
        )
        for admin_id in settings.ADMIN_IDS:
            try:
                await _bot.send_message(admin_id, txt, parse_mode="HTML")
            except Exception:
                pass
