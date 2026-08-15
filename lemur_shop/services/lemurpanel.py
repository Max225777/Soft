from __future__ import annotations

import logging
import time

import httpx

from lemur_shop.config import settings

log = logging.getLogger(__name__)

# Кеш куків Fragment: (cookies_dict, expires_at_ts)
_cache: tuple[dict[str, str], float] | None = None


class CookieError(Exception):
    pass


def _parse_cookie_string(raw: str) -> dict[str, str]:
    """'k1=v1; k2=v2' → {'k1': 'v1', 'k2': 'v2'}"""
    out: dict[str, str] = {}
    for part in raw.split(";"):
        part = part.strip()
        if not part or "=" not in part:
            continue
        k, v = part.split("=", 1)
        out[k.strip()] = v.strip()
    return out


def _header_safe(v: str) -> bool:
    """Значення куки має бути безпечним для HTTP-заголовка: без пробілів,
    переносів, керуючих символів і HTML."""
    if not v or len(v) > 4096:
        return False
    if any(c in v for c in "\r\n\t <>\"'"):
        return False
    return all(32 < ord(c) < 127 for c in v)


def _sanitize(cookies: dict[str, str]) -> dict[str, str]:
    return {k: v for k, v in cookies.items() if isinstance(v, str) and _header_safe(v)}


def _looks_like_fragment(cookies: dict[str, str]) -> bool:
    """Справжні куки Fragment завжди мають хоч один ключ stel_* із валідним
    (header-safe) значенням. Інакше це не куки (напр. HTML сторінки)."""
    return any(k.startswith("stel") and _header_safe(v) for k, v in cookies.items())


def _extract_cookies(data) -> dict[str, str]:
    """LemurPanel може віддавати куки різними формами — приводимо до dict.

    Підтримувані варіанти:
      • {"cookies": "stel_ssid=...; stel_token=..."}         (рядок)
      • {"cookies": {"stel_ssid": "...", ...}}                (обʼєкт)
      • {"stel_ssid": "...", "stel_token": "..."}             (плоский dict)
      • "stel_ssid=...; ..."                                   (голий рядок)
    """
    if isinstance(data, str):
        return _parse_cookie_string(data)
    if isinstance(data, dict):
        for key in ("cookies", "cookie", "data", "result"):
            if key in data:
                return _extract_cookies(data[key])
        # плоский dict із самими куками (лишаємо тільки stel_*-подібні)
        flat = {k: str(v) for k, v in data.items() if isinstance(v, (str, int))}
        return flat
    raise CookieError(f"unexpected cookie payload type: {type(data)}")


async def _fetch_from_panel() -> dict[str, str]:
    if not settings.LEMURPANEL_URL or not settings.SHOP_API_KEY:
        raise CookieError("LEMURPANEL_URL / SHOP_API_KEY not configured")

    base = settings.LEMURPANEL_URL.rstrip("/")
    key = settings.SHOP_API_KEY
    # Точний шлях/формат — з боку LemurPanel. Перебираємо ймовірні варіанти;
    # перший, що поверне валідні куки, виграє (і його буде видно в логах).
    paths = [
        "/api/fragment/cookies", "/api/fragment/cookie", "/api/cookies",
        "/api/cookie", "/fragment/cookies", "/api/fragment", "/cookies",
        "/api/get_cookies", "/api/fragment/session",
    ]
    headers = {
        "Authorization": f"Bearer {key}",
        "X-Api-Key": key,
        "X-Shop-Key": key,
        "Accept": "application/json",
    }
    # Ключ ще й у query — деякі панелі приймають саме так.
    query = {"key": key, "api_key": key, "token": key}

    last_err: Exception | None = None
    async with httpx.AsyncClient(timeout=15, follow_redirects=True) as c:
        for path in paths:
            url = f"{base}{path}"
            for method in ("GET", "POST"):
                try:
                    if method == "GET":
                        r = await c.get(url, headers=headers, params=query)
                    else:
                        r = await c.post(url, headers=headers, params=query, json={"key": key})
                    if r.status_code != 200:
                        last_err = CookieError(f"{method} {url} → HTTP {r.status_code}")
                        continue
                    ct = r.headers.get("content-type", "").lower()
                    body = r.text
                    # Ігноруємо HTML (напр. SPA index.html з кодом 200) — це не куки.
                    if "html" in ct or body.lstrip()[:1] == "<":
                        last_err = CookieError(f"{method} {url} → HTML, not cookies")
                        continue
                    try:
                        payload = r.json()
                    except Exception:
                        payload = body if "stel" in body else None
                    if payload is None:
                        last_err = CookieError(f"{method} {url} → not JSON/cookies")
                        continue
                    cookies = _sanitize(_extract_cookies(payload))
                    if _looks_like_fragment(cookies):
                        log.info("LemurPanel cookies from %s %s (%d keys: %s)",
                                 method, url, len(cookies), ", ".join(list(cookies)[:4]))
                        return cookies
                    last_err = CookieError(f"{method} {url} → no stel_ cookies in body")
                except Exception as e:
                    last_err = e
                    continue
    raise CookieError(f"could not fetch Fragment cookies: {last_err}")


async def get_fragment_cookies(force: bool = False) -> dict[str, str]:
    """Повертає актуальні валідні куки Fragment (кеш на FRAGMENT_COOKIE_TTL сек).

    Пріоритет: 1) прямі куки з FRAGMENT_COOKIES_FALLBACK (найнадійніше),
               2) LemurPanel API. Кешуємо лише валідні (з ключами stel_*).
    """
    global _cache
    now = time.time()
    if not force and _cache and now < _cache[1]:
        return _cache[0]

    cookies: dict[str, str] = {}

    # 1) Прямі куки з env
    if settings.FRAGMENT_COOKIES_FALLBACK:
        c = _sanitize(_parse_cookie_string(settings.FRAGMENT_COOKIES_FALLBACK))
        if _looks_like_fragment(c):
            cookies = c
        else:
            log.warning("FRAGMENT_COOKIES_FALLBACK встановлено, але немає валідних stel_* куків")

    # 2) LemurPanel API (якщо прямих немає)
    if not cookies:
        cookies = _sanitize(await _fetch_from_panel())

    if not _looks_like_fragment(cookies):
        raise CookieError(
            "немає валідних куків Fragment (потрібні stel_ssid/stel_token/stel_dt/...). "
            "Встанови FRAGMENT_COOKIES_FALLBACK з реальними куками або виправ LemurPanel endpoint"
        )

    _cache = (cookies, now + max(60, settings.FRAGMENT_COOKIE_TTL))
    return cookies


def invalidate_cookie_cache() -> None:
    global _cache
    _cache = None
