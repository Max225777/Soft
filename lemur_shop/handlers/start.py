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

WELCOME_TEXT = (
    "🦎 <b>Лемур</b>\n\n"
    "Цифровой магазин TG-аккаунтов.\n\n"
    "Нажмите кнопку ниже, чтобы открыть магазин."
)


async def _make_code(session) -> str:
    from sqlalchemy import select
    for _ in range(10):
        code = "".join(secrets.choice(_CHARS) for _ in range(8))
        if not await session.scalar(select(User).where(User.referral_code == code).limit(1)):
            return code
    raise RuntimeError("ref code collision")


def _open_keyboard() -> InlineKeyboardMarkup:
    if settings.WEBAPP_URL:
        btn = InlineKeyboardButton(
            text="🛍 Открыть магазин",
            web_app=WebAppInfo(url=settings.WEBAPP_URL),
        )
    else:
        btn = InlineKeyboardButton(text="🛍 Открыть магазин", callback_data="menu:shop")
    return InlineKeyboardMarkup(inline_keyboard=[[btn]])


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

    await message.answer(WELCOME_TEXT, reply_markup=_open_keyboard(), parse_mode="HTML")
