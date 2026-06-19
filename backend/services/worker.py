import argparse
import json
import threading
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import MetaTrader5 as mt5
import redis

from backend.brokers.mt5_broker import MetaTrader5
from backend.config.logger import setup_logger
from backend.config.secrets import get_azure_secret
from backend.config.supaclient import supabase
from backend.strategies.common import _calculate_take_profit
from backend.services.position_monitor import (
    HaltFlag,
    MonitorConfig,
    PositionMonitor,
    TrackedPosition,
)
from backend.services.vault import vault

logger = setup_logger(__name__)
EXIT_CONFIG_ERROR = 78
EXIT_RUNTIME_ERROR = 1

def _parse_iso(ts: str) -> datetime:
    ts = ts.replace("Z", "+00:00")
    dt = datetime.fromisoformat(ts)
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)

def _sleep_until(execute_at: Optional[str]) -> None:
    if not execute_at:
        logger.warning("Signal has no execute_at - executing immediately")
        return
    target = _parse_iso(execute_at)
    delay = (target - datetime.now(timezone.utc)).total_seconds()
    if delay > 0:
        logger.info(f"Holding {delay:.3f}s until execute_at={execute_at}")
        time.sleep(delay)
    else:
        logger.warning(f"execute_at already passed by {abs(delay):.3f}s - executing immediately")

def _pick(cfg: Dict[str, Any], *keys: str, default=None):
    for k in keys:
        if cfg.get(k) not in (None, ""):
            return cfg[k]
    return default

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()

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

    login = _pick(cfg, "login", "account_login", "account_number")
    password = _pick(cfg, "password", "account_password", "encrypted_password")
    server = _pick(cfg, "server", "account_server")
    path = _pick(cfg, "path", "terminal_path")
    timezone_name = _pick(cfg, "timezone", default="Africa/Lagos")

    if not login or not password or not server:
        raise RuntimeError(f"Missing login/password/server for account_id={account_id}")

    cfg["_resolved"] = {
        "login": int(login),
        "password": password,
        "server": server,
        "path": path,
        "timezone": timezone_name,
        "risk_amount": float(_pick(cfg, "risk_amount", default=25)),
        "rr_ratio": float(_pick(cfg, "rr_ratio", default=3.0)),
    }
    return cfg

def _resolve_redis_url(cfg: Dict[str, Any]) -> str:
    redis_url = get_azure_secret("REDIS-URL")
    if not redis_url:
        raise RuntimeError("Missing REDIS-URL secret in Azure Key Vault")
    if str(redis_url).startswith(("http://", "https://")):
        raise RuntimeError(
            "REDIS-URL must be a Redis URI (redis:// or rediss://), not an HTTP URL"
        )
    return redis_url

def _set_account_status(account_id: str, status: str, detail: str = "") -> None:
    """
    Flips broker_accounts.status and writes a status_detail note.
    Called at startup (→ ready), clean shutdown (→ provisioned), and on crash (→ error).
    """

    try:
        supabase.table("broker_accounts").update(
            {
                "status": status,
                "status_detail": detail,
                "last_heartbeat": _now(),
            }
        ).eq("id", account_id).execute()
        logger.info(f"[STATUS] account_id={account_id} -> {status} ({detail})")
    except Exception as e:
        logger.error(f"Failed to update account status: {e}")

def _heartbeat_loop(account_id: str, stop_event: threading.Event) -> None:
    """
    Background thread. Writes last_heartbeat every HEARTBEAT_INTERVAL seconds.
    Runs independently of the Redis listen loop so a slow/blocked signal
    never delays the heartbeat. Orchestrator uses stale heartbeats to detect
    hung or dead workers and restart them.
    """
    while not stop_event.is_set():
        try:
            supabase.table("broker_accounts").update(
                {"last_heartbeat": _now()}
            ).eq("id", account_id).execute()
        except Exception as e:
            logger.warning(f"Heartbeat write failed: {e}")
        stop_event.wait(30)

def _upsert_execution(signal_id: str, account_id: str, data: Dict[str, Any]) -> None:
    """
    Creates or updates the execution row for this (account, signal) pair.
    The UNIQUE constraint on (account_id, signal_id) makes this safe to call
    multiple times — later calls update the existing row in place.
 
    Status flow written here:
      pending → sent → filled | submitted | rejected | error
    """
    payload = {"signal_id": signal_id, "account_id": account_id, **data}
    supabase.table("executions").upsert(
        payload,
        on_conflict="signal_id,account_id",
    ).execute()

