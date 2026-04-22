"""ORM-модели SQLAlchemy для локальной БД."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class AppSetting(Base):
    """Пары key-value для настроек (включая зашифрованный токен и salt)."""

    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class Niche(Base):
    __tablename__ = "niches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    category: Mapped[str] = mapped_column(String(64), default="")
    country: Mapped[str] = mapped_column(String(64), default="")
    price_min: Mapped[float | None] = mapped_column(Float, nullable=True)
    price_max: Mapped[float | None] = mapped_column(Float, nullable=True)
    keywords: Mapped[str] = mapped_column(String(255), default="")
    extra_filters: Mapped[dict] = mapped_column(JSON, default=dict)

    default_cost: Mapped[float] = mapped_column(Float, default=0.0)
    markup_percent: Mapped[float] = mapped_column(Float, default=0.0)

    auto_bump: Mapped[bool] = mapped_column(Boolean, default=False)
    bump_interval_min: Mapped[int] = mapped_column(Integer, default=480)  # 8 часов по умолчанию
    auto_stick: Mapped[bool] = mapped_column(Boolean, default=False)
    priority_item_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    accounts: Mapped[list["Account"]] = relationship(back_populates="niche", cascade="all, delete-orphan")
    sales: Mapped[list["Sale"]] = relationship(back_populates="niche")


class Account(Base):
    """Аккаунт маркетплейса — снимок из API + локальные поля (себестоимость, бинд)."""

    __tablename__ = "accounts"
    __table_args__ = (UniqueConstraint("item_id", name="uq_accounts_item_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    item_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(512), default="")
    category: Mapped[str] = mapped_column(String(64), default="")
    country: Mapped[str] = mapped_column(String(64), default="")
    price: Mapped[float] = mapped_column(Float, default=0.0)
    amount: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(32), default="active")  # active/inactive/sold/deleted

    cost: Mapped[float] = mapped_column(Float, default=0.0)  # себестоимость (локально)
    is_priority: Mapped[bool] = mapped_column(Boolean, default=False)

    bumps_available: Mapped[int] = mapped_column(Integer, default=3)
    sticks_available: Mapped[int] = mapped_column(Integer, default=1)
    last_bumped_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_stuck_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    niche_id: Mapped[int | None] = mapped_column(ForeignKey("niches.id", ondelete="SET NULL"), nullable=True)
    niche: Mapped[Niche | None] = relationship(back_populates="accounts")

    raw: Mapped[dict] = mapped_column(JSON, default=dict)  # исходный объект от API

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    @property
    def profit(self) -> float:
        return float(self.price or 0) - float(self.cost or 0)


class Sale(Base):
    __tablename__ = "sales"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    item_id: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(512), default="")
    price: Mapped[float] = mapped_column(Float, default=0.0)
    cost: Mapped[float] = mapped_column(Float, default=0.0)
    profit: Mapped[float] = mapped_column(Float, default=0.0)
    niche_id: Mapped[int | None] = mapped_column(ForeignKey("niches.id", ondelete="SET NULL"), nullable=True)
    sold_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)

    niche: Mapped[Niche | None] = relationship(back_populates="sales")


class ActionLog(Base):
    """Лог выполненных действий (автоматических и ручных)."""

    __tablename__ = "action_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    level: Mapped[str] = mapped_column(String(16), default="INFO")
    action: Mapped[str] = mapped_column(String(64), default="")  # bump/stick/price_update/…
    item_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    niche_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    message: Mapped[str] = mapped_column(Text, default="")
    details: Mapped[dict] = mapped_column(JSON, default=dict)


class PriceHistory(Base):
    __tablename__ = "price_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    item_id: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    price: Mapped[float] = mapped_column(Float, default=0.0)
    changed_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
