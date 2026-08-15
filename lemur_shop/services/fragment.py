from __future__ import annotations

import json
import logging
import re
from urllib.parse import quote

import httpx

from lemur_shop.config import settings
from lemur_shop.services.lemurpanel import get_fragment_cookies, invalidate_cookie_cache

log = logging.getLogger(__name__)

FRAGMENT_BASE = "https://fragment.com"

_HASH_RE = re.compile(r'/api\?hash=([a-f0-9]+)')
_HASH_RE2 = re.compile(r'"apiHash"\s*:\s*"([a-f0-9]+)"')

# Fingerprint пристрою (як шле фронтенд Fragment при TON-оплаті).
DEVICE_FINGERPRINT = (
    '{"platform":"android","appName":"Tonkeeper","appVersion":"26.04.3",'
    '"maxProtocolVersion":2,"features":["SendTransaction",'
    '{"name":"SignData","types":["text","binary","cell"]},'
    '{"name":"SendTransaction","maxMessages":255}]}'
)

# FRAGMENT_PAY_CURRENCY → payment_method Fragment.
_PAY_METHOD = {"USDT": "usdt_ton", "TON": "ton", "USDC": "usdc_base"}


class FragmentError(Exception):
    pass


def _pay_method() -> str:
    return _PAY_METHOD.get((settings.FRAGMENT_PAY_CURRENCY or "USDT").upper(), "usdt_ton")


def _account_json() -> str:
    """Обʼєкт account для Fragment (walletStateInit/publicKey можуть бути порожні)."""
    return json.dumps({
        "address": settings.WALLET_ADDRESS,
        "chain": "-239",             # TON mainnet
        "walletStateInit": "",
        "publicKey": "",
    })


def _cookie_header(cookies: dict[str, str]) -> str:
    return "; ".join(f"{k}={v}" for k, v in cookies.items())


def _headers(cookies: dict[str, str], referer_path: str) -> dict[str, str]:
    referer = f"{FRAGMENT_BASE}{referer_path}"
    return {
        "User-Agent": settings.FRAGMENT_USER_AGENT,
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Accept-Language": "en-US,en;q=0.9",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "Origin": FRAGMENT_BASE,
        "Referer": referer,
        "X-Aj-Referer": referer,          # Fragment (main-aj.js) перевіряє цей заголовок
        "X-Requested-With": "XMLHttpRequest",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
        "Priority": "u=1, i",
        "Cookie": _cookie_header(cookies),
    }


async def _get_hash(client: httpx.AsyncClient, cookies: dict[str, str], page: str) -> str:
    r = await client.get(
        f"{FRAGMENT_BASE}{page}",
        headers={"User-Agent": settings.FRAGMENT_USER_AGENT,
                 "Cookie": _cookie_header(cookies)},
    )
    m = _HASH_RE.search(r.text) or _HASH_RE2.search(r.text)
    if not m:
        raise FragmentError(f"api hash not found on {page} (auth expired?)")
    return m.group(1)


async def _api(client: httpx.AsyncClient, cookies: dict[str, str], api_hash: str,
               referer_path: str, **form) -> dict:
    """POST https://fragment.com/api?hash=<HASH> form-data з правильними заголовками."""
    r = await client.post(
        f"{FRAGMENT_BASE}/api",
        params={"hash": api_hash},
        data=form,
        headers=_headers(cookies, referer_path),
    )
    method = form.get("method", "?")
    log.info("fragment %s → HTTP %d %s", method, r.status_code, r.text[:300])
    if r.status_code in (401, 403):
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
    return [{"address": m.get("address"), "amount": str(m.get("amount")),
             "payload": m.get("payload")} for m in msgs]


async def _resolve_recipient(client, cookies, api_hash, referer_path, *,
                             search_method: str, query: str, **extra) -> str:
    data = await _api(client, cookies, api_hash, referer_path,
                      method=search_method, query=query.lstrip("@"), **extra)
    found = data.get("found") if isinstance(data, dict) else None
    if not found or not found.get("recipient"):
        raise FragmentError(f"recipient '{query}' not found ({search_method})")
    return str(found["recipient"])


async def get_stars_transaction(username: str, quantity: int) -> list[dict]:
    """Повний Fragment-флоу для Stars → список messages для оплати з гаманця."""
    if not settings.WALLET_ADDRESS:
        raise FragmentError("WALLET_ADDRESS не задано (адреса гаманця бота потрібна Fragment)")
    cookies = await get_fragment_cookies()
    log.info("fragment stars: cookie keys=%s (stel_ton_token=%s)",
             list(cookies), "yes" if cookies.get("stel_ton_token") else "NO")
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        try:
            search_hash = await _get_hash(client, cookies, "/stars")
            rid = await _resolve_recipient(
                client, cookies, search_hash, "/stars",
                search_method="searchStarsRecipient", query=username, quantity="",
            )
            buy_ref = f"/stars/buy?recipient={quote(str(rid), safe='')}&quantity={quantity}"
            buy_hash = await _get_hash(client, cookies, buy_ref)
            init = await _api(client, cookies, buy_hash, buy_ref,
                              method="initBuyStarsRequest", recipient=rid,
                              quantity=str(quantity), payment_method=_pay_method())
            req_id = init.get("req_id") or init.get("id")
            if not req_id:
                raise FragmentError(f"no req_id from initBuyStarsRequest: {str(init)[:200]}")
            link = await _api(client, cookies, buy_hash, buy_ref,
                              method="getBuyStarsLink", account=_account_json(),
                              device=DEVICE_FINGERPRINT, transaction=1, id=req_id, show_sender=0)
        except FragmentError as e:
            if "auth" in str(e).lower() or "expired" in str(e).lower():
                invalidate_cookie_cache()
            raise
    transaction = link.get("transaction", link)
    return _extract_messages(transaction)


async def get_premium_transaction(username: str, months: int) -> list[dict]:
    """Повний Fragment-флоу для Premium (подарунок) → messages для оплати."""
    if not settings.WALLET_ADDRESS:
        raise FragmentError("WALLET_ADDRESS не задано (адреса гаманця бота потрібна Fragment)")
    cookies = await get_fragment_cookies()
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        try:
            search_hash = await _get_hash(client, cookies, "/premium")
            rid = await _resolve_recipient(
                client, cookies, search_hash, "/premium",
                search_method="searchPremiumGiftRecipient", query=username, months=months,
            )
            buy_ref = f"/premium/buy?recipient={quote(str(rid), safe='')}&months={months}"
            buy_hash = await _get_hash(client, cookies, buy_ref)
            init = await _api(client, cookies, buy_hash, buy_ref,
                              method="initGiftPremiumRequest", recipient=rid,
                              months=str(months), payment_method=_pay_method())
            req_id = init.get("req_id") or init.get("id")
            if not req_id:
                raise FragmentError(f"no req_id from initGiftPremiumRequest: {str(init)[:200]}")
            link = await _api(client, cookies, buy_hash, buy_ref,
                              method="getGiftPremiumLink", account=_account_json(),
                              device=DEVICE_FINGERPRINT, transaction=1, id=req_id, show_sender=0)
        except FragmentError as e:
            if "auth" in str(e).lower() or "expired" in str(e).lower():
                invalidate_cookie_cache()
            raise
    transaction = link.get("transaction", link)
    return _extract_messages(transaction)
