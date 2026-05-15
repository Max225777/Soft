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
        "Цифровой магазин TG-аккаунтов.\n\n"
        "Нажмите кнопку ниже, чтобы открыть магазин."
    ),
    "ua": (
        "🦎 <b>Лемур</b>\n\n"
        "Цифровий магазин TG-акаунтів.\n\n"
        "Натисніть кнопку нижче, щоб відкрити магазин."
    ),
    "en": (
        "🦎 <b>Lemur</b>\n\n"
        "Digital shop for TG accounts.\n\n"
        "Press the button below to open the shop."
    ),
}

BTN_LABEL = {"ru": "🛍 Открыть магазин", "ua": "🛍 Відкрити магазин", "en": "🛍 Open shop"}


def _open_keyboard(lang: str) -> InlineKeyboardMarkup:
    label = BTN_LABEL.get(lang, BTN_LABEL["ru"])
    if settings.WEBAPP_URL:
        btn = InlineKeyboardButton(text=label, web_app=WebAppInfo(url=settings.WEBAPP_URL))
    else:
        btn = InlineKeyboardButton(text=label, callback_data="menu:shop")
    return InlineKeyboardMarkup(inline_keyboard=[[btn]])
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
