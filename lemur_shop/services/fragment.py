from __future__ import annotations

import logging
import re

import httpx

from lemur_shop.config import settings
from lemur_shop.services.lemurpanel import get_fragment_cookies, invalidate_cookie_cache

log = logging.getLogger(__name__)

FRAGMENT_BASE = "https://fragment.com"

_HASH_RE = re.compile(r'/api\?hash=([a-f0-9]+)')
_HASH_RE2 = re.compile(r'"apiHash"\s*:\s*"([a-f0-9]+)"')

# Кеш API-hash (живе довше за куки, але недовго — перезчитуємо зі сторінки).
_hash_cache: dict[str, tuple[str, float]] = {}


class FragmentError(Exception):
    pass


def _headers(cookies: dict[str, str]) -> dict[str, str]:
    cookie_str = "; ".join(f"{k}={v}" for k, v in cookies.items())
    return {
        "User-Agent": settings.FRAGMENT_USER_AGENT,
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "X-Requested-With": "XMLHttpRequest",
        "Origin": FRAGMENT_BASE,
        "Referer": f"{FRAGMENT_BASE}/stars",
        "Cookie": cookie_str,
    }


async def _get_hash(client: httpx.AsyncClient, cookies: dict[str, str], page: str = "/stars") -> str:
    r = await client.get(
        f"{FRAGMENT_BASE}{page}",
        headers={"User-Agent": settings.FRAGMENT_USER_AGENT,
                 "Cookie": "; ".join(f"{k}={v}" for k, v in cookies.items())},
    )
    html = r.text
    m = _HASH_RE.search(html) or _HASH_RE2.search(html)
    if not m:
        raise FragmentError(f"api hash not found on {page} (auth expired?)")
    return m.group(1)


async def _api(client: httpx.AsyncClient, cookies: dict[str, str], api_hash: str, **form) -> dict:
    """POST https://fragment.com/api?hash=<HASH> з form-data."""
    r = await client.post(
        f"{FRAGMENT_BASE}/api",
        params={"hash": api_hash},
        data=form,
        headers=_headers(cookies),
    )
    method = form.get("method", "?")
    log.info("fragment %s → HTTP %d %s", method, r.status_code, r.text[:300])
    if r.status_code == 401 or r.status_code == 403:
        raise FragmentError(f"fragment {method}: auth {r.status_code}")
    try:
        data = r.json()
    except Exception:
        raise FragmentError(f"fragment {method}: non-JSON response: {r.text[:200]}")
    if isinstance(data, dict) and data.get("error"):
        raise FragmentError(f"fragment {method}: {data.get('error')}")
    return data


def _extract_messages(transaction: dict) -> list[dict]:
    """З transaction дістаємо список повідомлень для оплати.
    Кожне: {'address': str, 'amount': str(нанотони), 'payload': base64}."""
    msgs = transaction.get("messages") if isinstance(transaction, dict) else None
    if not msgs:
        raise FragmentError(f"no messages in transaction: {str(transaction)[:300]}")
    out = []
    for m in msgs:
        out.append({
            "address": m.get("address"),
            "amount": str(m.get("amount")),
            "payload": m.get("payload"),
        })
    return out


async def _resolve_recipient(client, cookies, api_hash, *, search_method: str, query: str, **extra) -> str:
    data = await _api(client, cookies, api_hash, method=search_method, query=query.lstrip("@"), **extra)
    found = data.get("found") if isinstance(data, dict) else None
    if not found or not found.get("recipient"):
        raise FragmentError(f"recipient '{query}' not found ({search_method})")
    return str(found["recipient"])


async def get_stars_transaction(username: str, quantity: int) -> list[dict]:
    """Повний Fragment-флоу для Stars → список messages для оплати з гаманця."""
    cookies = await get_fragment_cookies()
    log.info("fragment stars: cookie keys=%s (stel_ton_token=%s)",
             list(cookies), "yes" if cookies.get("stel_ton_token") else "NO")
    async with httpx.AsyncClient(timeout=30, follow_redirects=True,
                                 proxy=settings.FRAGMENT_PROXY or None) as client:
        try:
            api_hash = await _get_hash(client, cookies, "/stars")
            rid = await _resolve_recipient(
                client, cookies, api_hash,
                search_method="searchStarsRecipient", query=username, quantity=quantity,
            )
            # Хеш беремо зі сторінки покупки (як робить сайт: /stars/buy?recipient=..&quantity=..).
            from urllib.parse import quote
            buy_page = f"/stars/buy?recipient={quote(str(rid), safe='')}&quantity={quantity}"
            try:
                buy_hash = await _get_hash(client, cookies, buy_page)
            except FragmentError:
                buy_hash = api_hash
            init = await _api(client, cookies, buy_hash,
                              method="initBuyStarsRequest", recipient=rid, quantity=quantity)
            req_id = init.get("req_id") or init.get("id")
            if not req_id:
                raise FragmentError(f"no req_id from initBuyStarsRequest: {str(init)[:200]}")
            link = await _api(client, cookies, buy_hash,
                              method="getBuyStarsLink", id=req_id, show_sender=0,
                              currency=settings.FRAGMENT_PAY_CURRENCY)
        except FragmentError as e:
            # куки могли протухнути — скинемо кеш, щоб наступна спроба взяла свіжі
            if "auth" in str(e).lower() or "expired" in str(e).lower():
                invalidate_cookie_cache()
            raise
    transaction = link.get("transaction", link)
    return _extract_messages(transaction)


async def get_premium_transaction(username: str, months: int) -> list[dict]:
    """Повний Fragment-флоу для Premium (подарунок) → messages для оплати."""
    cookies = await get_fragment_cookies()
    async with httpx.AsyncClient(timeout=30, follow_redirects=True,
                                 proxy=settings.FRAGMENT_PROXY or None) as client:
        try:
            api_hash = await _get_hash(client, cookies, "/premium")
            rid = await _resolve_recipient(
                client, cookies, api_hash,
                search_method="searchPremiumGiftRecipient", query=username, months=months,
            )
            from urllib.parse import quote
            buy_page = f"/premium/buy?recipient={quote(str(rid), safe='')}&months={months}"
            try:
                buy_hash = await _get_hash(client, cookies, buy_page)
            except FragmentError:
                buy_hash = api_hash
            init = await _api(client, cookies, buy_hash,
                              method="initGiftPremiumRequest", recipient=rid, months=months)
            req_id = init.get("req_id") or init.get("id")
            if not req_id:
                raise FragmentError(f"no req_id from initGiftPremiumRequest: {str(init)[:200]}")
            link = await _api(client, cookies, buy_hash,
                              method="getGiftPremiumLink", id=req_id,
                              currency=settings.FRAGMENT_PAY_CURRENCY)
        except FragmentError as e:
            if "auth" in str(e).lower() or "expired" in str(e).lower():
                invalidate_cookie_cache()
            raise
    transaction = link.get("transaction", link)
    return _extract_messages(transaction)
