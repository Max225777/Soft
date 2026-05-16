from __future__ import annotations

from decimal import Decimal

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy import func, select

from lemur_shop.config import settings
from lemur_shop.db.models import Order, TopUp, User
from lemur_shop.db.session import AsyncSessionLocal

router = Router()


def _is_admin(user_id: int) -> bool:
    return user_id in settings.ADMIN_IDS


async def _find_user(session, query: str) -> User | None:
    q = query.lstrip("@")
    if q.isdigit():
        return await session.get(User, int(q))
    result = await session.execute(select(User).where(User.username == q).limit(1))
    return result.scalar_one_or_none()


@router.message(Command("topup"))
async def cmd_topup(message: Message) -> None:
    if not _is_admin(message.from_user.id):
        return

    parts = (message.text or "").split()
    if len(parts) != 3:
        await message.answer("Використання: /topup <user_id> <сума>\nПриклад: /topup 123456789 5.00")
        return

    try:
        amount = Decimal(parts[2])
        if amount <= 0:
            raise ValueError
    except (ValueError, Exception):
        await message.answer("❌ Невірний формат. Приклад: /topup 123456789 5.00")
        return

    async with AsyncSessionLocal() as s:
        async with s.begin():
            user = await _find_user(s, parts[1])
            if not user:
                await message.answer(f"❌ Користувача «{parts[1]}» не знайдено.")
                return
            user.balance_usd = user.balance_usd + amount
            s.add(TopUp(
                user_id=user.id,
                amount_usd=amount,
                admin_id=message.from_user.id,
            ))

    name = user.username or str(user.id)
    await message.answer(
        f"✅ Баланс поповнено\n\n"
        f"👤 @{name} (ID: <code>{user.id}</code>)\n"
        f"➕ +${amount:.2f}\n"
        f"💰 Новий баланс: ${float(user.balance_usd):.2f}",
        parse_mode="HTML"
    )


@router.message(Command("balance"))
async def cmd_balance(message: Message) -> None:
    if not _is_admin(message.from_user.id):
        return

    parts = (message.text or "").split()
    if len(parts) != 2:
        await message.answer("Використання: /balance <user_id>")
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


@router.message(Command("stats"))
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


@router.message(Command("ban"))
async def cmd_ban(message: Message) -> None:
    if not _is_admin(message.from_user.id):
        return
    parts = (message.text or "").split()
    if len(parts) != 2:
        await message.answer("Використання: /ban <user_id або @username>")
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


@router.message(Command("unban"))
async def cmd_unban(message: Message) -> None:
    if not _is_admin(message.from_user.id):
        return
    parts = (message.text or "").split()
    if len(parts) != 2:
        await message.answer("Використання: /unban <user_id або @username>")
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


@router.message(Command("myid"))
async def cmd_myid(message: Message) -> None:
    await message.answer(f"Ваш ID: <code>{message.from_user.id}</code>", parse_mode="HTML")
