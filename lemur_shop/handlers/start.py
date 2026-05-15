from __future__ import annotations

import logging
import secrets
import string

from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message, WebAppInfo

from lemur_shop.config import settings
from lemur_shop.db.models import User
from lemur_shop.db.session import AsyncSessionLocal
from lemur_shop.services.referral import get_referrer_by_code

log = logging.getLogger(__name__)
router = Router()

_CHARS = string.ascii_uppercase + string.digits

WELCOME = {
    "ru": (
        "🦎 <b>Лемур</b>\n\n"
        "Добро пожаловать в наш магазин.\n\n"
        "Нажмите кнопку ниже, чтобы открыть каталог."
    ),
    "ua": (
        "🦎 <b>Лемур</b>\n\n"
        "Ласкаво просимо до нашого магазину.\n\n"
        "Натисніть кнопку нижче, щоб відкрити каталог."
    ),
    "en": (
        "🦎 <b>Lemur</b>\n\n"
        "Welcome to our shop.\n\n"
        "Press the button below to open the catalogue."
    ),
}

BTN_LABEL = {"ru": "🛍 Открыть каталог", "ua": "🛍 Відкрити каталог", "en": "🛍 Open catalogue"}


def _open_keyboard(lang: str) -> InlineKeyboardMarkup:
    label = BTN_LABEL.get(lang, BTN_LABEL["ru"])
    if settings.WEBAPP_URL:
        btn = InlineKeyboardButton(text=label, web_app=WebAppInfo(url=settings.WEBAPP_URL))
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
            else:
                user.username = message.from_user.username

    lang = user.lang if user.lang in WELCOME else "ru"
    await message.answer(WELCOME[lang], reply_markup=_open_keyboard(lang), parse_mode="HTML")