def _log_event(
    signal_id: str,
    account_id: str,
    event_type: str,
    detail: Optional[dict] = None
) -> None:
    """
    Appends one row to execution_events. Never raises — worker stays alive
    even if this table is unavailable.
 
    event_type values:
      signal_received   — message landed on this worker
      lot_size_computed — sizing calculated, about to send
      order_result      — MT5 responded (filled / submitted / rejected)
      error             — anything that aborted the flow
 
    detail is a JSONB payload used by the Glass Box dashboard for chart replay.
    """
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
    except Exception:
        pass

def _already_processed(signal_id: str, account_id: str) -> bool:
    """
    Returns True if this (account, signal) pair already has a terminal status.
    Prevents re-executing on worker restart or duplicate Redis delivery.
    """
    terminal = {"filled", "submitted", "rejected", "error", "skipped"}
    row = (
        supabase.table("executions")
        .select("status")
        .eq("signal_id",  signal_id)
        .eq("account_id", account_id)
        .limit(1)
        .execute()
    )
    if not getattr(row, "data", None):
        return False
    return row.data[0].get("status") in terminal

def _compute_lot_size(
    symbol:      str,
    entry_price: float,
    stop_loss:   float,
    risk_amount: float,
) -> float:
    """
    lot_size = risk_amount / (sl_distance * contract_size)
 
    contract_size is read from the broker (100 000 for standard forex lots,
    varies for indices, metals, crypto). This makes the formula correct for
    any instrument without hardcoding.
 
    Returns 0.0 if the result would be below the broker's volume_min —
    caller treats 0.0 as an unexecutable signal and writes status=error.
    """
    sl_distance = abs(entry_price - stop_loss)
    if sl_distance <= 0:
        return 0.0
 
    info = mt5.symbol_info(symbol)
    if info is None:
        return 0.0
 
    contract_size = float(getattr(info, "trade_contract_size", 100_000) or 100_000)
    raw_lots      = risk_amount / (sl_distance * contract_size)
 
    step  = float(getattr(info, "volume_step", 0.01) or 0.01)
    min_v = float(getattr(info, "volume_min",  0.01) or 0.01)
    max_v = float(getattr(info, "volume_max",  100.0) or 100.0)
 
    if raw_lots < min_v:
        return 0.0
 
    raw_lots = min(raw_lots, max_v)
    steps    = int((raw_lots - min_v) / step)
    return round(min_v + (steps * step), 2)


def _start_monitor(account: Dict[str, Any], halt_flag: HaltFlag) -> PositionMonitor:
    """
    Start per-account position monitor after MT5 initializes successfully.
    """
    info = mt5.account_info()
    if info is None:
        raise RuntimeError("Cannot start monitor - mt5.account_info() is None")

    account_number_raw = _pick(account, "account_number", "login", "account_login", default=0)
    account_number = int(account_number_raw) if account_number_raw else 0
    symbol = str(_pick(account, "symbol", default=""))

    monitor_config = MonitorConfig(
        account_id=str(account["id"]),
        account_number=account_number,
        symbol=symbol,
        rr_ratio=float(_pick(account, "rr_ratio", default=3.0)),
        breakeven_buffer_ticks=int(_pick(account, "breakeven_buffer_ticks", default=10)),
        max_daily_drawdown_pct=float(_pick(account, "max_daily_drawdown_pct", default=0.02)),
        poll_interval_seconds=5.0,
    )

    monitor = PositionMonitor(
        config=monitor_config,
        halt_flag=halt_flag,
        supabase=supabase,
    )
    monitor.seed_day_start_balance(float(info.balance))
    monitor.daemon = True
    monitor.start()
    logger.info(f"[WORKER] Position monitor started for account {account_number}")
    return monitor


def _register_fill_with_monitor(
    monitor: Optional[PositionMonitor],
    ticket: int,
    symbol: str,
    side: str,           # 'long' | 'short'
    entry_price: float,
    sl_price: float,
) -> None:
    """
    Register an order/position with monitor so breakeven logic can track it.
    """
    if monitor is None:
        logger.warning("[WORKER] Monitor not running - skipping position registration")
        return

    sl_distance = abs(entry_price - sl_price)
    if sl_distance <= 0:
        logger.warning(f"[WORKER] Invalid SL distance for ticket={ticket}; skipping monitor tracking")
        return

    tracked = TrackedPosition(
        ticket=ticket,
        symbol=symbol,
        side=side,
        entry_price=entry_price,
        sl_distance=sl_distance,
    )
    monitor.track(tracked)


