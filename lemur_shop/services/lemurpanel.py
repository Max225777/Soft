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
    """Значення куки має бути безпечним для HTTP-заголовка та формату Cookie:
    без керуючих символів, пробілів, ';' і не-ASCII. Решту символів дозволяємо."""
    if not v or len(v) > 8192:
        return False
    if "\r" in v or "\n" in v or "\t" in v or " " in v or ";" in v:
        return False
    return all(0x20 < ord(c) < 0x7f for c in v)


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
    headers = {"X-Shop-Key": key, "Accept": "application/json"}

    async with httpx.AsyncClient(timeout=15, follow_redirects=True) as c:
        # 1) Точний ендпоінт — РІВНО як робочий curl: GET, лише заголовок X-Shop-Key,
        #    без query-параметрів (вони ламають відповідь панелі).
        primary = settings.LEMURPANEL_COOKIE_PATH
        url = f"{base}{primary}"
        try:
            r = await c.get(url, headers=headers)
            ct = r.headers.get("content-type", "")
            log.info("LemurPanel primary GET %s → %s ct=%s body[:120]=%r",
                     url, r.status_code, ct, r.text[:120])
            if r.status_code == 200:
                try:
                    payload = r.json()
                except Exception:
                    payload = None
                if payload is not None:
                    cookies = _sanitize(_extract_cookies(payload))
                    log.info("LemurPanel primary parsed cookie keys: %s", list(cookies))
                    if _looks_like_fragment(cookies):
                        return cookies
                    log.warning("LemurPanel primary 200 but no valid stel_* cookies "
                                "(raw keys before sanitize: %s)", list(_extract_cookies(payload)))
        except Exception as e:
            log.warning("LemurPanel primary request failed: %s", e)

        # 2) Резервні шляхи (на випадок, якщо шлях зміниться) — GET, лише заголовок.
        last_err: Exception | None = CookieError(f"primary {url} did not return valid cookies")
        for path in ("/api/fragment/cookies", "/api/cookies", "/fragment/cookies"):
            u = f"{base}{path}"
            try:
                r = await c.get(u, headers=headers)
                if r.status_code != 200:
                    last_err = CookieError(f"GET {u} → HTTP {r.status_code}")
                    continue
                if "html" in r.headers.get("content-type", "").lower() or r.text.lstrip()[:1] == "<":
                    last_err = CookieError(f"GET {u} → HTML, not cookies")
                    continue
                try:
                    payload = r.json()
                except Exception:
                    last_err = CookieError(f"GET {u} → not JSON")
                    continue
                cookies = _sanitize(_extract_cookies(payload))
                if _looks_like_fragment(cookies):
                    log.info("LemurPanel cookies from %s (%s)", u, ", ".join(cookies))
                    return cookies
                last_err = CookieError(f"GET {u} → no stel_ cookies")
            except Exception as e:
                last_err = e
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


async def diagnose() -> str:
    """Діагностика: показує, що LemurPanel реально віддає по кожному адресу.
    Запусти /fragdiag у боті й надішли вивід."""
    lines = []
    base = (settings.LEMURPANEL_URL or "").rstrip("/")
    lines.append(f"LEMURPANEL_URL: {base or '(порожньо)'}")
    lines.append(f"SHOP_API_KEY: {'заданий (' + str(len(settings.SHOP_API_KEY)) + ' симв.)' if settings.SHOP_API_KEY else '(порожньо)'}")
    fb = settings.FRAGMENT_COOKIES_FALLBACK
    if fb:
        c = _sanitize(_parse_cookie_string(fb))
        lines.append(f"FRAGMENT_COOKIES_FALLBACK: {'✅ валідний, ключі: ' + ', '.join(c) if _looks_like_fragment(c) else '⚠️ заданий, але немає stel_* куків'}")
    else:
        lines.append("FRAGMENT_COOKIES_FALLBACK: (порожньо)")

    if not base:
        lines.append("\n→ LEMURPANEL_URL порожній, панель не опитується.")
        return "\n".join(lines)

    key = settings.SHOP_API_KEY
    headers = {"X-Shop-Key": key, "Accept": "application/json"}   # рівно як робочий curl
    paths = [settings.LEMURPANEL_COOKIE_PATH]
    lines.append("\nПеревірка (GET, лише X-Shop-Key):")
    async with httpx.AsyncClient(timeout=12, follow_redirects=True) as c:
        for path in paths:
            url = f"{base}{path}"
            try:
                r = await c.get(url, headers=headers)
                ct = r.headers.get("content-type", "").split(";")[0]
                snippet = r.text[:80].replace("\n", " ").replace("\r", " ")
                mark = ""
                if "html" in ct.lower() or r.text.lstrip()[:1] == "<":
                    mark = " ← HTML (не куки)"
                elif "stel" in r.text:
                    mark = " ← ✅ Є stel_!"
                lines.append(f"  {path} → {r.status_code} {ct} | {snippet}{mark}")
            except Exception as e:
                lines.append(f"  {path} → ПОМИЛКА: {type(e).__name__}: {str(e)[:60]}")
    return "\n".join(lines)
