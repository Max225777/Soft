from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from lemur_shop.db.models import User


async def get_referrer_by_code(session: AsyncSession, code: str) -> User | None:
    return (await session.execute(
        select(User).where(User.referral_code == code)
    )).scalar_one_or_none()
