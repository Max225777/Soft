from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select

from lemur_shop.config import settings
from lemur_shop.db.models import Order, User
from lemur_shop.db.session import AsyncSessionLocal
from lemur_shop.i18n import t
from lemur_shop.keyboards.inline import back_to_main, categories_keyboard
from lemur_shop.services.lolz_shop import search_accounts

router = Router()


def _lolz_price(item: dict) -> float:
    return float(item.get("price") or item.get("price_usd") or 0)


def _lolz_title(item: dict) -> str:
    return item.get("title") or item.get("item_origin") or f"#{item.get('item_id', '?')}"


@router.callback_query(F.data == "menu:shop")
async def cb_shop(callback: CallbackQuery) -> None:
    async with AsyncSessionLocal() as s:
        user = await s.get(User, callback.from_user.id)
    lang = user.lang if user else "ru"
    await callback.message.edit_text(
        t(lang, "shop_title"),
        reply_markup=categories_keyboard(lang),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("cat:"))
async def cb_category(callback: CallbackQuery) -> None:
    category = callback.data.split(":")[1]
    await callback.answer()  # прибираємо loading

    async with AsyncSessionLocal() as s:
        user = await s.get(User, callback.from_user.id)
    lang = user.lang if user else "ru"

    # Шукаємо акаунти на Lolz
    items = await search_accounts(category)

    if not items:
        await callback.message.edit_text(
            t(lang, "no_items"),
            reply_markup=back_to_main(lang),
            parse_mode="HTML",
        )
        return

    b = InlineKeyboardBuilder()
    for item in items:
        item_id = item.get("item_id") or item.get("id")
        price = _lolz_price(item)
        title = _lolz_title(item)
        b.row(InlineKeyboardButton(
            text=f"{title} — ${price:.2f}",
            callback_data=f"buy:{item_id}:{price:.2f}:{category}",
        ))
    b.row(InlineKeyboardButton(text=t(lang, "btn_back"), callback_data="menu:shop"))

    await callback.message.edit_text(
        t(lang, "shop_title"),
        reply_markup=b.as_markup(),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("buy:"))
async def cb_buy(callback: CallbackQuery) -> None:
    parts = callback.data.split(":")
    # buy:{lolz_item_id}:{price}:{category}
    lolz_item_id = int(parts[1])
    price_usd = float(parts[2])
    category = parts[3] if len(parts) > 3 else "ua"

    async with AsyncSessionLocal() as s:
        async with s.begin():
            user = await s.get(User, callback.from_user.id)
            order = Order(
                user_id=user.id,
                product_id=0,           # без продукту в БД — товар напряму з Lolz
                price_usd=price_usd,
                status="pending",
                lolz_item_id=lolz_item_id,
            )
            s.add(order)
            await s.flush()
            order_id = order.id
            lang = user.lang

    admin_contact = f"@{settings.ADMIN_USERNAME}" if settings.ADMIN_USERNAME else "адміну"
    await callback.message.edit_text(
        t(lang, "order_contact", id=order_id, admin=admin_contact),
        reply_markup=back_to_main(lang),
        parse_mode="HTML",
    )

    if settings.ADMIN_CHAT_ID:
        uname = f"@{user.username}" if user.username else str(user.id)
        b = InlineKeyboardBuilder()
        b.row(InlineKeyboardButton(
            text="⚡ Автовидати",
            callback_data=f"autodeliver:{order_id}",
        ))
        await callback.bot.send_message(
            settings.ADMIN_CHAT_ID,
            f"🛍 <b>Нове замовлення #{order_id}</b>\n"
            f"Lolz item: #{lolz_item_id}\n"
            f"Ціна: ${price_usd}\n"
            f"Від: {uname}",
            reply_markup=b.as_markup(),
            parse_mode="HTML",
        )
