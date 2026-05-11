from __future__ import annotations

import secrets
import string
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import settings
from bot.db.models import Balance, ReferralPayout, TxType, User
from bot.services import balance as balance_svc


_CODE_CHARS = string.ascii_uppercase + string.digits
_CODE_LEN = 8


def generate_code() -> str:
    return "".join(secrets.choice(_CODE_CHARS) for _ in range(_CODE_LEN))


async def ensure_unique_code(session: AsyncSession) -> str:
    for _ in range(10):
        code = generate_code()
        exists = await session.scalar(select(User).where(User.referral_code == code).limit(1))
        if not exists:
            return code
    raise RuntimeError("Could not generate unique referral code")


async def get_referrer_by_code(session: AsyncSession, code: str) -> User | None:
    result = await session.execute(select(User).where(User.referral_code == code))
    return result.scalar_one_or_none()


async def get_referral_stats(session: AsyncSession, user_id: int) -> dict:
    """Повертає статистику реф. програми для користувача."""
    referrals_count = await session.scalar(
        select(func.count()).where(User.referred_by_id == user_id)
    )

    total_earned = await session.scalar(
        select(func.coalesce(func.sum(ReferralPayout.bonus_usd), 0))
        .where(ReferralPayout.referrer_id == user_id)
    )

    last_payouts = await session.execute(
        select(ReferralPayout)
        .where(ReferralPayout.referrer_id == user_id)
        .order_by(ReferralPayout.created_at.desc())
        .limit(10)
    )

    return {
        "referrals_count": referrals_count or 0,
        "total_earned_usd": Decimal(str(total_earned or 0)),
        "bonus_percent": settings.REFERRAL_BONUS_PERCENT,
        "last_payouts": list(last_payouts.scalars()),
    }


async def accrue_referral_bonus(
    session: AsyncSession,
    order_id: int,
    referred_user_id: int,
    order_amount_usd: Decimal,
) -> ReferralPayout | None:
    """
    Нараховує реферальний бонус реферу після успішної оплати замовлення.
    Викликається одразу після підтвердження оплати.
    """
    # Знаходимо реферера
    user = await session.get(User, referred_user_id)
    if user is None or user.referred_by_id is None:
        return None

    # Перевіряємо чи вже нараховано (idempotency)
    already = await session.scalar(
        select(ReferralPayout).where(ReferralPayout.order_id == order_id).limit(1)
    )
    if already:
        return already

    bonus_percent = Decimal(str(settings.REFERRAL_BONUS_PERCENT))
    bonus_usd = (order_amount_usd * bonus_percent / Decimal("100")).quantize(Decimal("0.000001"))

    if bonus_usd <= 0:
        return None

    payout = ReferralPayout(
        referrer_id=user.referred_by_id,
        referred_id=referred_user_id,
        order_id=order_id,
        order_amount_usd=order_amount_usd,
        bonus_usd=bonus_usd,
        bonus_percent=float(bonus_percent),
    )
    session.add(payout)

    await balance_svc.deposit(
        session=session,
        user_id=user.referred_by_id,
        amount_usd=bonus_usd,
        tx_type=TxType.REFERRAL_BONUS,
        comment=f"Реферальний бонус {settings.REFERRAL_BONUS_PERCENT}% від замовлення #{order_id}",
    )

    await session.flush()
    return payout
