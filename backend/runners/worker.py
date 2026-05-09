import argparse
import json
import threading
import time
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any, Dict, Optional

import MetaTrader5 as mt5
import redis

from backend.brokers.mt5_broker import MetaTrader5 as MT5Broker
from backend.config.logger import setup_logger
from backend.config.secrets import get_azure_secret
from backend.config.supaclient import supabase

logger = setup_logger(__name__)

HEARTBEAT_INTERVAL = 30
CHANNEL_DEFAULT = "signals"
WORKER_STRATEGY_NAME = "Worker"


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def _parse_iso(ts: str) -> datetime:
    ts = ts.replace("Z", "+00:00")
    dt = datetime.fromisoformat(ts)
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _sleep_until(execute_at: Optional[str]) -> None:
    if not execute_at:
        logger.warning("Signal has no execute_at — executing immediately")
        return
    target = _parse_iso(execute_at)
    delay = (target - datetime.now(timezone.utc)).total_seconds()
    if delay > 0:
        logger.info(f"Holding {delay:.3f}s until execute_at={execute_at}")
        time.sleep(delay)
    else:
        logger.warning(f"execute_at already passed by {abs(delay):.3f}s — executing immediately")


def _pick(cfg: Dict[str, Any], *keys: str, default=None):
    for k in keys:
        if cfg.get(k) not in (None, ""):
            return cfg[k]
    return default


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _optional_float(value: Any) -> Optional[float]:
    if value in (None, ""):
        return None
    return float(value)


def _normalize_symbol(symbol: str) -> str:
    return symbol[:-1] + "m" if symbol.endswith("M") else symbol


# ---------------------------------------------------------------------------
# Account config
# ---------------------------------------------------------------------------

def _resolve_account_config(account_id: str) -> Dict[str, Any]:
    row = (
        supabase.table("broker_accounts")
        .select("*")
        .eq("id", account_id)
        .limit(1)
        .execute()
    )
    if not getattr(row, "data", None):
        raise RuntimeError(f"No broker_accounts row found for account_id={account_id}")
    cfg = row.data[0]

    login = _pick(cfg, "login", "account_login")
    password = _pick(cfg, "password", "account_password")
    server = _pick(cfg, "server", "account_server")
    path = _pick(cfg, "path", "terminal_path")
    timezone_name = _pick(cfg, "timezone", default="Africa/Lagos")

    if not login:
        login = get_azure_secret("ACCOUNT")
    if not password:
        password = get_azure_secret("PASSWORD")
    if not server:
        server = get_azure_secret("SERVER")

    if not login or not password or not server:
        raise RuntimeError("Missing MT5 credentials (login / password / server).")

    cfg["_resolved"] = {
        "login": int(login),
        "password": str(password),
        "server": str(server),
        "path": path,
        "timezone": timezone_name,
        "risk_amount": float(_pick(cfg, "risk_amount", default=25)),
    }
    return cfg


def _resolve_redis_url(cfg: Dict[str, Any]) -> str:
    return (
        _pick(cfg, "redis_url")
        or get_azure_secret("REDIS-URL")
        or "redis://localhost:6379/0"
    )


# ---------------------------------------------------------------------------
# Account status — broker_accounts.status + last_heartbeat
# ---------------------------------------------------------------------------

def _set_account_status(account_id: str, status: str, detail: str = "") -> None:
    try:
        supabase.table("broker_accounts").update(
            {
                "status": status,
                "status_detail": detail,
                "last_heartbeat": _now(),
            }
        ).eq("id", account_id).execute()
        logger.info(f"[STATUS] account_id={account_id} → {status} ({detail})")
    except Exception as e:
        logger.error(f"Failed to update account status: {e}")


def _heartbeat_loop(account_id: str, stop_event: threading.Event) -> None:
    while not stop_event.is_set():
        try:
            supabase.table("broker_accounts").update(
                {"last_heartbeat": _now()}
            ).eq("id", account_id).execute()
        except Exception as e:
            logger.warning(f"Heartbeat write failed: {e}")
        stop_event.wait(HEARTBEAT_INTERVAL)


# ---------------------------------------------------------------------------
# Supabase — executions + execution_events
# ---------------------------------------------------------------------------

def _upsert_execution(signal_id: str, account_id: str, data: Dict[str, Any]) -> None:
    payload = {"signal_id": signal_id, "account_id": account_id, **data}
    supabase.table("executions").upsert(
        payload, on_conflict="signal_id,account_id"
    ).execute()


