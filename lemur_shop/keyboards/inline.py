from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from lemur_shop.i18n import t


def lang_keyboard() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(
        InlineKeyboardButton(text="🇺🇦 Українська", callback_data="lang:ua"),
        InlineKeyboardButton(text="🇷🇺 Русский",    callback_data="lang:ru"),
    )
    return b.as_markup()


def main_menu(lang: str, is_admin: bool = False) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text=t(lang, "btn_shop"),    callback_data="menu:shop"))
    b.row(
        InlineKeyboardButton(text=t(lang, "btn_profile"),  callback_data="menu:profile"),
        InlineKeyboardButton(text=t(lang, "btn_referral"), callback_data="menu:referral"),
    )
    if is_admin:
        b.row(InlineKeyboardButton(text=t(lang, "btn_admin"), callback_data="menu:admin"))
    return b.as_markup()


def categories_keyboard(lang: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text=t(lang, "cat_accounts"), callback_data="cat:tg_account"))
    b.row(InlineKeyboardButton(text=t(lang, "cat_stars"),    callback_data="cat:stars"))
    b.row(InlineKeyboardButton(text=t(lang, "cat_premium"),  callback_data="cat:premium"))
    b.row(InlineKeyboardButton(text=t(lang, "btn_back"),     callback_data="menu:main"))
    return b.as_markup()


def products_keyboard(lang: str, products: list) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for p in products:
        b.row(InlineKeyboardButton(
            text=f"{p.title} — ${p.price_usd}",
            callback_data=f"buy:{p.id}",
        ))
    b.row(InlineKeyboardButton(text=t(lang, "btn_back"), callback_data="menu:shop"))
    return b.as_markup()


def back_to_main(lang: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text=t(lang, "btn_back"), callback_data="menu:main"))
    return b.as_markup()


def admin_keyboard(lang: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text=t(lang, "btn_orders"), callback_data="admin:orders"))
    b.row(InlineKeyboardButton(text=t(lang, "btn_back"),   callback_data="menu:main"))
    return b.as_markup()


def orders_keyboard(lang: str, orders: list) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for o in orders:
        if o.status == "pending":
            b.row(InlineKeyboardButton(
                text=f"#{o.id} ${o.price_usd} — {t(lang, 'btn_deliver')}",
                callback_data=f"deliver:{o.id}",
            ))
    b.row(InlineKeyboardButton(text=t(lang, "btn_back"), callback_data="menu:admin"))
    return b.as_markup()
