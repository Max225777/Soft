from __future__ import annotations

from lemur_shop.db.models import Base
from lemur_shop.db.session import engine


async def create_tables() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
