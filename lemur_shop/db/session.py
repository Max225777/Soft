from __future__ import annotations

from collections.abc import AsyncGenerator
from urllib.parse import urlparse, urlunparse

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from lemur_shop.config import settings

# Railway/Neon дають postgresql://, потрібен postgresql+asyncpg://
_raw = settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)

# asyncpg не підтримує query params (sslmode, channel_binding тощо)
# Прибираємо всі query params і передаємо ssl окремо
_parsed = urlparse(_raw)
_needs_ssl = "sslmode=" in (settings.DATABASE_URL)
_clean_url = urlunparse(_parsed._replace(query=""))

engine = create_async_engine(
    _clean_url,
    echo=False,
    pool_pre_ping=True,
    connect_args={"ssl": True} if _needs_ssl else {},
)

AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session
