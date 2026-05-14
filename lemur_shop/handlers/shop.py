from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from lemur_shop.api.lolz import LolzApiError
from lemur_shop.db.models import Order, User
from lemur_shop.db.session import AsyncSessionLocal
from lemur_shop.i18n import t
from lemur_shop.keyboards.inline import back_to_main, categories_keyboard, resend_keyboard
from lemur_shop.services.lolz_shop import auto_buy, search_accounts

router = Router()


def _item_id(item: dict) -> int:
    return int(item.get("item_id") or item.get("id") or 0)


def _price(item: dict) -> float:
    return float(item.get("price") or item.get("price_usd") or 0)


def _title(item: dict) -> str:
    origin = item.get("item_origin") or ""
    reg = item.get("reg_date") or item.get("registration_date") or ""
    label = origin or f"TG #{_item_id(item)}"
    return f"{label}  {reg}".strip()


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
    await callback.answer()

    async with AsyncSessionLocal() as s:
        user = await s.get(User, callback.from_user.id)
    lang = user.lang if user else "ru"

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
        iid = _item_id(item)
        price = _price(item)
        title = _title(item)
        b.row(InlineKeyboardButton(
            text=f"{title} — ${price:.2f}",
            callback_data=f"buy:{iid}:{price:.2f}:{category}",
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
    lolz_item_id = int(parts[1])
    price_usd = float(parts[2])
    category = parts[3] if len(parts) > 3 else "us"

    async with AsyncSessionLocal() as s:
        user = await s.get(User, callback.from_user.id)
        lang = user.lang

    # Показуємо "купую..."
    await callback.message.edit_text(t(lang, "buying_wait"), parse_mode="HTML")
    await callback.answer()

    # Купуємо на Lolz
    try:
        phone, code = await auto_buy(lolz_item_id, price_usd)
    except (LolzApiError, ValueError):
        await callback.message.edit_text(
            t(lang, "buy_error"),
            reply_markup=back_to_main(lang),
            parse_mode="HTML",
        )
        return

    # Зберігаємо замовлення
    async with AsyncSessionLocal() as s:
        async with s.begin():
            order = Order(
                user_id=callback.from_user.id,
                product_id=0,
                lolz_item_id=lolz_item_id,
                price_usd=price_usd,
                status="delivered",
                delivered_data=f"{phone}\n{code}",
                resend_count=1,
            )
            s.add(order)
            await s.flush()
            order_id = order.id

    # Спочатку номер
    await callback.message.edit_text(
        t(lang, "phone_msg", phone=phone),
        parse_mode="HTML",
    )

    # Потім код + інструкція
    kb = resend_keyboard(lang, order_id, 1)
    await callback.message.answer(
        t(lang, "code_msg", phone=phone, code=code),
        reply_markup=kb,
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("resend:"))
async def cb_resend(callback: CallbackQuery) -> None:
    order_id = int(callback.data.split(":")[1])

    async with AsyncSessionLocal() as s:
        async with s.begin():
            order = await s.get(Order, order_id)
            if not order or order.user_id != callback.from_user.id:
                await callback.answer("❌")
                return
            from lemur_shop.keyboards.inline import MAX_RESENDS
            if order.resend_count >= MAX_RESENDS:
                await callback.answer(t("ru", "resend_limit"), show_alert=True)
                return
            order.resend_count += 1
            count = order.resend_count
            raw = order.delivered_data or ""
        buyer = await s.get(User, callback.from_user.id)
        lang = buyer.lang if buyer else "ru"

    lines = raw.splitlines()
    phone = lines[0] if lines else "?"
    code  = lines[1] if len(lines) > 1 else "?"

    kb = resend_keyboard(lang, order_id, count)
    await callback.message.answer(
        t(lang, "resend_ok", id=order_id, phone=phone, code=code),
        reply_markup=kb,
        parse_mode="HTML",
    )
    await callback.answer()
