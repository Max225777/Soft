from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.models import Balance, Transaction, TxStatus, TxType, User


class InsufficientFundsError(Exception):
    pass


async def get_or_create_balance(session: AsyncSession, user_id: int) -> Balance:
    result = await session.execute(select(Balance).where(Balance.user_id == user_id))
    balance = result.scalar_one_or_none()
    if balance is None:
        balance = Balance(user_id=user_id, amount_usd=Decimal("0"))
        session.add(balance)
        await session.flush()
    return balance


async def get_balance_usd(session: AsyncSession, user_id: int) -> Decimal:
    balance = await get_or_create_balance(session, user_id)
    return balance.amount_usd


async def deposit(
    session: AsyncSession,
    user_id: int,
    amount_usd: Decimal,
    tx_type: TxType,
    payment_method: str | None = None,
    external_id: str | None = None,
    original_amount: Decimal | None = None,
    original_currency: str | None = None,
    stars_count: int | None = None,
    stars_rate: Decimal | None = None,
    comment: str = "",
) -> Transaction:
    balance = await get_or_create_balance(session, user_id)
    balance.amount_usd += amount_usd

    tx = Transaction(
        user_id=user_id,
        type=tx_type,
        status=TxStatus.COMPLETED,
        amount_usd=amount_usd,
        original_amount=original_amount,
        original_currency=original_currency,
        stars_count=stars_count,
        stars_rate=stars_rate,
        external_id=external_id,
        payment_method=payment_method,
        comment=comment,
        completed_at=datetime.now(timezone.utc),
    )
    session.add(tx)
    await session.flush()
    return tx


async def withdraw(
    session: AsyncSession,
    user_id: int,
    amount_usd: Decimal,
    tx_type: TxType,
    order_id: int | None = None,
    comment: str = "",
) -> Transaction:
    balance = await get_or_create_balance(session, user_id)

    if balance.amount_usd < amount_usd:
        raise InsufficientFundsError(
            f"Balance {balance.amount_usd} USD < required {amount_usd} USD"
        )

    balance.amount_usd -= amount_usd

    tx = Transaction(
        user_id=user_id,
        type=tx_type,
        status=TxStatus.COMPLETED,
        amount_usd=-amount_usd,
        order_id=order_id,
        comment=comment,
        completed_at=datetime.now(timezone.utc),
    )
    session.add(tx)
    await session.flush()
    return tx


async def get_transactions(
    session: AsyncSession,
    user_id: int,
    limit: int = 20,
    offset: int = 0,
) -> list[Transaction]:
    result = await session.execute(
        select(Transaction)
        .where(Transaction.user_id == user_id)
        .order_by(Transaction.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars())
