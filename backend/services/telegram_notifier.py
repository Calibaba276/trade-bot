"""
Telegram notification service for the trade bot.

Pulls TELEGRAM-BOT-TOKEN and TELEGRAM-CHAT-ID from Azure Key Vault and
sends messages via the Telegram Bot API. All public functions fail silently
so a Telegram outage never interrupts live trading.
"""

import threading
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
    """Send a plain message in a daemon thread so callers are never blocked. Never raises."""
    def _run() -> None:
        try:
            _send(text)
        except Exception as exc:
            logger.warning(f"[TELEGRAM] notify failed: {exc}")
    threading.Thread(target=_run, daemon=True).start()


def _notify_blocking(text: str) -> None:
    """Send synchronously in the calling thread. Use for shutdown/halt alerts where the
    process may exit immediately after — daemon threads are killed before they can POST."""
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
        f"<code>{signal_id}</code>"
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
        f"<code>{signal_id}</code>"
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
        f"<code>{signal_id}</code>"
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
    _notify_blocking(msg)


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
    _notify_blocking(msg)


def notify_strategy_online(symbol: str, account: str, server: str, mode: str) -> None:
    """Strategy runner process started — confirms the runner actually launched.

    Mirror of notify_worker_online: the worker and the strategy runner are
    SEPARATE processes, so a WORKER ONLINE message says nothing about whether the
    strategy runner came up. Also validates Telegram credentials in this process."""
    token = _bot_token()
    chat_id = _chat_id()
    if not token or not chat_id:
        logger.error(
            "[TELEGRAM] TELEGRAM-BOT-TOKEN or TELEGRAM-CHAT-ID missing from Key Vault — "
            "no Telegram notifications will be sent from this strategy runner. "
            "Add both secrets to calibabasecret vault."
        )
    msg = (
        f"🟢 <b>STRATEGY ONLINE — {symbol}</b>\n"
        f"Account : {account}\n"
        f"Server  : {server}\n"
        f"Mode    : {mode}"
    )
    notify(msg)


def notify_strategy_offline(symbol: str, reason: str) -> None:
    """Strategy runner crashed or exited. Sent synchronously because the process
    typically exits immediately after, which would kill a daemon-thread send."""
    msg = (
        f"🔴 <b>STRATEGY OFFLINE — {symbol}</b>\n"
        f"Reason  : {reason}"
    )
    _notify_blocking(msg)


def notify_strategy_active(
    symbol: str,
    pdh: float,
    pdl: float,
    daily_bias: str | None,
    date: str,
) -> None:
    """PDH/PDL captured and daily bias set — strategy is ready to trade."""
    bias_icon = "🐂" if daily_bias == "bull" else ("🐻" if daily_bias == "bear" else "⚪")
    bias_text = "Bullish" if daily_bias == "bull" else ("Bearish" if daily_bias == "bear" else "No Bias")
    msg = (
        f"📊 <b>STRATEGY ACTIVE — {symbol}</b>\n"
        f"PDH   : {pdh}\n"
        f"PDL   : {pdl}\n"
        f"Bias  : {bias_icon} {bias_text}\n"
        f"Date  : {date}"
    )
    notify(msg)


def notify_liquidity_swept(
    symbol: str,
    direction: str,
    reference_level: float,
    sweep_point: float,
    session: str,
    current_time: str,
) -> None:
    """Price wick swept past a key liquidity level (PDH or PDL)."""
    icon = "🔴" if direction == "bearish" else "🟢"
    level_label = "PDH" if direction == "bearish" else "PDL"
    wick_label = "Wick High" if direction == "bearish" else "Wick Low "
    msg = (
        f"{icon} <b>LIQUIDITY SWEPT — {symbol}</b>\n"
        f"Setup      : {direction.capitalize()}\n"
        f"{level_label}        : {reference_level}\n"
        f"{wick_label} : {sweep_point}\n"
        f"Session    : {session}\n"
        f"Time       : {current_time} NGT"
    )
    notify(msg)


