from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum

from sqlalchemy import (
    BigInteger, Boolean, DateTime, ForeignKey,
    Integer, Numeric, String, Text, UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class Region(str, Enum):
    UA = "UA"
    RU = "RU"
    KZ = "KZ"


class Currency(str, Enum):
    USD = "USD"
    UAH = "UAH"
    RUB = "RUB"
    KZT = "KZT"


class TxType(str, Enum):
    DEPOSIT_CRYPTO   = "deposit_crypto"
    DEPOSIT_CARD     = "deposit_card"
    DEPOSIT_STARS    = "deposit_stars"
    PURCHASE         = "purchase"
    REFERRAL_BONUS   = "referral_bonus"
    REFUND           = "refund"


class TxStatus(str, Enum):
    PENDING   = "pending"
    COMPLETED = "completed"
    FAILED    = "failed"
    EXPIRED   = "expired"


class OrderStatus(str, Enum):
    PENDING   = "pending"
    PAID      = "paid"
    DELIVERED = "delivered"
    FAILED    = "failed"
    REFUNDED  = "refunded"


class ProductCategory(str, Enum):
    TG_ACCOUNT = "tg_account"
    STARS      = "stars"
    PREMIUM    = "premium"


# ---------------------------------------------------------------------------
# User
# ---------------------------------------------------------------------------

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)  # Telegram user_id
    username: Mapped[str | None] = mapped_column(String(64), nullable=True)
    full_name: Mapped[str] = mapped_column(String(128), default="")

    region: Mapped[str] = mapped_column(String(4), default=Region.RU)
    display_currency: Mapped[str] = mapped_column(String(4), default=Currency.USD)

    referral_code: Mapped[str] = mapped_column(String(16), unique=True, nullable=False)
    referred_by_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    is_banned: Mapped[bool] = mapped_column(Boolean, default=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    balance: Mapped["Balance"] = relationship(back_populates="user", uselist=False,
                                               cascade="all, delete-orphan")
    transactions: Mapped[list["Transaction"]] = relationship(back_populates="user")
    orders: Mapped[list["Order"]] = relationship(back_populates="user")
    referrals: Mapped[list["User"]] = relationship(
        foreign_keys=[referred_by_id], lazy="select"
    )


# ---------------------------------------------------------------------------
# Balance  (в USD, Decimal для точності)
# ---------------------------------------------------------------------------

class Balance(Base):
    __tablename__ = "balances"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
    )

    amount_usd: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0"))

    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    user: Mapped["User"] = relationship(back_populates="balance")


# ---------------------------------------------------------------------------
# Transaction — будь-який рух коштів
# ---------------------------------------------------------------------------

class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )

    type: Mapped[str] = mapped_column(String(32), nullable=False)    # TxType
    status: Mapped[str] = mapped_column(String(16), default=TxStatus.PENDING)

    # Сума в USD (завжди), оригінальна сума + валюта для довідки
    amount_usd: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    original_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    original_currency: Mapped[str | None] = mapped_column(String(8), nullable=True)

    # Stars-специфіка
    stars_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    stars_rate: Mapped[Decimal | None] = mapped_column(Numeric(10, 6), nullable=True)  # USD за 1 зірку

    # Зовнішній payment ID (CryptoBot invoice_id, FreeCassa order_id тощо)
    external_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    payment_method: Mapped[str | None] = mapped_column(String(32), nullable=True)

    # Референс на замовлення (якщо транзакція — оплата замовлення)
    order_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("orders.id", ondelete="SET NULL"), nullable=True
    )

    comment: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    user: Mapped["User"] = relationship(back_populates="transactions")


# ---------------------------------------------------------------------------
# Order
# ---------------------------------------------------------------------------

class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )

    status: Mapped[str] = mapped_column(String(16), default=OrderStatus.PENDING)
    category: Mapped[str] = mapped_column(String(32), nullable=False)  # ProductCategory

    price_usd: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    cost_usd: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0"))

    # Для TG-акаунтів
    lolz_item_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Видача (заповнюється після успішної доставки)
    delivered_phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    delivered_code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    delivered_extra: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON

    # Для Stars / Premium — кому дарувати
    recipient_tg_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    recipient_username: Mapped[str | None] = mapped_column(String(64), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    user: Mapped["User"] = relationship(back_populates="orders")


# ---------------------------------------------------------------------------
# ReferralPayout — лог нарахованих реферальних бонусів
# ---------------------------------------------------------------------------

class ReferralPayout(Base):
    __tablename__ = "referral_payouts"
    __table_args__ = (UniqueConstraint("order_id", name="uq_refpayout_order"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    referrer_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    referred_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    order_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False
    )

    order_amount_usd: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    bonus_usd: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    bonus_percent: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


# ---------------------------------------------------------------------------
# ExchangeRate — кеш курсів валют (оновлюється раз на годину)
# ---------------------------------------------------------------------------

class ExchangeRate(Base):
    __tablename__ = "exchange_rates"

    currency: Mapped[str] = mapped_column(String(8), primary_key=True)  # UAH, RUB, KZT
    rate_to_usd: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)  # 1 USD = N одиниць
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
