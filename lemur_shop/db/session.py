from __future__ import annotations

import re
import ssl
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from lemur_shop.config import settings

# Railway дає postgresql://, SQLAlchemy async потребує postgresql+asyncpg://
_url = settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)

# asyncpg не підтримує sslmode як query параметр — прибираємо
_has_ssl = "sslmode=" in _url
_url = re.sub(r"[?&]sslmode=[^&]*", "", _url).rstrip("?").rstrip("&")

_connect_args: dict = {"ssl": True} if _has_ssl else {}

engine = create_async_engine(
    _url,
    echo=False,
    pool_pre_ping=True,
    connect_args=_connect_args,
)

AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session
