from __future__ import annotations

from decimal import Decimal

from aiogram import F, Router
from aiogram.types import CallbackQuery, Message, LabeledPrice, PreCheckoutQuery

from bot.db.models import TxType, User
from bot.db.session import AsyncSessionLocal
from bot.keyboards.inline import balance_keyboard, back_keyboard, currency_keyboard
from bot.services import balance as balance_svc
from bot.services.stars import stars_to_usd, get_rate, usd_to_stars
from bot.utils.currency import format_amount

router = Router()

# Мінімальне поповнення Stars (у зірках)
MIN_STARS_DEPOSIT = 50


@router.callback_query(F.data == "menu:balance")
async def cb_balance(callback: CallbackQuery) -> None:
    async with AsyncSessionLocal() as session:
        user = await session.get(User, callback.from_user.id)
        if not user:
            await callback.answer("Спочатку введіть /start")
            return

        amount_usd = await balance_svc.get_balance_usd(session, user.id)

    formatted = format_amount(amount_usd, user.display_currency)
    usd_formatted = format_amount(amount_usd, "USD")

    text = (
        "💳 <b>Ваш баланс</b>\n\n"
        f"<b>{formatted}</b>"
    )
    if user.display_currency != "USD":
        text += f"\n<i>≈ {usd_formatted}</i>"

    text += "\n\nОберіть спосіб поповнення:"

    await callback.message.edit_text(text, reply_markup=balance_keyboard(), parse_mode="HTML")


# ---------------------------------------------------------------------------
# Stars deposit
# ---------------------------------------------------------------------------

@router.callback_query(F.data == "deposit:stars")
async def cb_deposit_stars(callback: CallbackQuery) -> None:
    rate = get_rate()
    example_50 = stars_to_usd(50)
    example_100 = stars_to_usd(100)

    await callback.message.edit_text(
        f"⭐ <b>Поповнення через Telegram Stars</b>\n\n"
        f"Курс: 1 USD = {int(rate)} ⭐\n\n"
        f"50 ⭐ = {format_amount(example_50, 'USD')}\n"
        f"100 ⭐ = {format_amount(example_100, 'USD')}\n\n"
        f"Введіть кількість зірок (мінімум {MIN_STARS_DEPOSIT}):",
        reply_markup=back_keyboard("menu:balance"),
        parse_mode="HTML",
    )
    # Встановлюємо стан FSM (спрощено через callback data в наступному кроці)


@router.callback_query(F.data == "deposit:crypto")
async def cb_deposit_crypto(callback: CallbackQuery) -> None:
    await callback.message.edit_text(
        "🔷 <b>Поповнення через CryptoBot</b>\n\n"
        "Приймаємо: USDT, TON, BTC, ETH\n\n"
        "Введіть суму в USD для поповнення:",
        reply_markup=back_keyboard("menu:balance"),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "deposit:card")
async def cb_deposit_card(callback: CallbackQuery) -> None:
    await callback.message.edit_text(
        "💳 <b>Поповнення карткою (FreeCassa)</b>\n\n"
        "Комісія: ~4%\n"
        "Валюти: RUB, UAH, KZT\n\n"
        "Введіть суму для поповнення:",
        reply_markup=back_keyboard("menu:balance"),
        parse_mode="HTML",
    )


# ---------------------------------------------------------------------------
# Telegram Stars Invoice (вбудований платіж TG)
# ---------------------------------------------------------------------------

async def send_stars_invoice(message: Message, stars: int) -> None:
    """Надсилає invoice на оплату зірками через Telegram Payments."""
    usd_value = stars_to_usd(stars)
    await message.answer_invoice(
        title="Поповнення балансу Лемур",
        description=f"{stars} ⭐ → {format_amount(usd_value, 'USD')} на баланс",
        payload=f"stars_deposit:{message.from_user.id}:{stars}",
        currency="XTR",  # Telegram Stars
        prices=[LabeledPrice(label="Зірки", amount=stars)],
    )


@router.pre_checkout_query()
async def pre_checkout(query: PreCheckoutQuery) -> None:
    await query.answer(ok=True)


@router.message(F.successful_payment)
async def successful_stars_payment(message: Message) -> None:
    payload = message.successful_payment.invoice_payload
    if not payload.startswith("stars_deposit:"):
        return

    _, user_id_str, stars_str = payload.split(":")
    user_id = int(user_id_str)
    stars = int(stars_str)
    usd_amount = stars_to_usd(stars)
    rate = get_rate()

    async with AsyncSessionLocal() as session:
        async with session.begin():
            await balance_svc.deposit(
                session=session,
                user_id=user_id,
                amount_usd=usd_amount,
                tx_type=TxType.DEPOSIT_STARS,
                payment_method="stars",
                stars_count=stars,
                stars_rate=Decimal(str(1 / float(rate))),
                original_amount=Decimal(str(stars)),
                original_currency="XTR",
                comment=f"Поповнення {stars} Stars",
            )
            new_balance = await balance_svc.get_balance_usd(session, user_id)
            user = await session.get(User, user_id)

    await message.answer(
        f"✅ <b>Поповнення підтверджено!</b>\n\n"
        f"Зараховано: {stars} ⭐ → <b>{format_amount(usd_amount, 'USD')}</b>\n"
        f"Поточний баланс: <b>{format_amount(new_balance, user.display_currency if user else 'USD')}</b>",
        parse_mode="HTML",
    )


# ---------------------------------------------------------------------------
# Зміна валюти відображення
# ---------------------------------------------------------------------------

@router.callback_query(F.data == "menu:currency")
async def cb_currency_menu(callback: CallbackQuery) -> None:
    await callback.message.edit_text(
        "🌍 <b>Валюта відображення</b>\n\n"
        "Ціни будуть показані в обраній валюті.\n"
        "Внутрішній баланс завжди в USD.",
        reply_markup=currency_keyboard(),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("currency:"))
async def cb_set_currency(callback: CallbackQuery) -> None:
    currency = callback.data.split(":")[1]

    async with AsyncSessionLocal() as session:
        async with session.begin():
            user = await session.get(User, callback.from_user.id)
            if user:
                user.display_currency = currency

    labels = {"USD": "$ USD", "UAH": "₴ UAH", "RUB": "₽ RUB", "KZT": "₸ KZT"}
    await callback.answer(f"Валюта: {labels.get(currency, currency)}")
    await cb_balance(callback)


@router.callback_query(F.data == "menu:back")
async def cb_back_to_menu(callback: CallbackQuery) -> None:
    from bot.keyboards.inline import main_menu_keyboard
    from bot.config import settings

    async with AsyncSessionLocal() as session:
        user = await session.get(User, callback.from_user.id)

    region_labels = {"UA": "🇺🇦", "RU": "🇷🇺", "KZ": "🇰🇿"}
    flag = region_labels.get(user.region if user else "RU", "🌍")

    await callback.message.edit_text(
        f"🦎 <b>Лемур</b> {flag}\n\n"
        "Оберіть дію:",
        reply_markup=main_menu_keyboard(settings.WEBAPP_URL or "https://t.me"),
        parse_mode="HTML",
    )
