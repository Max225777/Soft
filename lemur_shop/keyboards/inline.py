from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.config import settings
from bot.db.models import Currency, Region


def region_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🇺🇦 Україна", callback_data="region:UA"),
        InlineKeyboardButton(text="🇷🇺 Россия",  callback_data="region:RU"),
        InlineKeyboardButton(text="🇰🇿 Казахстан", callback_data="region:KZ"),
    )
    return builder.as_markup()


def currency_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="$ USD", callback_data="currency:USD"),
        InlineKeyboardButton(text="₴ UAH", callback_data="currency:UAH"),
        InlineKeyboardButton(text="₽ RUB", callback_data="currency:RUB"),
        InlineKeyboardButton(text="₸ KZT", callback_data="currency:KZT"),
    )
    return builder.as_markup()


def main_menu_keyboard(webapp_url: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="🛍 Відкрити магазин",
            web_app=WebAppInfo(url=webapp_url),
        )
    )
    builder.row(
        InlineKeyboardButton(text="💳 Баланс", callback_data="menu:balance"),
        InlineKeyboardButton(text="👤 Профіль", callback_data="menu:profile"),
    )
    builder.row(
        InlineKeyboardButton(text="👥 Реферали", callback_data="menu:referral"),
    )
    return builder.as_markup()


def balance_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="💳 Карта (FreeCassa)", callback_data="deposit:card"),
        InlineKeyboardButton(text="🔷 Крипта (CryptoBot)", callback_data="deposit:crypto"),
    )
    builder.row(
        InlineKeyboardButton(text="⭐ Telegram Stars", callback_data="deposit:stars"),
    )
    builder.row(
        InlineKeyboardButton(text="🌍 Змінити валюту", callback_data="menu:currency"),
        InlineKeyboardButton(text="◀ Назад", callback_data="menu:back"),
    )
    return builder.as_markup()


def back_keyboard(callback: str = "menu:back") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="◀ Назад", callback_data=callback))
    return builder.as_markup()