def _log_event(
    signal_id: str,
    account_id: str,
    event_type: str,
    detail: Optional[dict] = None,
) -> None:
    try:
        supabase.table("execution_events").insert(
            {
                "signal_id": signal_id,
                "account_id": account_id,
                "event_type": event_type,
                "detail": detail or {},
                "occurred_at": _now(),
            }
        ).execute()
    except Exception as e:
        logger.warning(f"Failed to write execution event: {e}")


def _already_processed(signal_id: str, account_id: str) -> bool:
    terminal_statuses = {"filled", "submitted", "rejected", "error", "skipped"}
    row = (
        supabase.table("executions")
        .select("status")
        .eq("signal_id", signal_id)
        .eq("account_id", account_id)
        .limit(1)
        .execute()
    )
    if not getattr(row, "data", None):
        return False
    return row.data[0].get("status") in terminal_statuses


# ---------------------------------------------------------------------------
# Lot sizing
# ---------------------------------------------------------------------------

def _compute_lot_size(
    symbol: str,
    entry_price: float,
    stop_loss: float,
    risk_amount: float,
) -> float:
    sl_distance = abs(entry_price - stop_loss)
    if sl_distance <= 0:
        return 0.0

    info = mt5.symbol_info(symbol)
    if info is None:
        return 0.0

    contract_size = float(getattr(info, "trade_contract_size", 100_000) or 100_000)
    raw_lots = risk_amount / (sl_distance * contract_size)

    step = float(getattr(info, "volume_step", 0.01) or 0.01)
    min_v = float(getattr(info, "volume_min", 0.01) or 0.01)
    max_v = float(getattr(info, "volume_max", 100.0) or 100.0)

    if raw_lots < min_v:
        return 0.0

    raw_lots = min(raw_lots, max_v)
    steps = int((raw_lots - min_v) / step)
    return round(min_v + (steps * step), 2)


# ---------------------------------------------------------------------------
# Core execution
# ---------------------------------------------------------------------------

def _build_limit_order(
    symbol: str,
    direction: str,
    lot_size: float,
    entry_price: float,
    stop_loss: float,
    take_profit: Optional[float],
):
    return SimpleNamespace(
        asset=symbol,
        side=direction,
        quantity=lot_size,
        order_type="limit",
        order_class="",
        limit_price=entry_price,
        stop_loss_price=float(stop_loss),
        take_profit_price=_optional_float(take_profit),
        strategy=WORKER_STRATEGY_NAME,
        status="new",
        identifier=None,
    )


