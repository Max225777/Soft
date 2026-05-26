from __future__ import annotations

import logging
import secrets
import string

from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.types import (
    CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message, WebAppInfo,
)

from lemur_shop.config import settings
from lemur_shop.db.models import User
from lemur_shop.db.session import AsyncSessionLocal
from lemur_shop.services.referral import get_referrer_by_code

log = logging.getLogger(__name__)
router = Router()

_CHARS = string.ascii_uppercase + string.digits

WELCOME = {
    "ru": (
        "🦎 <b>Лемур Шоп</b>\n\n"
        "Привет! Добро пожаловать в автоматический цифровой магазин.\n\n"
        "🛒 <b>Что есть в магазине:</b>\n"
        "📱 Telegram аккаунты — 🇺🇸 🇰🇿 🇺🇦\n"
        "⭐ Аккаунты США от <b>25 звёзд</b>\n\n"
        "💳 <b>Способы оплаты:</b>\n"
        "⭐ Telegram Stars\n"
        "🤑 CryptoBot (USDT и др.)\n\n"
        "⚡️ Выдача мгновенная, работаем 24/7.\n\n"
        "👇 Нажми кнопку и открывай каталог:"
    ),
    "ua": (
        "🦎 <b>Лемур Шоп</b>\n\n"
        "Привіт! Ласкаво просимо до автоматичного цифрового магазину.\n\n"
        "🛒 <b>Що є в магазині:</b>\n"
        "📱 Telegram акаунти — 🇺🇸 🇰🇿 🇺🇦\n"
        "⭐ Акаунти США від <b>25 зірок</b>\n\n"
        "💳 <b>Способи оплати:</b>\n"
        "⭐ Telegram Stars\n"
        "🤑 CryptoBot (USDT та ін.)\n\n"
        "⚡️ Видача миттєва, працюємо 24/7.\n\n"
        "👇 Натисни кнопку і відкривай каталог:"
    ),
    "en": (
        "🦎 <b>Lemur Shop</b>\n\n"
        "Hey! Welcome to our automated digital store.\n\n"
        "🛒 <b>What's available:</b>\n"
        "📱 Telegram accounts — 🇺🇸 🇰🇿 🇺🇦\n"
        "⭐ US accounts from <b>25 stars</b>\n\n"
        "💳 <b>Payment methods:</b>\n"
        "⭐ Telegram Stars\n"
        "🤑 CryptoBot (USDT etc.)\n\n"
        "⚡️ Instant delivery, 24/7.\n\n"
        "👇 Press the button to open the catalogue:"
    ),
}

BTN_LABEL = {"ru": "🛍 Открыть каталог", "ua": "🛍 Відкрити каталог", "en": "🛍 Open catalogue"}


def _open_keyboard(lang: str) -> InlineKeyboardMarkup:
    label = BTN_LABEL.get(lang, BTN_LABEL["ru"])
    if settings.WEBAPP_URL:
        url = settings.WEBAPP_URL.rstrip('/') + '?v=3'
        btn = InlineKeyboardButton(text=label, web_app=WebAppInfo(url=url))
    else:
        btn = InlineKeyboardButton(text=label, callback_data="menu:shop")
    return InlineKeyboardMarkup(inline_keyboard=[[btn]])


async def _make_code(session) -> str:
    from sqlalchemy import select
    for _ in range(10):
        code = "".join(secrets.choice(_CHARS) for _ in range(8))
        if not await session.scalar(select(User).where(User.referral_code == code).limit(1)):
            return code
    raise RuntimeError("ref code collision")


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    log.info("/start від user_id=%s", message.from_user.id)
    parts = (message.text or "").split(maxsplit=1)
    ref_code = parts[1].strip() if len(parts) > 1 else None

    try:
        async with AsyncSessionLocal() as s:
            async with s.begin():
                user = await s.get(User, message.from_user.id)
                if user is None:
                    referrer = await get_referrer_by_code(s, ref_code) if ref_code else None
                    user = User(
                        id=message.from_user.id,
                        username=message.from_user.username,
                        full_name=message.from_user.full_name or "",
                        referral_code=await _make_code(s),
                        referred_by_id=referrer.id if referrer else None,
                    )
                    s.add(user)
                    lang = "ru"
                else:
                    user.username = message.from_user.username
                    lang = user.lang if user.lang in WELCOME else "ru"
    except Exception as e:
        log.error("/start DB error for user=%s: %s", message.from_user.id, e)
        lang = "ru"

    await message.answer(WELCOME[lang], reply_markup=_open_keyboard(lang), parse_mode="HTML")
