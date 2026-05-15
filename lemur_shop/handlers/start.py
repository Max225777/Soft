from __future__ import annotations

import logging
import secrets
import string

from aiogram import Bot, F, Router
from aiogram.enums import ChatMemberStatus
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

SUB_MSG = {
    "ru": (
        "🦎 <b>Лемур</b>\n\n"
        "Чтобы пользоваться магазином, подпишитесь на наш канал 👇"
    ),
    "ua": (
        "🦎 <b>Лемур</b>\n\n"
        "Щоб користуватись магазином, підпишіться на наш канал 👇"
    ),
    "en": (
        "🦎 <b>Lemur</b>\n\n"
        "To use the shop, please subscribe to our channel 👇"
    ),
}

SUB_OK_MSG = {
    "ru": "✅ Подписка подтверждена! Добро пожаловать.",
    "ua": "✅ Підписку підтверджено! Ласкаво просимо.",
    "en": "✅ Subscription confirmed! Welcome.",
}

SUB_FAIL_MSG = {
    "ru": "❌ Вы ещё не подписались. Подпишитесь и нажмите кнопку снова.",
    "ua": "❌ Ви ще не підписались. Підпишіться і натисніть кнопку знову.",
    "en": "❌ You haven't subscribed yet. Subscribe and try again.",
}

BTN_LABEL = {"ru": "🛍 Открыть каталог", "ua": "🛍 Відкрити каталог", "en": "🛍 Open catalogue"}
BTN_SUB   = {"ru": "📢 Подписаться",     "ua": "📢 Підписатись",      "en": "📢 Subscribe"}
BTN_CHECK = {"ru": "✅ Проверить подписку", "ua": "✅ Перевірити підписку", "en": "✅ Check subscription"}


def _open_keyboard(lang: str) -> InlineKeyboardMarkup:
    label = BTN_LABEL.get(lang, BTN_LABEL["ru"])
    if settings.WEBAPP_URL:
        btn = InlineKeyboardButton(text=label, web_app=WebAppInfo(url=settings.WEBAPP_URL))
    else:
        btn = InlineKeyboardButton(text=label, callback_data="menu:shop")
    return InlineKeyboardMarkup(inline_keyboard=[[btn]])


def _sub_keyboard(lang: str) -> InlineKeyboardMarkup:
    ch = settings.CHANNEL_USERNAME.lstrip("@")
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=BTN_SUB.get(lang, BTN_SUB["ru"]), url=f"https://t.me/{ch}")],
        [InlineKeyboardButton(text=BTN_CHECK.get(lang, BTN_CHECK["ru"]), callback_data="check_sub")],
    ])


async def _is_subscribed(bot: Bot, user_id: int) -> bool:
    if not settings.CHANNEL_USERNAME:
        return True
    try:
        member = await bot.get_chat_member(
            chat_id=settings.CHANNEL_USERNAME, user_id=user_id
        )
        log.info("Sub check user=%s status=%r type=%s", user_id, member.status, type(member).__name__)
        subscribed = member.status in (
            ChatMemberStatus.CREATOR,
            ChatMemberStatus.ADMINISTRATOR,
            ChatMemberStatus.MEMBER,
            ChatMemberStatus.RESTRICTED,
        )
        return subscribed
    except Exception as e:
        log.warning("Sub check failed for user=%s: %s — letting through", user_id, e)
        return True


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
                lang = "ru"
            else:
                user.username = message.from_user.username
                lang = user.lang if user.lang in WELCOME else "ru"

    if await _is_subscribed(message.bot, message.from_user.id):
        await message.answer(WELCOME[lang], reply_markup=_open_keyboard(lang), parse_mode="HTML")
    else:
        await message.answer(SUB_MSG[lang], reply_markup=_sub_keyboard(lang), parse_mode="HTML")


@router.callback_query(F.data == "check_sub")
async def cb_check_sub(call: CallbackQuery) -> None:
    async with AsyncSessionLocal() as s:
        user = await s.get(User, call.from_user.id)
        lang = (user.lang if user and user.lang in WELCOME else "ru")

    if await _is_subscribed(call.bot, call.from_user.id):
        await call.message.edit_text(
            SUB_OK_MSG[lang] + "\n\n" + WELCOME[lang],
            reply_markup=_open_keyboard(lang),
            parse_mode="HTML",
        )
    else:
        await call.answer(SUB_FAIL_MSG[lang], show_alert=True)
