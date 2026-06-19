"""
Telegram notification service for the trade bot.

Pulls TELEGRAM-BOT-TOKEN and TELEGRAM-CHAT-ID from Azure Key Vault and
sends messages via the Telegram Bot API. All public functions fail silently
so a Telegram outage never interrupts live trading.
"""

from functools import lru_cache

import requests

from backend.config.secrets import get_azure_secret
from backend.config.logger import setup_logger

logger = setup_logger(__name__)

_TIMEOUT = 8  # seconds


@lru_cache(maxsize=1)
def _bot_token() -> str | None:
    return get_azure_secret("TELEGRAM-BOT-TOKEN")


@lru_cache(maxsize=1)
def _chat_id() -> str | None:
    return get_azure_secret("TELEGRAM-CHAT-ID")


def _send(text: str) -> None:
    """Post one message to Telegram. Raises on failure (callers catch it)."""
    token = _bot_token()
    chat_id = _chat_id()
    if not token or not chat_id:
        logger.warning("[TELEGRAM] Missing TELEGRAM-BOT-TOKEN or TELEGRAM-CHAT-ID in Key Vault")
        return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    resp = requests.post(
        url,
        json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
        timeout=_TIMEOUT,
    )
    if not resp.ok:
        logger.warning(f"[TELEGRAM] API error {resp.status_code}: {resp.text[:200]}")


def notify(text: str) -> None:
    """Send a plain message. Never raises."""
    try:
        _send(text)
    except Exception as exc:
        logger.warning(f"[TELEGRAM] notify failed: {exc}")


# ---------------------------------------------------------------------------
# Typed helpers — one per key event
# ---------------------------------------------------------------------------

def notify_signal(
    symbol: str,
    direction: str,
    scenario: str,
    entry: float,
    sl: float,
    tp: float,
    signal_id: str,
) -> None:
    """Signal generated and published to Redis."""
    icon = "🟢" if direction.lower() == "buy" else "🔴"
    msg = (
        f"{icon} <b>SIGNAL — {symbol}</b>\n"
        f"Direction : {direction.upper()}\n"
        f"Scenario  : {scenario}\n"
        f"Entry     : {entry}\n"
        f"SL        : {sl}\n"
        f"TP        : {tp}\n"
        f"<code>{signal_id[:8]}</code>"
    )
    notify(msg)


def notify_order_filled(
    symbol: str,
    direction: str,
    lot_size: float,
    fill_price: float,
    sl: float,
    tp: float,
    broker_order_id: str,
    latency_ms: float,
    signal_id: str,
) -> None:
    """Order placed successfully at the broker."""
    icon = "✅"
    msg = (
        f"{icon} <b>ORDER PLACED — {symbol}</b>\n"
        f"Direction : {direction.upper()}\n"
        f"Lots      : {lot_size}\n"
        f"Entry     : {fill_price}\n"
        f"SL        : {sl}\n"
        f"TP        : {tp}\n"
        f"Broker ID : {broker_order_id}\n"
        f"Latency   : {latency_ms}ms\n"
        f"<code>{signal_id[:8]}</code>"
    )
    notify(msg)


def notify_order_rejected(
    symbol: str,
    direction: str,
    retcode: int,
    error: str,
    signal_id: str,
) -> None:
    """Order rejected by the broker."""
    msg = (
        f"⚠️ <b>ORDER REJECTED — {symbol}</b>\n"
        f"Direction : {direction.upper()}\n"
        f"Retcode   : {retcode}\n"
        f"Error     : {error}\n"
        f"<code>{signal_id[:8]}</code>"
    )
    notify(msg)


def notify_drawdown_halt(
    account_number: int,
    account_id: str,
    day_start: float,
    current: float,
    loss_pct: float,
    limit_pct: float,
) -> None:
    """Daily drawdown limit breached — account halted for today."""
    msg = (
        f"🚨 <b>DRAWDOWN HALT — Account {account_number}</b>\n"
        f"Day start : ${day_start:.2f}\n"
        f"Current   : ${current:.2f}\n"
        f"Loss      : {loss_pct:.2f}%\n"
        f"Limit     : {limit_pct:.1f}%\n"
        f"Status    : No new trades until tomorrow (UTC)\n"
        f"<code>{account_id[:8]}</code>"
    )
    notify(msg)


def notify_worker_online(account_number: int, server: str, account_id: str) -> None:
    """Worker connected to MT5 and ready to trade. Also validates Telegram credentials."""
    token = _bot_token()
    chat_id = _chat_id()
    if not token or not chat_id:
        logger.error(
            "[TELEGRAM] TELEGRAM-BOT-TOKEN or TELEGRAM-CHAT-ID missing from Key Vault — "
            "no Telegram notifications will be sent. Add both secrets to calibabasecret vault."
        )
    msg = (
        f"🟢 <b>WORKER ONLINE</b>\n"
        f"Account : {account_number}\n"
        f"Server  : {server}\n"
        f"<code>{account_id[:8]}</code>"
    )
    notify(msg)


def notify_worker_offline(account_number: int, reason: str, account_id: str) -> None:
    """Worker shut down or crashed."""
    msg = (
        f"🔴 <b>WORKER OFFLINE</b>\n"
        f"Account : {account_number}\n"
        f"Reason  : {reason}\n"
        f"<code>{account_id[:8]}</code>"
    )
    notify(msg)
