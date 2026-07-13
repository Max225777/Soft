from __future__ import annotations

import logging
import secrets
import string

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message, WebAppInfo,
)
from sqlalchemy import func, select as _select

from lemur_shop.config import settings
from lemur_shop.db.models import Order, User
from lemur_shop.db.session import AsyncSessionLocal
from lemur_shop.services.referral import resolve_referral

_REF_JOINED_MSG = {
    "ru": "👤 <b>Ваш реферал зашёл в бот!</b>",
    "ua": "👤 <b>Ваш реферал зайшов у бот!</b>",
    "en": "👤 <b>Your referral joined the bot!</b>",
}

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
INFO_BTN_LABEL = {"ru": "ℹ️ Информация о нас", "ua": "ℹ️ Інформація про нас", "en": "ℹ️ About us"}


def _open_keyboard(lang: str) -> InlineKeyboardMarkup:
    label = BTN_LABEL.get(lang, BTN_LABEL["ru"])
    if settings.WEBAPP_URL:
        url = settings.WEBAPP_URL.rstrip('/') + '?v=3'
        btn = InlineKeyboardButton(text=label, web_app=WebAppInfo(url=url))
    else:
        btn = InlineKeyboardButton(text=label, callback_data="menu:shop")
    info_btn = InlineKeyboardButton(text=INFO_BTN_LABEL.get(lang, INFO_BTN_LABEL["ru"]), callback_data="info:about")
    return InlineKeyboardMarkup(inline_keyboard=[[btn], [info_btn]])


async def _build_info() -> tuple[str, InlineKeyboardMarkup]:
    """Текст «Информация о нас» + клавіатура з документами/контактами."""
    sup = settings.SUPPORT_USERNAME.lstrip("@")
    rev = settings.REVIEWS_CHANNEL_USERNAME.lstrip("@")
    ch = settings.CHANNEL_USERNAME.lstrip("@")
    base = settings.WEBAPP_URL.rstrip("/") if settings.WEBAPP_URL else ""

    try:
        async with AsyncSessionLocal() as s:
            total_users = await s.scalar(_select(func.count()).select_from(User)) or 0
            total_orders = await s.scalar(
                _select(func.count()).select_from(Order).where(Order.status == "delivered")
            ) or 0
    except Exception:
        total_users = 0
        total_orders = 0

    def _num(n: int) -> str:
        return f"{n:,}".replace(",", " ")

    text = (
        "ℹ️ <b>Информация о нас</b>\n\n"
        "🦎 <b>Lemur Shop</b> — магазин цифровых товаров и услуг в Telegram: "
        "продажа TG-аккаунтов и продвижение (подписчики, просмотры, реакции).\n\n"
        f"👥 <b>Всего пользователей:</b> {_num(total_users)}\n"
        f"🛒 <b>Всего покупок:</b> {_num(total_orders)}\n"
        "\n📄 <b>Документы:</b>\n"
        "• Пользовательское соглашение\n"
        "• Политика конфиденциальности\n\n"
        f"💬 <b>Поддержка:</b> @{sup} (личный менеджер, не группа)\n"
    )
    if settings.SUPPORT_EMAIL:
        text += f"✉️ <b>E-mail:</b> {settings.SUPPORT_EMAIL}\n"
    text += (
        f"\n⭐ <b>Отзывы покупателей:</b> @{rev}\n"
        f"📣 <b>Наш канал:</b> @{ch}"
    )

    rows: list[list[InlineKeyboardButton]] = []
    if base.startswith("https://"):
        rows.append([InlineKeyboardButton(text="📄 Соглашение", url=f"{base}/terms"),
                     InlineKeyboardButton(text="🔒 Конфиденциальность", url=f"{base}/privacy")])
        rows.append([InlineKeyboardButton(text="ℹ️ Вся информация", url=f"{base}/info")])
    rows.append([InlineKeyboardButton(text="💬 Поддержка", url=f"https://t.me/{sup}"),
                 InlineKeyboardButton(text="⭐ Отзывы", url=f"https://t.me/{rev}")])
    return text, InlineKeyboardMarkup(inline_keyboard=rows)


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
                    referrer, link_id = await resolve_referral(s, ref_code) if ref_code else (None, None)
                    user = User(
                        id=message.from_user.id,
                        username=message.from_user.username,
                        full_name=message.from_user.full_name or "",
                        referral_code=await _make_code(s),
                        referred_by_id=referrer.id if referrer else None,
                        partner_link_id=link_id,
                    )
                    s.add(user)
                    lang = "ru"
                    # сповіщення рефереру
                    if referrer:
                        try:
                            ref_lang = referrer.lang or "ru"
                            await message.bot.send_message(
                                referrer.id,
                                _REF_JOINED_MSG.get(ref_lang, _REF_JOINED_MSG["ru"]),
                                parse_mode="HTML",
                            )
                        except Exception:
                            pass
                else:
                    user.username = message.from_user.username
                    lang = user.lang if user.lang in WELCOME else "ru"
    except Exception as e:
        log.error("/start DB error for user=%s: %s", message.from_user.id, e)
        lang = "ru"

    await message.answer(WELCOME[lang], reply_markup=_open_keyboard(lang), parse_mode="HTML")


@router.message(Command("info", "инфо", "інфо"))
async def cmd_info(message: Message) -> None:
    text, kb = await _build_info()
    await message.answer(text, reply_markup=kb, parse_mode="HTML")


@router.callback_query(F.data == "info:about")
async def cb_info_about(callback: CallbackQuery) -> None:
    try:
        await callback.answer()
    except Exception:
        pass
    text, kb = await _build_info()
    if callback.message:
        await callback.message.answer(text, reply_markup=kb, parse_mode="HTML")
