from __future__ import annotations

import logging
from decimal import Decimal

from aiogram import Router
from aiogram.filters import BaseFilter, Command
from aiogram.types import Message
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from lemur_shop.config import settings
from lemur_shop.db.models import Order, TopUp, User
from lemur_shop.db.session import AsyncSessionLocal

log = logging.getLogger(__name__)

router = Router()


class IsAdmin(BaseFilter):
    async def __call__(self, message: Message) -> bool:
        return message.from_user is not None and message.from_user.id in settings.ADMIN_IDS


def _is_admin(user_id: int) -> bool:
    return user_id in settings.ADMIN_IDS


async def _find_user(session, query: str) -> User | None:
    q = query.lstrip("@")
    if q.isdigit():
        return await session.get(User, int(q))
    result = await session.execute(select(User).where(User.username == q).limit(1))
    return result.scalar_one_or_none()


@router.message(Command("topup"), IsAdmin())
async def cmd_topup(message: Message) -> None:
    if not _is_admin(message.from_user.id):
        return

    parts = (message.text or "").split()
    if len(parts) != 3:
        await message.answer("Використання: /topup «user_id» «зірки»\nПриклад: /topup 123456789 100", parse_mode=None)
        return

    try:
        stars = int(parts[2])
        if stars <= 0:
            raise ValueError
    except (ValueError, Exception):
        await message.answer("❌ Невірний формат. Приклад: /topup 123456789 100", parse_mode=None)
        return

    # charge_id на основі message_id — гарантує exactly-once навіть якщо команда відправлена двічі
    charge_id = f"admin:{message.chat.id}:{message.message_id}"

    try:
        async with AsyncSessionLocal() as s:
            async with s.begin():
                user = await _find_user(s, parts[1])
                if not user:
                    await message.answer(f"❌ Користувача «{parts[1]}» не знайдено.")
                    return
                amount_usd = Decimal(str(round(stars * settings.STAR_DISPLAY_USD, 4)))
                bal_before = user.balance_stars
                user.balance_stars = user.balance_stars + stars
                user.balance_usd   = user.balance_usd + amount_usd
                s.add(TopUp(
                    user_id=user.id,
                    amount_usd=amount_usd,
                    amount_stars=stars,
                    admin_id=message.from_user.id,
                    method="admin",
                    charge_id=charge_id,
                ))
    except IntegrityError:
        log.warning("ADMIN TOPUP DUPLICATE: charge_id=%s — skipped", charge_id)
        await message.answer(
            f"⚠️ Це поповнення вже було зараховано (дублікат).\n"
            f"<code>{charge_id}</code>",
            parse_mode="HTML"
        )
        return

    log.info("ADMIN TOPUP: admin=%s user=%s stars=+%s balance %s→%s charge=%s",
             message.from_user.id, user.id, stars, bal_before, user.balance_stars, charge_id)

    name = user.username or str(user.id)
    await message.answer(
        f"✅ Баланс поповнено\n\n"
        f"👤 @{name} (ID: <code>{user.id}</code>)\n"
        f"➕ +⭐{stars} (~${float(amount_usd):.2f})\n"
        f"💰 Новий баланс: ⭐{user.balance_stars}\n"
        f"🆔 <code>{charge_id}</code>",
        parse_mode="HTML"
    )


@router.message(Command("deduct"), IsAdmin())
async def cmd_deduct(message: Message) -> None:
    if not _is_admin(message.from_user.id):
        return

    parts = (message.text or "").split()
    if len(parts) != 3:
        await message.answer("Використання: /deduct «user_id» «зірки»\nПриклад: /deduct 123456789 100", parse_mode=None)
        return

    try:
        stars = int(parts[2])
        if stars <= 0:
            raise ValueError
    except (ValueError, Exception):
        await message.answer("❌ Невірний формат. Приклад: /deduct 123456789 100", parse_mode=None)
        return

    async with AsyncSessionLocal() as s:
        async with s.begin():
            user = await _find_user(s, parts[1])
            if not user:
                await message.answer(f"❌ Користувача «{parts[1]}» не знайдено.")
                return
            if user.balance_stars < stars:
                await message.answer(
                    f"❌ Недостатньо зірок. Баланс: ⭐{user.balance_stars}, списати: ⭐{stars}"
                )
                return
            amount_usd = Decimal(str(round(stars * settings.STAR_DISPLAY_USD, 4)))
            user.balance_stars = user.balance_stars - stars
            user.balance_usd   = max(Decimal(0), user.balance_usd - amount_usd)

    name = user.username or str(user.id)
    await message.answer(
        f"✅ Баланс списано\n\n"
        f"👤 @{name} (ID: <code>{user.id}</code>)\n"
        f"➖ -⭐{stars} (~${float(amount_usd):.2f})\n"
        f"💰 Новий баланс: ⭐{user.balance_stars}",
        parse_mode="HTML"
    )


