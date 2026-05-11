"""AES-256 шифрование для API-токена.

Ключ производится из машинного идентификатора + соли, хранящейся в БД.
Для повышения безопасности можно заменить на системное хранилище (keyring)
в последующих версиях.
"""

from __future__ import annotations

import base64
import hashlib
import os
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


def _derive_key(salt: bytes) -> bytes:
    machine_id = _machine_id().encode("utf-8")
    return hashlib.pbkdf2_hmac("sha256", machine_id, salt, iterations=200_000, dklen=32)


def _machine_id() -> str:
    for path in ("/etc/machine-id", "/var/lib/dbus/machine-id"):
        p = Path(path)
        if p.exists():
            try:
                return p.read_text(encoding="utf-8").strip()
            except OSError:
                pass
    # Windows / macOS fallback: hostname + user
    return f"{os.environ.get('COMPUTERNAME', os.uname().nodename if hasattr(os, 'uname') else 'host')}"


def encrypt_token(token: str, salt: bytes) -> str:
    if not token:
        return ""
    key = _derive_key(salt)
    aes = AESGCM(key)
    nonce = os.urandom(12)
    ciphertext = aes.encrypt(nonce, token.encode("utf-8"), associated_data=None)
    return base64.b64encode(nonce + ciphertext).decode("ascii")


def decrypt_token(payload: str, salt: bytes) -> str:
    if not payload:
        return ""
    raw = base64.b64decode(payload.encode("ascii"))
    nonce, ciphertext = raw[:12], raw[12:]
    key = _derive_key(salt)
    aes = AESGCM(key)
    return aes.decrypt(nonce, ciphertext, associated_data=None).decode("utf-8")


def new_salt() -> bytes:
    return os.urandom(16)


def mask_token(token: str) -> str:
    if not token:
        return ""
    if len(token) <= 8:
        return "*" * len(token)
    return f"{token[:4]}{'*' * (len(token) - 8)}{token[-4:]}"
