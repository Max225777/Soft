from __future__ import annotations

import logging
from decimal import Decimal

from aiogram import F, Router
from aiogram.types import Message, PreCheckoutQuery
from sqlalchemy import select, text

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
    payload = sp.invoice_payload
    stars = sp.total_amount
    charge_id = sp.telegram_payment_charge_id

    log.info("Stars payment received: charge_id=%s payload=%r stars=%s from tg_user=%s",
             charge_id, payload, stars, message.from_user.id)

    try:
        parts = payload.split(":")
        if parts[0] != "stars_topup":
            log.warning("Stars payment unknown payload type=%r charge_id=%s", parts[0], charge_id)
            return
        user_id = int(parts[1])
    except Exception as e:
        log.error("Stars payment bad payload %r charge_id=%s: %s", payload, charge_id, e)
        return

    # Перевірка дубліката (окрема транзакція, best-effort)
    try:
        async with AsyncSessionLocal() as s:
            existing = await s.scalar(
                select(TopUp.id).where(TopUp.charge_id == charge_id).limit(1)
            )
        if existing:
            log.warning("Stars payment DUPLICATE: charge_id=%s user=%s stars=%s — skip (topup_id=%s)",
                        charge_id, user_id, stars, existing)
            await message.answer(
                f"ℹ️ Це поповнення вже було зараховано.\nCharge ID: <code>{charge_id}</code>",
                parse_mode="HTML"
            )
            return
    except Exception as e:
        # charge_id колонка може ще не існувати — не блокуємо зарахування
        log.warning("Stars dedup check failed (charge_id column may not exist): %s", e)

    amount_usd = Decimal(str(round(stars * settings.STAR_DISPLAY_USD, 4)))

    # Основна транзакція — оновлюємо баланс (без нових колонок, завжди працює)
    bal_before = 0
    new_balance = 0
    uname = f"ID:{user_id}"
    topup_id: int | None = None

    try:
        async with AsyncSessionLocal() as s:
            async with s.begin():
                user = await s.get(User, user_id)
                if not user:
                    log.error("Stars payment for unknown user=%s stars=%s charge_id=%s", user_id, stars, charge_id)
                    return
                uname = f"@{user.username}" if user.username else f"ID:{user_id}"
                bal_before = user.balance_stars
                user.balance_stars = user.balance_stars + stars
                user.balance_usd   = user.balance_usd + amount_usd
                new_balance = user.balance_stars
                topup = TopUp(
                    user_id=user_id,
                    amount_usd=amount_usd,
                    amount_stars=stars,
                    admin_id=0,
                )
                s.add(topup)
                await s.flush()
                topup_id = topup.id
    except Exception as e:
        log.error("Stars payment DB error: charge_id=%s user=%s stars=%s: %s",
                  charge_id, user_id, stars, e, exc_info=True)
        return

    log.info("Stars payment CREDITED: charge_id=%s user=%s stars=+%s balance %s→%s",
             charge_id, user_id, stars, bal_before, new_balance)

    # Best-effort: зберігаємо charge_id і method (якщо колонки вже є)
    if topup_id:
        try:
            async with AsyncSessionLocal() as s:
                async with s.begin():
                    await s.execute(
                        text("UPDATE topups SET method='stars', charge_id=:cid WHERE id=:tid"),
                        {"cid": charge_id, "tid": topup_id}
                    )
        except Exception as e:
            log.warning("Could not set charge_id on topup_id=%s: %s", topup_id, e)

    await message.answer(
        f"✅ Баланс поповнено!\n\n"
        f"⭐ +{stars} зірок\n"
        f"💫 Новий баланс: <b>⭐{new_balance}</b>",
        parse_mode="HTML"
    )

    from lemur_shop.server import _bot
    if _bot and settings.ADMIN_IDS:
        txt = (
            f"⭐ <b>Поповнення через Stars!</b>\n\n"
            f"👤 {uname} (<code>{user_id}</code>)\n"
            f"⭐ Зараховано: <b>+{stars}</b>\n"
            f"💫 Баланс: <b>⭐{new_balance}</b>\n"
            f"🆔 charge_id: <code>{charge_id}</code>"
        )
        for admin_id in settings.ADMIN_IDS:
            try:
                await _bot.send_message(admin_id, txt, parse_mode="HTML")
            except Exception:
                pass