@router.message(Command("balance"), IsAdmin())
async def cmd_balance(message: Message) -> None:
    if not _is_admin(message.from_user.id):
        return

    parts = (message.text or "").split()
    if len(parts) != 2:
        await message.answer("Використання: /balance «user_id»", parse_mode=None)
        return

    async with AsyncSessionLocal() as s:
        user = await _find_user(s, parts[1])
        if not user:
            await message.answer(f"❌ Користувача «{parts[1]}» не знайдено.")
            return
        orders_count = await s.scalar(select(func.count(Order.id)).where(Order.user_id == user.id))
        total_spent = await s.scalar(
            select(func.sum(Order.price_usd)).where(Order.user_id == user.id, Order.status == "delivered")
        ) or Decimal(0)

    name = user.username or str(user.id)
    await message.answer(
        f"👤 @{name} (ID: <code>{user.id}</code>)\n"
        f"💰 Баланс: <b>${float(user.balance_usd):.2f}</b>\n"
        f"📦 Замовлень: {orders_count}\n"
        f"💳 Витрачено всього: ${float(total_spent):.2f}",
        parse_mode="HTML"
    )


@router.message(Command("stats"), IsAdmin())
async def cmd_stats(message: Message) -> None:
    if not _is_admin(message.from_user.id):
        return

    async with AsyncSessionLocal() as s:
        total_users = await s.scalar(select(func.count(User.id))) or 0

        total_revenue = await s.scalar(
            select(func.sum(Order.price_usd)).where(Order.status == "delivered")
        ) or Decimal(0)

        total_cost = await s.scalar(
            select(func.sum(Order.cost_usd)).where(Order.status == "delivered")
        ) or Decimal(0)

        total_orders = await s.scalar(
            select(func.count(Order.id)).where(Order.status == "delivered")
        ) or 0

        total_topups_amount = await s.scalar(select(func.sum(TopUp.amount_usd))) or Decimal(0)
        total_topups_count = await s.scalar(select(func.count(TopUp.id))) or 0

        # По категоріях
        from sqlalchemy import text
        cats_result = await s.execute(
            select(Order.category, func.count(Order.id), func.sum(Order.price_usd))
            .where(Order.status == "delivered")
            .group_by(Order.category)
        )
        cats = cats_result.all()

    profit = total_revenue - total_cost

    lines = [
        "📊 <b>Статистика магазину</b>\n",
        f"👥 Користувачів: <b>{total_users}</b>",
        f"📦 Замовлень: <b>{total_orders}</b>",
        "",
        f"💳 Поповнень: {total_topups_count} шт → <b>${float(total_topups_amount):.2f}</b>",
        f"💰 Дохід (продажі): <b>${float(total_revenue):.2f}</b>",
        f"💸 Витрати (Lolz): ${float(total_cost):.2f}",
        f"📈 Прибуток: <b>${float(profit):.2f}</b>",
    ]

    if cats:
        from lemur_shop.services.lolz_shop import CATEGORIES as _CATS
        lines.append("\n🗂 <b>По категоріях:</b>")
        for cat_key, cnt, rev in cats:
            info = _CATS.get(cat_key or "", {})
            flag = info.get("flag", "")
            title = info.get("title", (cat_key or "?").upper())
            lines.append(f"  {flag} {title}: {cnt} шт — ${float(rev or 0):.2f}")

    await message.answer("\n".join(lines), parse_mode="HTML")


