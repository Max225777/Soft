from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    LabeledPrice,
    Message,
)

from lemur_shop.config import settings

log = logging.getLogger(__name__)
router = Router()

# USD пресети для поповнення через Stars
TOPUP_PRESETS = [
    ("$1", 1.0),
    ("$2", 2.0),
    ("$5", 5.0),
    ("$10", 10.0),
    ("$25", 25.0),
]

TOPUP_TEXT = {
    "ru": "⭐ Пополнение баланса через Telegram Stars\n\nВыберите сумму:",
    "ua": "⭐ Поповнення балансу через Telegram Stars\n\nОберіть суму:",
    "en": "⭐ Top up balance via Telegram Stars\n\nSelect amount:",
}


def _topup_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        InlineKeyboardButton(text=label, callback_data=f"stars_amount:{usd}")
        for label, usd in TOPUP_PRESETS
    ]
    rows = [buttons[:3], buttons[3:]]
    return InlineKeyboardMarkup(inline_keyboard=rows)


@router.message(Command("topup"))
async def cmd_topup(message: Message) -> None:
    from lemur_shop.db.models import User
    from lemur_shop.db.session import AsyncSessionLocal

    lang = "ru"
    async with AsyncSessionLocal() as s:
        user = await s.get(User, message.from_user.id)
        if user and user.lang in TOPUP_TEXT:
            lang = user.lang

    await message.answer(TOPUP_TEXT[lang], reply_markup=_topup_keyboard())


@router.callback_query(F.data.startswith("stars_amount:"))
async def cb_stars_amount(callback: CallbackQuery) -> None:
    try:
        amount_usd = float(callback.data.split(":")[1])
    except (IndexError, ValueError):
        await callback.answer("Помилка", show_alert=True)
        return

    stars = max(1, round(amount_usd * settings.STARS_PER_USD))
    user_id = callback.from_user.id

    await callback.answer()
    await callback.message.answer_invoice(
        title="Поповнення балансу Лемур",
        description=f"Зарахування ${amount_usd:.2f} на баланс магазину",
        payload=f"stars_topup:{user_id}:{amount_usd}",
        currency="XTR",
        prices=[LabeledPrice(label="Telegram Stars", amount=stars)],
    )
