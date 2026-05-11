from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery

from bot.config import settings
from bot.db.models import User
from bot.db.session import AsyncSessionLocal
from bot.keyboards.inline import back_keyboard
from bot.services import referral as ref_svc
from bot.services.balance import get_balance_usd
from bot.utils.currency import format_amount

router = Router()


@router.callback_query(F.data == "menu:profile")
async def cb_profile(callback: CallbackQuery) -> None:
    async with AsyncSessionLocal() as session:
        user = await session.get(User, callback.from_user.id)
        if not user:
            await callback.answer("Спочатку введіть /start")
            return

        balance_usd = await get_balance_usd(session, user.id)
        orders_count = len(user.orders) if user.orders else 0

    region_labels = {"UA": "🇺🇦 Україна", "RU": "🇷🇺 Росія", "KZ": "🇰🇿 Казахстан"}
    currency_labels = {"USD": "$ USD", "UAH": "₴ UAH", "RUB": "₽ RUB", "KZT": "₸ KZT"}

    name = user.full_name or user.username or str(user.id)
    username_str = f"@{user.username}" if user.username else "—"

    text = (
        f"👤 <b>Профіль</b>\n\n"
        f"<b>{name}</b>\n"
        f"{username_str}\n\n"
        f"📍 Регіон: {region_labels.get(user.region, user.region)}\n"
        f"💱 Валюта: {currency_labels.get(user.display_currency, user.display_currency)}\n"
        f"💳 Баланс: <b>{format_amount(balance_usd, user.display_currency)}</b>\n"
        f"🛍 Замовлень: {orders_count}\n"
    )

    await callback.message.edit_text(text, reply_markup=back_keyboard(), parse_mode="HTML")


@router.callback_query(F.data == "menu:referral")
async def cb_referral(callback: CallbackQuery) -> None:
    async with AsyncSessionLocal() as session:
        user = await session.get(User, callback.from_user.id)
        if not user:
            await callback.answer("Спочатку введіть /start")
            return

        stats = await ref_svc.get_referral_stats(session, user.id)

    bot_username = (await callback.bot.get_me()).username
    ref_link = f"https://t.me/{bot_username}?start={user.referral_code}"

    text = (
        f"👥 <b>Реферальна програма</b>\n\n"
        f"Ваш бонус: <b>+{stats['bonus_percent']:.0f}%</b> з кожної покупки реферала\n\n"
        f"📊 Статистика:\n"
        f"  • Запрошено: <b>{stats['referrals_count']}</b> чол.\n"
        f"  • Зароблено: <b>{format_amount(stats['total_earned_usd'], 'USD')}</b>\n\n"
        f"🔗 Ваше посилання:\n"
        f"<code>{ref_link}</code>\n\n"
        f"<i>Натисніть щоб скопіювати</i>"
    )

    await callback.message.edit_text(text, reply_markup=back_keyboard(), parse_mode="HTML")
