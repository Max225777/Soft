from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.types import CallbackQuery, Message

from bot.db.models import Region, User
from bot.db.session import AsyncSessionLocal
from bot.keyboards.inline import main_menu_keyboard, region_keyboard
from bot.services import referral as ref_svc
from bot.config import settings

router = Router()


async def _get_or_create_user(
    session,
    tg_user,
    ref_code: str | None = None,
) -> tuple[User, bool]:
    user = await session.get(User, tg_user.id)
    created = False

    if user is None:
        code = await ref_svc.ensure_unique_code(session)
        referrer = None
        if ref_code:
            referrer = await ref_svc.get_referrer_by_code(session, ref_code)

        user = User(
            id=tg_user.id,
            username=tg_user.username,
            full_name=tg_user.full_name or "",
            referral_code=code,
            referred_by_id=referrer.id if referrer else None,
        )
        session.add(user)
        await session.flush()
        created = True
    else:
        # Оновлюємо username якщо змінився
        if user.username != tg_user.username:
            user.username = tg_user.username
            await session.flush()

    return user, created


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    args = message.text.split(maxsplit=1)[1] if " " in (message.text or "") else None
    ref_code = args.strip() if args else None

    async with AsyncSessionLocal() as session:
        async with session.begin():
            user, created = await _get_or_create_user(
                session, message.from_user, ref_code
            )

    if created:
        # Новий користувач — просимо вибрати регіон
        await message.answer(
            "🦎 Ласкаво просимо до <b>Лемур</b>!\n\n"
            "Оберіть ваш регіон — це вплине на доступні способи оплати та валюту відображення:",
            reply_markup=region_keyboard(),
            parse_mode="HTML",
        )
    else:
        await _show_main_menu(message, user)


@router.callback_query(F.data.startswith("region:"))
async def cb_set_region(callback: CallbackQuery) -> None:
    region = callback.data.split(":")[1]
    if region not in (r.value for r in Region):
        await callback.answer("Невідомий регіон")
        return

    async with AsyncSessionLocal() as session:
        async with session.begin():
            user = await session.get(User, callback.from_user.id)
            if user:
                user.region = region
                # Автоматично ставимо дефолтну валюту для регіону
                user.display_currency = {
                    "UA": "UAH",
                    "RU": "RUB",
                    "KZ": "KZT",
                }.get(region, "USD")

    region_labels = {"UA": "🇺🇦 Україна", "RU": "🇷🇺 Росія", "KZ": "🇰🇿 Казахстан"}
    await callback.answer(f"Регіон: {region_labels.get(region, region)}")

    async with AsyncSessionLocal() as session:
        user = await session.get(User, callback.from_user.id)

    await callback.message.edit_text(
        "✅ Регіон збережено!\n\n"
        "Тепер ви можете користуватись магазином:",
        reply_markup=main_menu_keyboard(settings.WEBAPP_URL or "https://t.me"),
    )


async def _show_main_menu(message: Message, user: User) -> None:
    region_labels = {"UA": "🇺🇦", "RU": "🇷🇺", "KZ": "🇰🇿"}
    flag = region_labels.get(user.region, "🌍")

    await message.answer(
        f"🦎 <b>Лемур</b> {flag}\n\n"
        "Цифровий магазин: TG-акаунти, Stars, Premium\n\n"
        "Оберіть дію нижче:",
        reply_markup=main_menu_keyboard(settings.WEBAPP_URL or "https://t.me"),
        parse_mode="HTML",
    )
