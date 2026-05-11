from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery
from sqlalchemy import func, select

from lemur_shop.db.models import Order, ReferralPayout, User
from lemur_shop.db.session import AsyncSessionLocal
from lemur_shop.i18n import t
from lemur_shop.keyboards.inline import back_to_main, lang_keyboard

router = Router()


@router.callback_query(F.data == "menu:profile")
async def cb_profile(callback: CallbackQuery) -> None:
    async with AsyncSessionLocal() as s:
        user = await s.get(User, callback.from_user.id)
        if not user:
            return
        orders_count = await s.scalar(
            select(func.count()).where(Order.user_id == user.id)
        )
    lang = user.lang
    name = user.full_name or user.username or str(user.id)
    uname = f"@{user.username}" if user.username else "—"
    lang_label = "🇺🇦 Українська" if lang == "ua" else "🇷🇺 Русский"

    text = (
        f"{t(lang, 'profile_title')}\n\n"
        f"<b>{name}</b>  {uname}\n\n"
        f"{t(lang, 'profile_lang')}: {lang_label}\n"
        f"{t(lang, 'profile_bal')}: <b>${user.balance_usd}</b>\n"
        f"{t(lang, 'profile_orders')}: <b>{orders_count}</b>"
    )

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text=t(lang, "btn_change_lang"), callback_data="menu:change_lang"))
    b.row(InlineKeyboardButton(text=t(lang, "btn_back"), callback_data="menu:main"))

    await callback.message.edit_text(text, reply_markup=b.as_markup(), parse_mode="HTML")


@router.callback_query(F.data == "menu:change_lang")
async def cb_change_lang(callback: CallbackQuery) -> None:
    await callback.message.edit_text(t("ru", "choose_lang"), reply_markup=lang_keyboard())


@router.callback_query(F.data == "menu:referral")
async def cb_referral(callback: CallbackQuery) -> None:
    async with AsyncSessionLocal() as s:
        user = await s.get(User, callback.from_user.id)
        if not user:
            return
        ref_count = await s.scalar(
            select(func.count()).where(User.referred_by_id == user.id)
        )
        earned = await s.scalar(
            select(func.coalesce(func.sum(ReferralPayout.bonus_usd), 0))
            .where(ReferralPayout.referrer_id == user.id)
        )
    lang = user.lang
    me = await callback.bot.get_me()
    link = f"https://t.me/{me.username}?start={user.referral_code}"

    text = (
        f"{t(lang, 'ref_title')}\n\n"
        f"{t(lang, 'ref_bonus', pct=5)}\n\n"
        f"{t(lang, 'ref_invited', n=ref_count or 0)}\n"
        f"{t(lang, 'ref_earned', amt=f'{float(earned or 0):.2f}')}\n\n"
        f"{t(lang, 'ref_link')}\n<code>{link}</code>"
    )
    await callback.message.edit_text(text, reply_markup=back_to_main(lang), parse_mode="HTML")
