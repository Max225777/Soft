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
