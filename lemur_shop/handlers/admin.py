from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery
from sqlalchemy import func, select

from lemur_shop.config import settings
from lemur_shop.db.models import Order, User
from lemur_shop.db.session import AsyncSessionLocal
from lemur_shop.i18n import t
from lemur_shop.keyboards.inline import admin_keyboard, orders_keyboard

router = Router()


def _is_admin(user_id: int) -> bool:
    return user_id in settings.ADMIN_IDS


@router.callback_query(F.data == "menu:admin")
async def cb_admin(callback: CallbackQuery) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer("❌")
        return

    async with AsyncSessionLocal() as s:
        user = await s.get(User, callback.from_user.id)
        total_users  = await s.scalar(select(func.count(User.id)))
        total_orders = await s.scalar(select(func.count(Order.id)))
        pending      = await s.scalar(select(func.count(Order.id)).where(Order.status == "pending"))
    lang = user.lang if user else "ru"

    text = (
        f"{t(lang, 'admin_title')}\n\n"
        f"{t(lang, 'admin_users',  n=total_users)}\n"
        f"{t(lang, 'admin_orders', n=total_orders)}\n"
        f"{t(lang, 'admin_pending', n=pending)}"
    )
    await callback.message.edit_text(text, reply_markup=admin_keyboard(lang), parse_mode="HTML")


@router.callback_query(F.data == "admin:orders")
async def cb_orders(callback: CallbackQuery) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer("❌")
        return

    async with AsyncSessionLocal() as s:
        user = await s.get(User, callback.from_user.id)
        result = await s.execute(
            select(Order).order_by(Order.created_at.desc()).limit(20)
        )
        orders = list(result.scalars())
        rows = []
        for o in orders:
            u = await s.get(User, o.user_id)
            uname = u.username or str(o.user_id) if u else str(o.user_id)
            rows.append(f"#{o.id} | ${o.price_usd} | {o.status} | @{uname}")

    lang = user.lang if user else "ru"
    text = t(lang, "orders_list") + "\n\n" + "\n".join(rows) if rows else t(lang, "orders_list")
    await callback.message.edit_text(text, reply_markup=orders_keyboard(lang, orders), parse_mode="HTML")
