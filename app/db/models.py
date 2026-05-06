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

    # --- Главный критерий: приватный тег с Lolzteam Market ---
    tag_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    tag_name: Mapped[str] = mapped_column(String(128), default="")

    # --- Доп. фильтры (применяются если tag_id не задан или вместе с ним) ---
    category: Mapped[str] = mapped_column(String(64), default="telegram")
    country: Mapped[str] = mapped_column(String(64), default="")
    price_min: Mapped[float | None] = mapped_column(Float, nullable=True)
    price_max: Mapped[float | None] = mapped_column(Float, nullable=True)
    keywords: Mapped[str] = mapped_column(String(255), default="")
    exact_title: Mapped[str] = mapped_column(String(512), default="")  # точная фраза в названии (опц.)
    extra_filters: Mapped[dict] = mapped_column(JSON, default=dict)

    default_cost: Mapped[float] = mapped_column(Float, default=0.0)
    markup: Mapped[float] = mapped_column(Float, default=0.0)  # наценка в абсолютной сумме ($)

    # --- Автоподнятие (обычные, не закреплённые) ---
    auto_bump: Mapped[bool] = mapped_column(Boolean, default=False)
    bumps_per_day: Mapped[int] = mapped_column(Integer, default=0)  # сколько поднятий в сутки от этой ниши (0 = не ограничено)
    bumps_per_tick: Mapped[int] = mapped_column(Integer, default=5)  # скільки bump за один цикл (одну ітерацію)
    spamblock_filter: Mapped[dict] = mapped_column(JSON, default=dict)  # {only_clean:bool, allow_geo:bool, allow_unchecked:bool}

    # --- Автозакрепление ---
    auto_stick: Mapped[bool] = mapped_column(Boolean, default=False)
    stick_slots: Mapped[int] = mapped_column(Integer, default=0)  # сколько слотов закреплений занимает эта ниша

    # --- Поднятие закреплённых (отдельный пул) ---
    auto_bump_stuck: Mapped[bool] = mapped_column(Boolean, default=False)
    stuck_bumps_per_day: Mapped[int] = mapped_column(Integer, default=0)  # поднятий среди закреплённых в сутки
    stuck_bump_cooldown_min: Mapped[int] = mapped_column(Integer, default=60)  # пауза между bump одного и того же stuck-акк (Lolzteam: 1 раз/час)

    # JSON-массив из 24 чисел — сколько bump-ов делать в каждом часу суток (для обычных).
    # [] = равномерно в течение дня. Настраивается интерактивной кривой в UI.
    hourly_schedule: Mapped[list] = mapped_column(JSON, default=list)

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
    is_stuck: Mapped[bool] = mapped_column(Boolean, default=False)
    last_bumped_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_stuck_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    niche_id: Mapped[int | None] = mapped_column(ForeignKey("niches.id", ondelete="SET NULL"), nullable=True)
    niche: Mapped[Niche | None] = relationship(back_populates="accounts")

    # Список приватных меток с Lolzteam: [{id: int, title: str}, …]
    tags: Mapped[list] = mapped_column(JSON, default=list)
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
