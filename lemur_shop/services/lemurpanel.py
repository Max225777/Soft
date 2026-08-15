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


def _looks_like_cookies(c: dict[str, str]) -> bool:
    """Схоже на куки Fragment — має хоч один stel_*-ключ (або взагалі непорожнє)."""
    if not c:
        return False
    return any(k.startswith("stel") for k in c) or len(c) >= 1


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
                    try:
                        payload = r.json()
                    except Exception:
                        payload = r.text
                    cookies = _extract_cookies(payload)
                    if _looks_like_cookies(cookies):
                        log.info("LemurPanel cookies from %s %s (%d keys: %s)",
                                 method, url, len(cookies), ", ".join(list(cookies)[:4]))
                        return cookies
                    last_err = CookieError(f"{method} {url} → no cookies in body")
                except Exception as e:
                    last_err = e
                    continue
    raise CookieError(f"could not fetch Fragment cookies: {last_err}")


async def get_fragment_cookies(force: bool = False) -> dict[str, str]:
    """Повертає актуальні куки Fragment (кеш на FRAGMENT_COOKIE_TTL секунд)."""
    global _cache
    now = time.time()
    if not force and _cache and now < _cache[1]:
        return _cache[0]

    try:
        cookies = await _fetch_from_panel()
    except CookieError as e:
        if settings.FRAGMENT_COOKIES_FALLBACK:
            log.warning("LemurPanel fetch failed (%s) — using FRAGMENT_COOKIES_FALLBACK", e)
            cookies = _parse_cookie_string(settings.FRAGMENT_COOKIES_FALLBACK)
        else:
            raise

    if not cookies:
        raise CookieError("no Fragment cookies available")

    _cache = (cookies, now + max(60, settings.FRAGMENT_COOKIE_TTL))
    return cookies


def invalidate_cookie_cache() -> None:
    global _cache
    _cache = None