def _execute_signal(
    broker:       MetaTrader5,
    signal:       Dict[str, Any],
    account_id:   str,
    default_risk: float,
    default_rr_ratio: float,
    halt_flag:    Optional[HaltFlag] = None,
    monitor:      Optional[PositionMonitor] = None,
) -> None:
    """
    Full lifecycle for one signal on one account.
 
    Step 1 — Guard checks   : signal_id present, account targeting, dedup
    Step 2 — Timing gate    : sleep until execute_at (ICT prop-firm safe delay)
    Step 3 — Lot sizing     : risk_amount / (sl_distance * contract_size)
    Step 4 — Pending limit  : TRADE_ACTION_PENDING + BUY_LIMIT / SELL_LIMIT
                              Price must come TO entry_price — we never chase
    Step 5 — Record outcome : executions updated, execution_events appended
    """
    signal_id = str(signal.get("signal_id") or "")
    if not signal_id:
        logger.warning("Signal missing signal_id - skipping")
        return
 
    # --- Optional account targeting ---
    if signal.get("account_id") and str(signal["account_id"]) != str(account_id):
        return
    if (
        isinstance(signal.get("target_accounts"), list)
        and str(account_id) not in {str(x) for x in signal["target_accounts"]}
    ):
        return
 
    # --- Deduplication ---
    if _already_processed(signal_id, account_id):
        logger.info(f"[SKIP] signal_id={signal_id} already in terminal status")
        return
 
    # --- Signal received ---
    _log_event(signal_id, account_id, "signal_received", {
        "scenario":  signal.get("scenario"),
        "direction": signal.get("direction"),
    })
 
    # --- Timing gate ---
    _sleep_until(signal.get("execute_at"))
    if halt_flag is not None and halt_flag.is_halted():
        logger.warning(
            f"[WORKER] account={account_id} HALTED after delay - skipping signal {signal_id}"
        )
        _upsert_execution(signal_id, account_id, {
            "status": "skipped",
            "error": "account halted by drawdown guard",
        })
        _log_event(signal_id, account_id, "error", {"error": "account halted by drawdown guard"})
        return
 
    # --- Validate direction ---
    direction = str(signal.get("direction", "")).lower()
    if direction not in {"buy", "sell"}:
        _upsert_execution(signal_id, account_id, {"status": "error", "error": "invalid direction"})
        _log_event(signal_id, account_id, "error", {"error": "invalid direction"})
        return
 
    # --- Symbol ---
    symbol_raw = str(signal.get("symbol", ""))
    symbol     = broker._symbol(symbol_raw)
    broker.select_symbol(symbol)
 
    # --- Prices — keys match verdict.py field names exactly ---
    entry_price = float(signal.get("entry_price") or 0)
    stop_loss   = _pick(signal, "stop_loss", "sl_price")
    take_profit = _pick(signal, "take_profit", "tp_price")
 
    # risk_amount always comes from broker_accounts (default_risk)
    # verdict carries risk_in_price for lot sizing transparency but
    # the account's configured risk_amount is the authoritative sizing input
    risk_amount = default_risk
    rr_ratio = float(_pick(signal, "rr_ratio", "reward_risk_ratio", default=default_rr_ratio))
 
    if stop_loss in (None, ""):
        _upsert_execution(signal_id, account_id, {"status": "error", "symbol": symbol, "error": "missing stop_loss"})
        _log_event(signal_id, account_id, "error", {"error": "missing stop_loss"})
        return
 
    if entry_price <= 0:
        _upsert_execution(signal_id, account_id, {"status": "error", "symbol": symbol, "error": "missing entry_price"})
        _log_event(signal_id, account_id, "error", {"error": "missing entry_price"})
        return

    if take_profit in (None, ""):
        take_profit = _calculate_take_profit(entry_price, float(stop_loss), direction, rr_ratio)
        if take_profit is None:
            _upsert_execution(signal_id, account_id, {"status": "error", "symbol": symbol, "error": "invalid take_profit calculation"})
            _log_event(signal_id, account_id, "error", {"error": "invalid take_profit calculation"})
            return
 
    # --- Lot sizing ---
    lot_size = _compute_lot_size(symbol, entry_price, float(stop_loss), risk_amount)
    if lot_size <= 0:
        _upsert_execution(signal_id, account_id, {"status": "error", "symbol": symbol, "error": "lot_size computed as 0"})
        _log_event(signal_id, account_id, "error", {"error": "lot_size computed as 0"})
        return
 
    _log_event(signal_id, account_id, "lot_size_computed", {
        "risk_amount": risk_amount,
        "entry_price": entry_price,
        "stop_loss":   float(stop_loss),
        "lot_size":    lot_size,
    })
 
    # --- Build pending limit order ---
    # TRADE_ACTION_PENDING + BUY_LIMIT / SELL_LIMIT:
    # order sits at entry_price and only fills when price returns to that level.
    # This is the correct ICT execution model — we never chase with a market order.
    order_type = mt5.ORDER_TYPE_BUY_LIMIT if direction == "buy" else mt5.ORDER_TYPE_SELL_LIMIT
 
    request = {
        "action":       mt5.TRADE_ACTION_PENDING,
        "symbol":       symbol,
        "volume":       lot_size,
        "type":         order_type,
        "price":        entry_price,
        "sl":           float(stop_loss),
        "tp":           float(take_profit) if take_profit not in (None, "") else 0.0,
        "deviation":    20,
        "type_time":    mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
        "comment":      f"signal:{signal_id[:8]}",
    }
 
    # --- Mark as sent before calling order_send ---
    # If the worker crashes between here and the result write, the orchestrator
    # can detect rows stuck at "sent" and reconcile them against MT5 history.
    _upsert_execution(signal_id, account_id, {
        "status":       "sent",
        "symbol":       symbol,
        "direction":    direction,
        "entry_price":  entry_price,
        "stop_loss":    float(stop_loss),
        "take_profit":  float(take_profit) if take_profit not in (None, "") else None,
        "lot_size":     lot_size,
        "submitted_at": _now(),
    })
 
    t_send = time.monotonic()
    result = mt5.order_send(request)
    latency_ms = round((time.monotonic() - t_send) * 1000, 2)
 
    # --- Result handling ---
    done_codes  = {mt5.TRADE_RETCODE_DONE}
    placed_code = getattr(mt5, "TRADE_RETCODE_PLACED", None)
    if placed_code:
        done_codes.add(placed_code)
 
    if result and result.retcode in done_codes:
        status = "filled" if result.retcode == mt5.TRADE_RETCODE_DONE else "submitted"
        _upsert_execution(signal_id, account_id, {
            "status":          status,
            "broker_order_id": str(result.order or ""),
            "fill_price":      float(result.price or 0),
            "retcode":         int(result.retcode),
            "latency_ms":      latency_ms,
            "executed_at":     _now(),
        })
        _log_event(signal_id, account_id, "order_result", {
            "status":          status,
            "broker_order_id": result.order,
            "fill_price":      result.price,
            "retcode":         result.retcode,
            "latency_ms":      latency_ms,
        })
        logger.info(
            f"[EXECUTED] signal_id={signal_id} status={status} "
            f"symbol={symbol} lots={lot_size} latency={latency_ms}ms"
        )
        ticket = int(result.order or 0)
        if status == "filled" and ticket > 0:
            side = "long" if direction == "buy" else "short"
            tracked_entry = float(result.price or 0) if status == "filled" else entry_price
            if tracked_entry <= 0:
                tracked_entry = entry_price
            _register_fill_with_monitor(
                monitor=monitor,
                ticket=ticket,
                symbol=symbol,
                side=side,
                entry_price=float(tracked_entry),
                sl_price=float(stop_loss),
            )
  
    else:
        err  = getattr(result, "comment", "order_send failed")
        code = int(getattr(result, "retcode", -1)) if result else -1
        _upsert_execution(signal_id, account_id, {
            "status":      "rejected",
            "retcode":     code,
            "error":       str(err),
            "latency_ms":  latency_ms,
            "executed_at": _now(),
        })
        _log_event(signal_id, account_id, "order_result", {
            "status":     "rejected",
            "retcode":    code,
            "error":      str(err),
            "latency_ms": latency_ms,
        })
        logger.error(f"[REJECTED] signal_id={signal_id} retcode={code} error={err}")


