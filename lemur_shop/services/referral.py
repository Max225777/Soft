from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from lemur_shop.db.models import PartnerLink, User


async def get_referrer_by_code(session: AsyncSession, code: str) -> User | None:
    return (await session.execute(
        select(User).where(User.referral_code == code)
    )).scalar_one_or_none()


async def resolve_referral(session: AsyncSession, code: str) -> tuple[User | None, int | None]:
    """Повертає (реферер, id_партнёрської_лінки).

    Спочатку пробуємо звичайний реферальний код юзера, потім — код
    партнёрської лінки. Для звичайного реферала link_id = None.
    """
    if not code:
        return None, None
    user = await get_referrer_by_code(session, code)
    if user:
        return user, None
    link = (await session.execute(
        select(PartnerLink).where(PartnerLink.code == code)
    )).scalar_one_or_none()
    if link:
        partner = await session.get(User, link.partner_id)
        if partner and partner.is_partner:
            return partner, link.id
    return None, None
