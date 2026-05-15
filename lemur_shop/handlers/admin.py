from __future__ import annotations

from decimal import Decimal

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from sqlalchemy import func, select

from lemur_shop.config import settings
from lemur_shop.db.models import Order, User
from lemur_shop.db.session import AsyncSessionLocal

router = Router()


def _is_admin(user_id: int) -> bool:
    return user_id in settings.ADMIN_IDS


@router.message(Command("topup"))
async def cmd_topup(message: Message) -> None:
    if not _is_admin(message.from_user.id):
        return

    parts = (message.text or "").split()
    if len(parts) != 3:
        await message.answer("Використання: /topup <user_id> <сума>\nПриклад: /topup 123456789 5.00")
        return

    try:
        target_id = int(parts[1])
        amount = Decimal(parts[2])
        if amount <= 0:
            raise ValueError
    except (ValueError, Exception):
        await message.answer("❌ Невірний формат. Приклад: /topup 123456789 5.00")
        return

    async with AsyncSessionLocal() as s:
        async with s.begin():
            user = await s.get(User, target_id)
            if not user:
                await message.answer(f"❌ Користувача {target_id} не знайдено.")
                return
            user.balance_usd = user.balance_usd + amount

    name = user.username or str(target_id)
    await message.answer(
        f"✅ Баланс поповнено\n\n"
        f"👤 @{name} (ID: {target_id})\n"
        f"➕ +${amount:.2f}\n"
        f"💰 Новий баланс: ${float(user.balance_usd):.2f}"
    )


@router.message(Command("balance"))
async def cmd_balance(message: Message) -> None:
    if not _is_admin(message.from_user.id):
        return

    parts = (message.text or "").split()
    if len(parts) != 2:
        await message.answer("Використання: /balance <user_id>")
        return

    try:
        target_id = int(parts[1])
    except ValueError:
        await message.answer("❌ Невірний user_id")
        return

    async with AsyncSessionLocal() as s:
        user = await s.get(User, target_id)
        if not user:
            await message.answer(f"❌ Користувача {target_id} не знайдено.")
            return
        orders_count = await s.scalar(select(func.count(Order.id)).where(Order.user_id == target_id))

    name = user.username or str(target_id)
    await message.answer(
        f"👤 @{name} (ID: {target_id})\n"
        f"💰 Баланс: ${float(user.balance_usd):.2f}\n"
        f"📦 Замовлень: {orders_count}"
    )


@router.message(Command("myid"))
async def cmd_myid(message: Message) -> None:
    await message.answer(f"Ваш ID: <code>{message.from_user.id}</code>", parse_mode="HTML")
