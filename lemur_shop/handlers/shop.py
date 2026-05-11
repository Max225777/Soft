from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery
from sqlalchemy import select

from lemur_shop.config import settings
from lemur_shop.db.models import Order, Product, User
from lemur_shop.db.session import AsyncSessionLocal
from lemur_shop.i18n import t
from lemur_shop.keyboards.inline import back_to_main, categories_keyboard, products_keyboard

router = Router()


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
    async with AsyncSessionLocal() as s:
        user = await s.get(User, callback.from_user.id)
        result = await s.execute(
            select(Product)
            .where(Product.category == category, Product.is_active == True)
            .order_by(Product.price_usd)
        )
        products = list(result.scalars())
    lang = user.lang if user else "ru"

    if not products:
        await callback.message.edit_text(
            t(lang, "no_items"),
            reply_markup=back_to_main(lang),
            parse_mode="HTML",
        )
        return

    await callback.message.edit_text(
        t(lang, "shop_title"),
        reply_markup=products_keyboard(lang, products),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("buy:"))
async def cb_buy(callback: CallbackQuery) -> None:
    product_id = int(callback.data.split(":")[1])
    async with AsyncSessionLocal() as s:
        async with s.begin():
            user = await s.get(User, callback.from_user.id)
            product = await s.get(Product, product_id)
            if not product or not product.is_active:
                await callback.answer("❌")
                return

            order = Order(
                user_id=user.id,
                product_id=product.id,
                price_usd=product.price_usd,
                status="pending",
            )
            s.add(order)
            await s.flush()
            order_id = order.id
            lang = user.lang

    admin_contact = f"@{settings.ADMIN_USERNAME}" if settings.ADMIN_USERNAME else "адміну"
    await callback.message.edit_text(
        t(lang, "order_contact", admin=admin_contact) + f"\n\n<i>Замовлення #{order_id}</i>",
        reply_markup=back_to_main(lang),
        parse_mode="HTML",
    )

    # Сповіщення адміну
    if settings.ADMIN_CHAT_ID:
        uname = f"@{user.username}" if user.username else str(user.id)
        await callback.bot.send_message(
            settings.ADMIN_CHAT_ID,
            f"🛍 <b>Нове замовлення #{order_id}</b>\n"
            f"Товар: {product.title}\n"
            f"Ціна: ${product.price_usd}\n"
            f"Від: {uname}",
            parse_mode="HTML",
        )