def _execute_signal(
    broker: MT5Broker,
    signal: Dict[str, Any],
    account_id: str,
    default_risk: float,
) -> None:
    signal_id = str(signal.get("signal_id") or "")
    if not signal_id:
        logger.warning("Signal missing signal_id — skipping")
        return

    if signal.get("account_id") and str(signal["account_id"]) != str(account_id):
        return
    if (
        isinstance(signal.get("target_accounts"), list)
        and str(account_id) not in {str(x) for x in signal["target_accounts"]}
    ):
        return

    if _already_processed(signal_id, account_id):
        logger.info(f"[SKIP] signal_id={signal_id} already in terminal status")
        return

    _log_event(signal_id, account_id, "signal_received", {
        "scenario": signal.get("scenario"),
        "direction": signal.get("direction"),
    })

    _sleep_until(signal.get("execute_at"))

    direction = str(signal.get("direction", "")).lower()
    if direction not in {"buy", "sell"}:
        _upsert_execution(signal_id, account_id, {"status": "error", "error": "invalid direction"})
        _log_event(signal_id, account_id, "error", {"error": "invalid direction"})
        return

    symbol_raw = str(signal.get("symbol", ""))
    symbol = _normalize_symbol(symbol_raw)
    broker.select_symbol(symbol)

    entry_price = float(signal.get("entry_price") or 0)
    stop_loss = signal.get("sl_price")
    take_profit = _optional_float(signal.get("tp_price"))

    risk_amount = default_risk

    if stop_loss in (None, ""):
        _upsert_execution(signal_id, account_id, {"status": "error", "symbol": symbol, "error": "missing sl_price"})
        _log_event(signal_id, account_id, "error", {"error": "missing sl_price"})
        return

    if entry_price <= 0:
        _upsert_execution(signal_id, account_id, {"status": "error", "symbol": symbol, "error": "missing entry_price"})
        _log_event(signal_id, account_id, "error", {"error": "missing entry_price"})
        return

    lot_size = _compute_lot_size(symbol, entry_price, float(stop_loss), risk_amount)
    if lot_size <= 0:
        _upsert_execution(signal_id, account_id, {"status": "error", "symbol": symbol, "error": "lot_size computed as 0"})
        _log_event(signal_id, account_id, "error", {"error": "lot_size computed as 0"})
        return

    _log_event(signal_id, account_id, "lot_size_computed", {
        "risk_amount": risk_amount,
        "entry_price": entry_price,
        "sl_price": float(stop_loss),
        "lot_size": lot_size,
    })

    order = _build_limit_order(
        symbol=symbol,
        direction=direction,
        lot_size=lot_size,
        entry_price=entry_price,
        stop_loss=float(stop_loss),
        take_profit=take_profit,
    )

    _upsert_execution(signal_id, account_id, {
        "status": "sent",
        "symbol": symbol,
        "direction": direction,
        "entry_price": entry_price,
        "stop_loss": float(stop_loss),
        "take_profit": take_profit,
        "lot_size": lot_size,
        "submitted_at": _now(),
    })

    t_send = time.monotonic()
    submit_fn = getattr(broker, "submit_order", None)
    if callable(submit_fn):
        result_order = submit_fn(order)
    else:
        result_order = broker._submit_order(order)
    latency_ms = round((time.monotonic() - t_send) * 1000, 2)

    if result_order and getattr(result_order, "status", "") in {"filled", "submitted"}:
        status = "filled" if result_order.status == "filled" else "submitted"
        _upsert_execution(signal_id, account_id, {
            "status": status,
            "broker_order_id": str(getattr(result_order, "identifier", "") or ""),
            "latency_ms": latency_ms,
            "executed_at": _now(),
        })
        _log_event(signal_id, account_id, "order_result", {
            "status": status,
            "broker_order_id": getattr(result_order, "identifier", None),
            "latency_ms": latency_ms,
        })
        logger.info(
            f"[EXECUTED] signal_id={signal_id} status={status} "
            f"symbol={symbol} lots={lot_size} latency={latency_ms}ms"
        )
    else:
        err = getattr(result_order, "error", None) or "submit_order failed"
        _upsert_execution(signal_id, account_id, {
            "status": "rejected",
            "error": str(err),
            "latency_ms": latency_ms,
            "executed_at": _now(),
        })
        _log_event(signal_id, account_id, "order_result", {
            "status": "rejected",
            "error": str(err),
            "latency_ms": latency_ms,
        })
        logger.error(f"[REJECTED] signal_id={signal_id} error={err}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def run():
    parser = argparse.ArgumentParser(description="Per-account Redis worker for MT5 execution")
    parser.add_argument("--account-id", required=True, help="broker_accounts.id (UUID)")
    parser.add_argument("--channel", default=CHANNEL_DEFAULT, help="Redis pub/sub channel")
    args = parser.parse_args()

    account_id = str(args.account_id)

    cfg = _resolve_account_config(account_id)
    resolved = cfg["_resolved"]

    broker = MT5Broker(
        {
            "login": resolved["login"],
            "password": resolved["password"],
            "server": resolved["server"],
            "path": resolved["path"],
            "timezone": resolved["timezone"],
        }
    )

    _set_account_status(account_id, "ready", "Worker online")

    stop_event = threading.Event()
    heartbeat_thread = threading.Thread(
        target=_heartbeat_loop,
        args=(account_id, stop_event),
        daemon=True,
        name=f"heartbeat-{account_id[:8]}",
    )
    heartbeat_thread.start()
    logger.info(f"Heartbeat thread started (interval={HEARTBEAT_INTERVAL}s)")

    redis_url = _resolve_redis_url(cfg)
    redis_client = redis.Redis.from_url(redis_url, decode_responses=True)
    pubsub = redis_client.pubsub(ignore_subscribe_messages=True)
    pubsub.subscribe(args.channel)

    logger.info(
        f"[WORKER READY] account_id={account_id} channel={args.channel}"
    )

    try:
        for message in pubsub.listen():
            if message.get("type") != "message":
                continue
            raw = message.get("data")
            if not raw:
                continue
            try:
                signal = json.loads(raw)
                _execute_signal(
                    broker=broker,
                    signal=signal,
                    account_id=account_id,
                    default_risk=resolved["risk_amount"],
                )
            except Exception as e:
                logger.exception(f"[WORKER ERROR] {e}")

    except KeyboardInterrupt:
        logger.info("Shutdown signal received")

    finally:
        stop_event.set()
        heartbeat_thread.join(timeout=5)
        _set_account_status(account_id, "provisioned", "Worker offline")
        mt5.shutdown()
        logger.info("MT5 shutdown. Worker exited cleanly.")


def main():
    run()


if __name__ == "__main__":
    run()
