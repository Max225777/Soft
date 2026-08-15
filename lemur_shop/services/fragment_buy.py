from __future__ import annotations

import logging

from lemur_shop.services import fragment, ton_wallet

log = logging.getLogger(__name__)


class BuyResult:
    def __init__(self, ok: bool, detail: str, total_ton: float = 0.0, dry_run: bool = False):
        self.ok = ok
        self.detail = detail
        self.total_ton = total_ton
        self.dry_run = dry_run

    def __repr__(self) -> str:
        return f"BuyResult(ok={self.ok}, ton={self.total_ton:.4f}, dry={self.dry_run}, {self.detail!r})"


async def buy_stars(username: str, quantity: int, *, confirm: bool = True) -> BuyResult:
    """Купує <quantity> Telegram Stars для @username через Fragment,
    оплачуючи з гаманця бота. Кроки:
      Fragment: searchStarsRecipient → initBuyStarsRequest → getBuyStarsLink
      Wallet:   надсилаємо transaction.messages з гаманця (TON)
    """
    username = username.lstrip("@").strip()
    if quantity < 50:
        return BuyResult(False, "мінімум 50 зірок (обмеження Fragment)")

    log.info("buy_stars: @%s x%d", username, quantity)
    messages = await fragment.get_stars_transaction(username, quantity)
    total_ton = sum(int(m["amount"]) for m in messages) / ton_wallet.NANO

    if not confirm:
        return BuyResult(True, f"розрахунок: {total_ton:.4f} TON за ⭐{quantity} для @{username}",
                         total_ton=total_ton, dry_run=True)

    res = await ton_wallet.send_ton_messages(messages)
    confirmed = await ton_wallet.wait_seqno(res.get("seqno_before", -1))
    status = "надіслано (dry-run)" if res.get("dry_run") else ("підтверджено" if confirmed else "надіслано, чекає підтвердження")
    return BuyResult(True, f"⭐{quantity} для @{username} — {status}",
                     total_ton=total_ton, dry_run=res.get("dry_run", False))


async def buy_premium(username: str, months: int, *, confirm: bool = True) -> BuyResult:
    """Дарує Telegram Premium на <months> місяців для @username через Fragment."""
    username = username.lstrip("@").strip()
    if months not in (3, 6, 12):
        return BuyResult(False, "Premium доступний на 3, 6 або 12 місяців")

    log.info("buy_premium: @%s %dm", username, months)
    messages = await fragment.get_premium_transaction(username, months)
    total_ton = sum(int(m["amount"]) for m in messages) / ton_wallet.NANO

    if not confirm:
        return BuyResult(True, f"розрахунок: {total_ton:.4f} TON за Premium {months}м для @{username}",
                         total_ton=total_ton, dry_run=True)

    res = await ton_wallet.send_ton_messages(messages)
    confirmed = await ton_wallet.wait_seqno(res.get("seqno_before", -1))
    status = "надіслано (dry-run)" if res.get("dry_run") else ("підтверджено" if confirmed else "надіслано, чекає підтвердження")
    return BuyResult(True, f"Premium {months}м для @{username} — {status}",
                     total_ton=total_ton, dry_run=res.get("dry_run", False))