@router.message(Command("ban"), IsAdmin())
async def cmd_ban(message: Message) -> None:
    if not _is_admin(message.from_user.id):
        return
    parts = (message.text or "").split()
    if len(parts) != 2:
        await message.answer("Використання: /ban «user_id або @username»", parse_mode=None)
        return
    async with AsyncSessionLocal() as s:
        async with s.begin():
            user = await _find_user(s, parts[1])
            if not user:
                await message.answer(f"❌ Користувача «{parts[1]}» не знайдено.")
                return
            user.is_banned = True
    name = user.username or str(user.id)
    await message.answer(f"🚫 @{name} (<code>{user.id}</code>) заблоковано.", parse_mode="HTML")


@router.message(Command("unban"), IsAdmin())
async def cmd_unban(message: Message) -> None:
    if not _is_admin(message.from_user.id):
        return
    parts = (message.text or "").split()
    if len(parts) != 2:
        await message.answer("Використання: /unban «user_id або @username»", parse_mode=None)
        return
    async with AsyncSessionLocal() as s:
        async with s.begin():
            user = await _find_user(s, parts[1])
            if not user:
                await message.answer(f"❌ Користувача «{parts[1]}» не знайдено.")
                return
            user.is_banned = False
    name = user.username or str(user.id)
    await message.answer(f"✅ @{name} (<code>{user.id}</code>) розблоковано.", parse_mode="HTML")


@router.message(Command("topups"), IsAdmin())
async def cmd_topups(message: Message) -> None:
    if not _is_admin(message.from_user.id):
        return

    parts = (message.text or "").split()
    if len(parts) != 2:
        await message.answer("Використання: /topups «user_id або @username»", parse_mode=None)
        return

    async with AsyncSessionLocal() as s:
        user = await _find_user(s, parts[1])
        if not user:
            await message.answer(f"❌ Користувача «{parts[1]}» не знайдено.")
            return

        rows = (await s.execute(
            select(TopUp)
            .where(TopUp.user_id == user.id)
            .order_by(TopUp.created_at.desc())
            .limit(15)
        )).scalars().all()

    name = user.username or str(user.id)
    if not rows:
        await message.answer(f"@{name}: поповнень немає.")
        return

    METHOD_LABELS = {"stars": "⭐ Stars", "crypto": "💎 Crypto", "admin": "👤 Адмін"}

    lines = [f"📋 Поповнення @{name} (ID: <code>{user.id}</code>) — останні {len(rows)}:\n"]
    for t in rows:
        method_label = METHOD_LABELS.get(t.method or "admin", t.method or "?")
        charge = f"\n   charge: <code>{t.charge_id}</code>" if t.charge_id else ""
        admin_note = f" | admin={t.admin_id}" if t.admin_id and t.admin_id > 0 else ""
        lines.append(
            f"• {t.created_at.strftime('%d.%m %H:%M')} — {method_label}"
            f" | <b>+⭐{t.amount_stars}</b>{admin_note}{charge}"
        )

    lines.append(f"\n💰 Поточний баланс: <b>⭐{user.balance_stars}</b>")
    await message.answer("\n".join(lines), parse_mode="HTML")


@router.message(Command("myid"), IsAdmin())
async def cmd_myid(message: Message) -> None:
    await message.answer(f"Ваш ID: <code>{message.from_user.id}</code>", parse_mode="HTML")


