from __future__ import annotations

"""Сховище кук Fragment.

Куки вставляє адмін в адмін-панелі (беруться з браузера fragment.com), вони
зберігаються в БД (app_settings['fragment_cookies']) і використовуються для
прямих запитів до Fragment. LemurPanel API більше не використовується.
"""

import logging
import time

from sqlalchemy import select

from lemur_shop.config import settings
from lemur_shop.db.models import AppSetting
from lemur_shop.db.session import AsyncSessionLocal

log = logging.getLogger(__name__)

SETTING_KEY = "fragment_cookies"

# Кеш розпарсених куків: (cookies_dict, expires_at_ts)
_cache: tuple[dict[str, str], float] | None = None


class CookieError(Exception):
    pass


# ─── Парсинг / валідація ─────────────────────────────────────────────────────

def _parse_cookie_string(raw: str) -> dict[str, str]:
    """'k1=v1; k2=v2' → {'k1': 'v1', 'k2': 'v2'}. Терпить префікс 'Cookie:'."""
    raw = (raw or "").strip()
    if raw.lower().startswith("cookie:"):
        raw = raw[len("cookie:"):].strip()
    out: dict[str, str] = {}
    # роздільник — ';' або переноси рядків
    for part in raw.replace("\n", ";").split(";"):
        part = part.strip()
        if not part or "=" not in part:
            continue
        k, v = part.split("=", 1)
        out[k.strip()] = v.strip()
    return out


def _header_safe(v: str) -> bool:
    if not v or len(v) > 8192:
        return False
    if "\r" in v or "\n" in v or "\t" in v or " " in v or ";" in v:
        return False
    return all(0x20 < ord(c) < 0x7f for c in v)


def _sanitize(cookies: dict[str, str]) -> dict[str, str]:
    return {k: v for k, v in cookies.items() if isinstance(v, str) and _header_safe(v)}


def _looks_like_fragment(cookies: dict[str, str]) -> bool:
    """Справжні куки Fragment мають хоч один ключ stel_* із валідним значенням."""
    return any(k.startswith("stel") and _header_safe(v) for k, v in cookies.items())


def parse_and_validate(raw: str) -> dict[str, str]:
    """Рядок кук → валідований dict. Кидає CookieError, якщо невалідно."""
    cookies = _sanitize(_parse_cookie_string(raw))
    if not _looks_like_fragment(cookies):
        raise CookieError(
            "не знайдено валідних кук Fragment. Потрібні stel_ssid / stel_token / "
            "stel_dt / stel_ton_token у форматі: stel_ssid=...; stel_token=...; ..."
        )
    return cookies


# ─── Сховище (БД) ────────────────────────────────────────────────────────────

async def _load_raw() -> str:
    """Сирий рядок кук: спершу з БД, потім з env FRAGMENT_COOKIES_FALLBACK."""
    async with AsyncSessionLocal() as s:
        row = await s.get(AppSetting, SETTING_KEY)
        if row and row.value:
            return row.value
    return settings.FRAGMENT_COOKIES_FALLBACK or ""


async def save_fragment_cookies(raw: str) -> dict[str, str]:
    """Валідує й зберігає куки в БД. Повертає dict валідних кук."""
    cookies = parse_and_validate(raw)
    # зберігаємо нормалізований рядок (лише валідні пари)
    normalized = "; ".join(f"{k}={v}" for k, v in cookies.items())
    async with AsyncSessionLocal() as s:
        async with s.begin():
            row = await s.get(AppSetting, SETTING_KEY)
            if row:
                row.value = normalized
            else:
                s.add(AppSetting(key=SETTING_KEY, value=normalized))
    invalidate_cookie_cache()
    log.info("Fragment cookies saved (%d keys: %s)", len(cookies), ", ".join(cookies))
    return cookies


async def clear_fragment_cookies() -> None:
    async with AsyncSessionLocal() as s:
        async with s.begin():
            row = await s.get(AppSetting, SETTING_KEY)
            if row:
                row.value = None
    invalidate_cookie_cache()


async def cookie_status() -> dict:
    """Статус для адмін-панелі (без розкриття значень)."""
    async with AsyncSessionLocal() as s:
        row = await s.get(AppSetting, SETTING_KEY)
        updated_at = row.updated_at.isoformat() if row and row.updated_at else None
    raw = await _load_raw()
    if not raw:
        return {"has": False, "valid": False, "keys": [], "updated_at": None,
                "source": None}
    cookies = _sanitize(_parse_cookie_string(raw))
    from_db = bool(row and row.value)
    return {
        "has": True,
        "valid": _looks_like_fragment(cookies),
        "keys": list(cookies),
        "updated_at": updated_at,
        "source": "db" if from_db else "env",
    }


# ─── Отримання кук для запитів до Fragment ───────────────────────────────────

async def get_fragment_cookies(force: bool = False) -> dict[str, str]:
    """Повертає валідні куки Fragment (кеш на FRAGMENT_COOKIE_TTL секунд)."""
    global _cache
    now = time.time()
    if not force and _cache and now < _cache[1]:
        return _cache[0]

    raw = await _load_raw()
    if not raw:
        raise CookieError(
            "куки Fragment не задані. Встав їх в адмін-панелі (розділ Fragment)."
        )
    cookies = parse_and_validate(raw)
    _cache = (cookies, now + max(60, settings.FRAGMENT_COOKIE_TTL))
    return cookies


def invalidate_cookie_cache() -> None:
    global _cache
    _cache = None