def notify_mss_confirmed(
    symbol: str,
    direction: str,
    swing_price: float,
    session: str,
    current_time: str,
) -> None:
    """Market Structure Shift confirmed — swing level identified after sweep."""
    swing_label = "Swing Low " if direction == "bearish" else "Swing High"
    msg = (
        f"⚡ <b>MSS CONFIRMED — {symbol}</b>\n"
        f"Direction  : {direction.capitalize()}\n"
        f"{swing_label} : {swing_price}\n"
        f"Session    : {session}\n"
        f"Time       : {current_time} NGT"
    )
    notify(msg)


def notify_fvg_confirmed(
    symbol: str,
    direction: str,
    fvg_top: float,
    fvg_bottom: float,
    session: str,
    current_time: str,
) -> None:
    """Fair Value Gap identified after MSS displacement."""
    msg = (
        f"📦 <b>FVG CONFIRMED — {symbol}</b>\n"
        f"Direction : {direction.capitalize()}\n"
        f"FVG Top   : {fvg_top}\n"
        f"FVG Bot   : {fvg_bottom}\n"
        f"Session   : {session}\n"
        f"Time      : {current_time} NGT"
    )
    notify(msg)


def notify_ote_zone(
    symbol: str,
    direction: str,
    ote_62: float,
    ote_79: float,
    current_time: str,
) -> None:
    """OTE zone calculated for NY Continuation — waiting for price to enter."""
    premium_label = "Premium" if direction == "bearish" else "Discount"
    msg = (
        f"📐 <b>OTE ZONE CALCULATED — {symbol}</b>\n"
        f"Direction : {direction.capitalize()} ({premium_label})\n"
        f"OTE 62%   : {round(ote_62, 5)}\n"
        f"OTE 79%   : {round(ote_79, 5)}\n"
        f"Time      : {current_time} NGT\n"
        f"Waiting for price to reach zone..."
    )
    notify(msg)


def notify_ote_hit(
    symbol: str,
    direction: str,
    ote_62: float,
    ote_79: float,
    current_time: str,
) -> None:
    """Price entered the OTE zone — watching for MSS to confirm entry."""
    msg = (
        f"🎯 <b>OTE ZONE REACHED — {symbol}</b>\n"
        f"Direction : {direction.capitalize()}\n"
        f"Zone      : {round(ote_62, 5)} – {round(ote_79, 5)}\n"
        f"Time      : {current_time} NGT\n"
        f"Watching for MSS confirmation..."
    )
    notify(msg)


def notify_ny_session_start(symbol: str, current_time: str) -> None:
    """NY session started at 13:30 NGT — technical markers reset."""
    msg = (
        f"🗽 <b>NY SESSION START — {symbol}</b>\n"
        f"Time   : {current_time} NGT\n"
        f"Status : Technical markers reset, watching for NY setup"
    )
    notify(msg)


def notify_market_closed(symbol: str, date: str) -> None:
    """Market closed for the day at 16:00 NGT — no new trades."""
    msg = (
        f"🔒 <b>MARKET CLOSED — {symbol}</b>\n"
        f"Date   : {date}\n"
        f"Status : No new trades until tomorrow (09:00 NGT)"
    )
    notify(msg)


def notify_breakeven_moved(
    symbol: str,
    side: str,
    ticket: int,
    entry_price: float,
    old_sl: float,
    new_sl: float,
    account_number: int,
) -> None:
    """Stop loss moved to breakeven after trade moved in favour."""
    msg = (
        f"🛡️ <b>BREAKEVEN MOVED — {symbol}</b>\n"
        f"Side    : {side.capitalize()}\n"
        f"Ticket  : {ticket}\n"
        f"Entry   : {entry_price:.5f}\n"
        f"Old SL  : {old_sl:.5f}\n"
        f"New SL  : {new_sl:.5f}\n"
        f"Account : {account_number}"
    )
    notify(msg)
