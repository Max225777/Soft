"""Хранение пользовательских настроек в таблице app_settings (включая зашифрованный токен)."""

from __future__ import annotations

from sqlalchemy import select

from app.db.models import AppSetting
from app.db.session import get_session
from app.services.crypto import decrypt_token, encrypt_token, new_salt


TOKEN_KEY = "api_token_encrypted"
SALT_KEY = "crypto_salt_hex"


def _ensure_salt() -> bytes:
    with get_session() as s:
        salt_row = s.get(AppSetting, SALT_KEY)
        if salt_row and salt_row.value:
            return bytes.fromhex(salt_row.value)
        salt = new_salt()
        s.merge(AppSetting(key=SALT_KEY, value=salt.hex()))
        s.commit()
        return salt


def save_token(token: str) -> None:
    salt = _ensure_salt()
    payload = encrypt_token(token, salt)
    with get_session() as s:
        s.merge(AppSetting(key=TOKEN_KEY, value=payload))
        s.commit()


def load_token() -> str:
    salt = _ensure_salt()
    with get_session() as s:
        row = s.get(AppSetting, TOKEN_KEY)
        if not row or not row.value:
            return ""
        try:
            return decrypt_token(row.value, salt)
        except Exception:
            return ""


def set_kv(key: str, value: str) -> None:
    with get_session() as s:
        s.merge(AppSetting(key=key, value=value))
        s.commit()


def get_kv(key: str, default: str = "") -> str:
    with get_session() as s:
        row = s.get(AppSetting, key)
        return row.value if row else default


def all_kv() -> dict[str, str]:
    with get_session() as s:
        rows = s.execute(select(AppSetting)).scalars().all()
        return {r.key: r.value for r in rows}


# ---- Глобальные лимиты ----

GLOBAL_BUMPS_PER_ACCOUNT = "global_bumps_per_account_per_day"  # по умолчанию 3 (лимит Lolzteam)
GLOBAL_STICK_SLOTS = "global_stick_slots_total"  # сколько всего слотов закреплений доступно аккаунту продавца


def get_global_bumps_per_account() -> int:
    try:
        return int(get_kv(GLOBAL_BUMPS_PER_ACCOUNT, "3"))
    except ValueError:
        return 3


def get_global_stick_slots() -> int:
    try:
        return int(get_kv(GLOBAL_STICK_SLOTS, "5"))
    except ValueError:
        return 5


def set_global_bumps_per_account(value: int) -> None:
    set_kv(GLOBAL_BUMPS_PER_ACCOUNT, str(max(1, int(value))))


def set_global_stick_slots(value: int) -> None:
    set_kv(GLOBAL_STICK_SLOTS, str(max(0, int(value))))
