from __future__ import annotations

import secrets
import string

from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.types import (
    CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message, WebAppInfo
)

from lemur_shop.config import settings
from lemur_shop.db.models import User
from lemur_shop.db.session import AsyncSessionLocal
from lemur_shop.i18n import t
from lemur_shop.keyboards.inline import lang_keyboard
from lemur_shop.services.referral import get_referrer_by_code

router = Router()

_CHARS = string.ascii_uppercase + string.digits


async def _make_code(session) -> str:
    from sqlalchemy import select
    for _ in range(10):
        code = "".join(secrets.choice(_CHARS) for _ in range(8))
        if not await session.scalar(select(User).where(User.referral_code == code).limit(1)):
            return code
    raise RuntimeError("ref code collision")


def _main_menu(lang: str, is_admin: bool = False) -> InlineKeyboardMarkup:
    """Якщо є WEBAPP_URL — кнопка відкриває Mini App, інакше inline меню."""
    rows = []
    if settings.WEBAPP_URL:
        rows.append([InlineKeyboardButton(
            text="🛍 Відкрити магазин",
            web_app=WebAppInfo(url=settings.WEBAPP_URL),
        )])
    else:
        rows.append([InlineKeyboardButton(text=t(lang, "btn_shop"),     callback_data="menu:shop")])
        rows.append([
            InlineKeyboardButton(text=t(lang, "btn_profile"),  callback_data="menu:profile"),
            InlineKeyboardButton(text=t(lang, "btn_referral"), callback_data="menu:referral"),
        ])
        if is_admin:
            rows.append([InlineKeyboardButton(text=t(lang, "btn_admin"), callback_data="menu:admin")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
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
                created = True
            else:
                user.username = message.from_user.username
                created = False
            lang = user.lang

    if created:
        await message.answer(t("ru", "choose_lang"), reply_markup=lang_keyboard())
    else:
        await message.answer(
            t(lang, "welcome_back"),
            reply_markup=_main_menu(lang, user.is_admin),
            parse_mode="HTML",
        )


@router.callback_query(F.data.startswith("lang:"))
async def cb_set_lang(callback: CallbackQuery) -> None:
    lang = callback.data.split(":")[1]
    async with AsyncSessionLocal() as s:
        async with s.begin():
            user = await s.get(User, callback.from_user.id)
            if user:
                user.lang = lang
                is_admin = user.is_admin

    await callback.message.edit_text(
        t(lang, "welcome_new"),
        reply_markup=_main_menu(lang, is_admin),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "menu:main")
async def cb_main_menu(callback: CallbackQuery) -> None:
    async with AsyncSessionLocal() as s:
        user = await s.get(User, callback.from_user.id)
    lang = user.lang if user else "ru"
    is_admin = user.is_admin if user else False
    await callback.message.edit_text(
        t(lang, "welcome_back"),
        reply_markup=_main_menu(lang, is_admin),
        parse_mode="HTML",
    )
