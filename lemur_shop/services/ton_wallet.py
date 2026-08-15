from __future__ import annotations

import asyncio
import base64
import logging

from lemur_shop.config import settings

log = logging.getLogger(__name__)

NANO = 1_000_000_000  # 1 TON = 1e9 nanoton


class WalletError(Exception):
    pass


def _mnemonic_list() -> list[str]:
    words = settings.WALLET_SEED.split()
    if len(words) not in (12, 24):
        raise WalletError(f"WALLET_SEED must be 12/24 words, got {len(words)}")
    return words


def _total_ton(messages: list[dict]) -> float:
    return sum(int(m["amount"]) for m in messages) / NANO


async def send_ton_messages(messages: list[dict]) -> dict:
    """Надсилає TON-повідомлення (address, amount нанотони, payload base64 BOC)
    одним external-повідомленням із гаманця бота через pytoniq.

    Повертає {'ok': bool, 'dry_run': bool, 'total_ton': float, 'seqno_before': int}.
    Запобіжники: ліміт суми + DRY_RUN.
    """
    if not messages:
        raise WalletError("no messages to send")

    total = _total_ton(messages)
    if total > settings.FRAGMENT_MAX_TON_PER_BUY:
        raise WalletError(
            f"refusing: total {total:.3f} TON > limit {settings.FRAGMENT_MAX_TON_PER_BUY} TON")

    log.info("TON send: %d msg(s), total=%.4f TON, dry_run=%s",
             len(messages), total, settings.FRAGMENT_DRY_RUN)

    if settings.FRAGMENT_DRY_RUN:
        for m in messages:
            log.info("  [DRY] → %s  %.4f TON  payload=%s",
                     m["address"], int(m["amount"]) / NANO, (m["payload"] or "")[:24])
        return {"ok": True, "dry_run": True, "total_ton": total, "seqno_before": -1}

    if not settings.WALLET_SEED:
        raise WalletError("WALLET_SEED not configured")

    # Імпорт всередині — pytoniq потрібен лише коли реально шлемо.
    try:
        from pytoniq import LiteBalancer, WalletV4R2
        from pytoniq_core import Address, Cell
    except Exception as e:
        raise WalletError(f"pytoniq not available: {e}")

    provider = LiteBalancer.from_config_url(settings.TON_CONFIG_URL, trust_level=2) \
        if hasattr(LiteBalancer, "from_config_url") else LiteBalancer.from_mainnet_config(trust_level=2)
    await provider.start_up()
    try:
        wallet = await WalletV4R2.from_mnemonic(provider, _mnemonic_list())
        seqno_before = await wallet.get_seqno()

        wallet_msgs = []
        for m in messages:
            body = None
            if m.get("payload"):
                body = Cell.one_from_boc(base64.b64decode(m["payload"]))
            wallet_msgs.append(wallet.create_wallet_internal_message(
                destination=Address(m["address"]),
                value=int(m["amount"]),
                body=body,
            ))
        await wallet.raw_transfer(msgs=wallet_msgs)
        log.info("TON transfer sent (seqno_before=%s, total=%.4f TON)", seqno_before, total)
        return {"ok": True, "dry_run": False, "total_ton": total, "seqno_before": seqno_before}
    finally:
        await provider.close_all()


async def wait_seqno(seqno_before: int, timeout: float = 60.0) -> bool:
    """Чекає, поки seqno гаманця зросте (= транзакція підтверджена в блокчейні)."""
    if settings.FRAGMENT_DRY_RUN or seqno_before < 0:
        return True
    try:
        from pytoniq import LiteBalancer, WalletV4R2
    except Exception:
        return False
    provider = LiteBalancer.from_config_url(settings.TON_CONFIG_URL, trust_level=2) \
        if hasattr(LiteBalancer, "from_config_url") else LiteBalancer.from_mainnet_config(trust_level=2)
    await provider.start_up()
    try:
        wallet = await WalletV4R2.from_mnemonic(provider, _mnemonic_list())
        deadline = asyncio.get_event_loop().time() + timeout
        while asyncio.get_event_loop().time() < deadline:
            if await wallet.get_seqno() > seqno_before:
                return True
            await asyncio.sleep(3)
        return False
    finally:
        await provider.close_all()
