"""
Emit candles and trade events from the ICT strategy to the Supabase tables
consumed by the Glass Box frontend (candles + trade_events).

All functions fail silently — a network/DB error must never interrupt live trading.
"""

from datetime import datetime, timezone

from backend.config.supaclient import supabase
from backend.config.logger import setup_logger

logger = setup_logger(__name__)


def _pair(sym: str) -> str:
    """Normalise broker/feed symbols to the 6-char pair used by the frontend.

    Examples: 'EURUSDm' → 'EURUSD',  'C:EURUSD' → 'EURUSD'
    """
    if ":" in sym:
        sym = sym.split(":")[-1]
    # Strip lowercase MT5 broker suffixes (m, n, …) that follow a 6-char pair
    if len(sym) > 6 and sym[6:].isalpha() and sym[6:].islower():
        sym = sym[:6]
    return sym


def emit_candle(
    user_id: str,
    account_id: str | None,
    pair: str,
    timeframe: str,
    bar_time_ms: int,
    open_: float,
    high: float,
    low: float,
    close: float,
    volume: float = 0,
) -> None:
    """Upsert one OHLCV bar. The unique(user_id, pair, timeframe, time) constraint
    deduplicates repeated calls for the same bar."""
    try:
        supabase.table("candles").upsert(
            {
                "user_id": user_id,
                "pair": pair,
                "timeframe": timeframe,
                "time": bar_time_ms,
                "open": open_,
                "high": high,
                "low": low,
                "close": close,
                "volume": volume,
            },
            on_conflict="user_id,pair,timeframe,time",
        ).execute()
    except Exception as exc:
        logger.warning(f"[EMITTER] candle upsert failed ({pair} {timeframe}): {exc}")


def emit_trade_event(
    user_id: str,
    account_id: str | None,
    pair: str,
    timeframe: str,
    event_type: str,
    *,
    pattern: str | None = None,
    price: float | None = None,
    high: float | None = None,
    low: float | None = None,
    volume: float = 0,
    confidence: float | None = None,
    metadata: dict | None = None,
) -> None:
    """Insert one row into trade_events. Called for MSS/FVG detections and entries."""
    try:
        now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
        row: dict = {
            "user_id": user_id,
            "account_id": account_id,
            "pair": pair,
            "timestamp": now_ms,
            "timeframe": timeframe,
            "type": event_type,
            "price": price,
            "high": high if high is not None else price,
            "low": low if low is not None else price,
            "volume": volume,
        }
        if pattern:
            row["pattern"] = pattern
        if confidence is not None:
            row["confidence"] = confidence
        if metadata:
            row["metadata"] = metadata

        supabase.table("trade_events").insert(row).execute()
    except Exception as exc:
        logger.warning(f"[EMITTER] trade_event insert failed ({pair} {event_type}): {exc}")


def emit_candles_from_df(
    user_id: str,
    account_id: str | None,
    pair: str,
    df: "import pandas; pandas.DataFrame",  # noqa: F821
) -> None:
    """
    Resample a 1-minute OHLCV DataFrame (DatetimeIndex) into 1m/5m/15m/1h candles
    and upsert the latest closed bar of each timeframe.
    """
    if df is None or df.empty:
        return

    # Determine the volume column name (MT5 may capitalise it differently)
    vol_col = next((c for c in ("volume", "Volume") if c in df.columns), None)

    agg: dict = {"open": "first", "high": "max", "low": "min", "close": "last"}
    if vol_col:
        agg[vol_col] = "sum"

    for tf_label, rule in [("1m", "1min"), ("5m", "5min"), ("15m", "15min"), ("1h", "60min")]:
        try:
            rs = df.resample(rule).agg(agg).dropna(subset=["open"])
            if rs.empty:
                continue

            bar = rs.iloc[-1]
            bar_ms = int(rs.index[-1].timestamp() * 1000)
            emit_candle(
                user_id, account_id, pair, tf_label, bar_ms,
                float(bar["open"]), float(bar["high"]),
                float(bar["low"]), float(bar["close"]),
                float(bar[vol_col]) if vol_col else 0,
            )
        except Exception as exc:
            logger.warning(f"[EMITTER] resample {tf_label} failed: {exc}")