@router.message(Command("platega_check"), IsAdmin())
async def cmd_platega_check(message: Message) -> None:
    """Ручна звірка застряглого СБП-платежу: /platega_check «tx_id».
    Перезапитує статус у Platega й, якщо оплачено, зараховує (ідемпотентно)."""
    parts = (message.text or "").split()
    if len(parts) != 2:
        await message.answer(
            "Використання: /platega_check «tx_id»\n"
            "tx_id — ID транзакції з дешборду Platega.", parse_mode=None)
        return
    tx_id = parts[1].strip()
    # Ліниво, щоб уникнути циклічного імпорту з server.
    from lemur_shop.server import _platega_query, _platega_credit, PLATEGA_PAID_STATES

    q = await _platega_query(tx_id)
    if q is None:
        await message.answer(
            f"❌ Не вдалося отримати статус транзакції <code>{tx_id}</code> у Platega.\n"
            f"Перевір tx_id або зарахуй вручну: /topup «user_id» «зірки»",
            parse_mode="HTML")
        return
    status = str(q.get("status") or q.get("state") or "").upper()
    payload = str(q.get("payload") or "")
    if status not in PLATEGA_PAID_STATES:
        await message.answer(
            f"ℹ️ Транзакція <code>{tx_id}</code> має статус <b>{status or '—'}</b> — не оплачено.",
            parse_mode="HTML")
        return
    ok, msg = await _platega_credit(tx_id, payload)
    if ok:
        await message.answer(f"✅ {msg}\n<code>{tx_id}</code>", parse_mode="HTML")
    else:
        await message.answer(f"⚠️ {msg}", parse_mode="HTML")


# ─── Партнёрська програма ───────────────────────────────────────────────────────

@router.message(Command("partner_add"), IsAdmin())
async def cmd_partner_add(message: Message) -> None:
    parts = (message.text or "").split()
    if len(parts) < 2:
        await message.answer("Використання: /partner_add «user_id або @username»", parse_mode=None)
        return
    async with AsyncSessionLocal() as s:
        async with s.begin():
            user = await _find_user(s, parts[1])
            if not user:
                await message.answer(f"❌ Користувача «{parts[1]}» не знайдено.")
                return
            user.is_partner = True
            name = user.username or user.full_name or str(user.id)
            uid = user.id
    await message.answer(f"🤝 @{name} (<code>{uid}</code>) тепер ПАРТНЁР.\nУ нього замість «Реферали» з'явиться «Партнёрка».", parse_mode="HTML")
    try:
        await message.bot.send_message(uid, "🤝 <b>Вам выдан статус партнёра!</b>\n\nОткройте вкладку «Партнёрка» в приложении — создавайте ссылки и зарабатывайте с покупок ваших рефералов.", parse_mode="HTML")
    except Exception:
        pass


@router.message(Command("partner_remove"), IsAdmin())
async def cmd_partner_remove(message: Message) -> None:
    parts = (message.text or "").split()
    if len(parts) < 2:
        await message.answer("Використання: /partner_remove «user_id або @username»", parse_mode=None)
        return
    async with AsyncSessionLocal() as s:
        async with s.begin():
            user = await _find_user(s, parts[1])
            if not user:
                await message.answer(f"❌ Користувача «{parts[1]}» не знайдено.")
                return
            user.is_partner = False
            name = user.username or user.full_name or str(user.id)
            uid = user.id
    await message.answer(f"➖ @{name} (<code>{uid}</code>) більше не партнёр.", parse_mode="HTML")


@router.message(Command("partner"), IsAdmin())
async def cmd_partner_info(message: Message) -> None:
    from lemur_shop.db.models import PartnerEarning
    parts = (message.text or "").split()
    if len(parts) < 2:
        await message.answer("Використання: /partner «user_id або @username»", parse_mode=None)
        return
    async with AsyncSessionLocal() as s:
        user = await _find_user(s, parts[1])
        if not user:
            await message.answer(f"❌ Користувача «{parts[1]}» не знайдено.")
            return
        invited = await s.scalar(select(func.count()).where(User.referred_by_id == user.id)) or 0
        earned = await s.scalar(select(func.coalesce(func.sum(PartnerEarning.amount_usd), 0)).where(PartnerEarning.partner_id == user.id)) or 0
        name = user.username or user.full_name or str(user.id)
    status = "✅ партнёр" if user.is_partner else "— не партнёр"
    await message.answer(
        f"🤝 <b>Партнёр @{name}</b> (<code>{user.id}</code>)\n\n"
        f"Статус: {status}\n"
        f"Запрошено: <b>{invited}</b>\n"
        f"Зароблено всього: <b>${float(earned):.2f}</b>\n"
        f"Баланс: <b>${float(user.partner_balance_usd or 0):.2f}</b>\n"
        f"Виплачено: <b>${float(user.partner_paid_usd or 0):.2f}</b>",
        parse_mode="HTML",
    )