def _on_signal_received(
    raw_message: Dict[str, Any],
    broker: MetaTrader5,
    account_id: str,
    account_label: str,
    default_risk: float,
    default_rr_ratio: float,
    halt_flag: HaltFlag,
    monitor: Optional[PositionMonitor],
) -> None:
    # --- HALT GATE ---
    if halt_flag.is_halted():
        logger.warning(
            f"[WORKER] account={account_label} HALTED - discarding signal "
            f"{raw_message.get('signal_id', '?')}"
        )
        return

    _execute_signal(
        broker=broker,
        signal=raw_message,
        account_id=account_id,
        default_risk=default_risk,
        default_rr_ratio=default_rr_ratio,
        halt_flag=halt_flag,
        monitor=monitor,
    )


def main():
    parser = argparse.ArgumentParser(description="Per-account Redis worker for MT5 execution")
    parser.add_argument("--account-id", required=True, help="broker_accounts.id (UUID)")
    parser.add_argument("--channel", default="signals", help="Redis pub/sub channel")
    args = parser.parse_args()

    account_id = str(args.account_id)
    account_label = account_id
    stop_event: Optional[threading.Event] = None
    heartbeat_thread: Optional[threading.Thread] = None
    monitor: Optional[PositionMonitor] = None
    worker_online = False
    exit_code = 0

    try:
        # --- Load account config from Supabase ---
        cfg = _resolve_account_config(account_id)
        resolved = cfg["_resolved"]
        account_label = str(_pick(cfg, "account_number", "login", default=account_id))

        password_secret_name = str(resolved["password"])
        try:
            password = vault.get_secret(password_secret_name)
        except RuntimeError as exc:
            raise RuntimeError(
                f"Vault lookup failed for password secret '{password_secret_name}': {exc}"
            ) from exc

        # --- Connect MT5 terminal once at startup — never at signal time ---
        broker = MetaTrader5(
            {
                "login":    resolved["login"],
                "password": password,
                "server":   resolved["server"],
                "path":     resolved["path"],
                "timezone": resolved["timezone"],
            }
        )
        logger.info(
            f"[WORKER] MT5 initialised — account={resolved['login']} server={resolved['server']}"
        )

        halt_flag = HaltFlag()
        monitor = _start_monitor(cfg, halt_flag)

        # --- Mark account as ready in Supabase ---
        _set_account_status(account_id, "ready", "Worker online")
        worker_online = True

        # --- Start heartbeat background thread ---
        stop_event = threading.Event()
        heartbeat_thread = threading.Thread(
            target=_heartbeat_loop,
            args=(account_id, stop_event),
            daemon=True,
            name=f"heartbeat-{account_id[:8]}",
        )
        heartbeat_thread.start()
        logger.info(f"Heartbeat thread started (interval=30s)")

        # --- Connect Redis ---
        redis_url = _resolve_redis_url(cfg)
        redis_client = redis.Redis.from_url(redis_url, decode_responses=True)
        pubsub = redis_client.pubsub(ignore_subscribe_messages=True)
        pubsub.subscribe(args.channel)

        logger.info(
            f"[WORKER READY] account_id={account_id} login={resolved['login']} "
            f"server={resolved['server']} channel={args.channel}"
        )

        # --- Main listen loop ---
        for message in pubsub.listen():
            if message.get("type") != "message":
                continue
            raw = message.get("data")
            if not raw:
                continue
            try:
                signal = json.loads(raw)
                _on_signal_received(
                    raw_message=signal,
                    broker=broker,
                    account_id=account_id,
                    account_label=account_label,
                    default_risk=resolved["risk_amount"],
                    default_rr_ratio=resolved["rr_ratio"],
                    halt_flag=halt_flag,
                    monitor=monitor,
                )
            except Exception as e:
                logger.exception(f"[WORKER ERROR] {e}")

    except KeyboardInterrupt:
        logger.info("Shutdown signal received")

    except RuntimeError as exc:
        exit_code = EXIT_CONFIG_ERROR
        detail = f"Startup configuration error: {exc}"
        _set_account_status(account_id, "error", detail[:500])
        logger.exception(f"[WORKER FATAL] account={account_label} {detail}")

    except Exception as exc:
        exit_code = EXIT_RUNTIME_ERROR
        detail = f"Worker crashed: {type(exc).__name__}: {exc}"
        _set_account_status(account_id, "error", detail[:500])
        logger.exception(f"[WORKER FATAL] account={account_label} {detail}")

    finally:
        # --- Clean shutdown ---
        if stop_event is not None:
            stop_event.set()
        if heartbeat_thread is not None:
            heartbeat_thread.join(timeout=5)
        if monitor is not None:
            monitor.stop()
            monitor.join(timeout=5)
        if worker_online and exit_code == 0:
            _set_account_status(account_id, "provisioned", "Worker offline")
        mt5.shutdown()
        logger.info("MT5 shutdown. Worker exited.")

    return exit_code
 
 
if __name__ == "__main__":
    raise SystemExit(main())
