import argparse
import json
import threading
import time
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, Optional

import MetaTrader5 as mt5
import redis

from supabase import create_client

from backend.brokers.mt5_broker import MetaTrader5
from backend.config.logger import setup_logger
from backend.config.secrets import get_azure_secret
from backend.config.supaclient import supabase, SUPABASE_URL
from backend.strategies.common import _calculate_take_profit
from backend.services.position_monitor import (
    HaltFlag,
    MonitorConfig,
    PositionMonitor,
    TrackedPosition,
)
from backend.services.vault import vault
from backend.services.telegram_notifier import (
    notify_order_filled,
    notify_order_rejected,
    notify_worker_online,
    notify_worker_offline,
)

logger = setup_logger("workers")
EXIT_CONFIG_ERROR = 78
EXIT_RUNTIME_ERROR = 1

def _get_admin_supabase():
    """
    Service-role client that bypasses RLS.
    Used for all worker writes (executions, execution_events, broker_accounts status).
    Falls back to the anon client if the secret hasn't been added yet.
    """
    url = SUPABASE_URL
    key = get_azure_secret("SUPABASE-SERVICE-ROLE-KEY") or get_azure_secret("SUPABASE-KEY")
    return create_client(url, key)

_admin_db = None

def _db():
    """Lazy singleton for the admin Supabase client."""
    global _admin_db
    if _admin_db is None:
        _admin_db = _get_admin_supabase()
    return _admin_db

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
        _db().table("broker_accounts")
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
        _db().table("broker_accounts").update(
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
            _db().table("broker_accounts").update(
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
    _db().table("executions").upsert(
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
        _db().table("execution_events").insert(
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

def _claim_signal(signal_id: str, account_id: str) -> bool:
    """
    Atomically claim a (signal_id, account_id) pair for execution.

    Inserts a fresh `pending` row. The UNIQUE(signal_id, account_id) constraint
    makes this the single source of truth for "who owns this signal" — if the
    row already exists (claimed by a previous delivery, a worker restart, or the
    durability backstop), the insert raises and we return False.

    This replaces the old read-then-act dedup, which had a race window where the
    Redis listener and the backstop sweep could both see "no terminal row" and
    execute the same signal twice.

    Returns True if THIS caller won the claim and should proceed to execute.
    """
    try:
        _db().table("executions").insert(
            {
                "signal_id": signal_id,
                "account_id": account_id,
                "status": "pending",
            }
        ).execute()
        return True
    except Exception as e:
        err_str = str(e)
        # Unique-constraint violation = already claimed by another path — normal, skip silently.
        # Anything else (RLS denial, network error, schema mismatch) = real problem — log it.
        if "duplicate" in err_str.lower() or "unique" in err_str.lower() or "23505" in err_str:
            logger.debug(f"[CLAIM] signal_id={signal_id} already claimed (duplicate key)")
        else:
            logger.error(
                f"[CLAIM FAILED] signal_id={signal_id} account_id={account_id} "
                f"— insert into executions was blocked: {e}. "
                f"Check Supabase RLS on the executions table or confirm SUPABASE-KEY "
                f"is the service_role key (not anon)."
            )
        return False

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
 
    # --- Atomic claim (dedup across Redis delivery + backstop sweep) ---
    if not _claim_signal(signal_id, account_id):
        logger.info(f"[SKIP] signal_id={signal_id} already claimed/processed")
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
        notify_order_filled(
            symbol=symbol,
            direction=direction,
            lot_size=lot_size,
            fill_price=float(result.price or entry_price),
            sl=float(stop_loss),
            tp=float(take_profit) if take_profit not in (None, "") else 0.0,
            broker_order_id=str(result.order or ""),
            latency_ms=latency_ms,
            signal_id=signal_id,
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
        notify_order_rejected(
            symbol=symbol,
            direction=direction,
            retcode=code,
            error=str(err),
            signal_id=signal_id,
        )


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


def _backstop_loop(
    broker: MetaTrader5,
    account_id: str,
    account_label: str,
    default_risk: float,
    default_rr_ratio: float,
    halt_flag: HaltFlag,
    monitor: Optional[PositionMonitor],
    stop_event: threading.Event,
    interval_seconds: int = 60,
    lookback_seconds: int = 900,
) -> None:
    """
    Durability backstop for Redis pub/sub message loss.

    Redis pub/sub is fire-and-forget: a signal published while this worker is
    not subscribed (process down, connection dropped, mid-reconnect) is gone
    forever. This thread periodically reads recent rows from the `signals`
    table and executes any that have no `executions` row for this account yet.

    Combined with the atomic _claim_signal(), this is safe to run alongside the
    live Redis listener — whichever path reaches a signal first wins the claim
    and the other path skips it. Lookback bounds how stale a recovered signal
    can be (default 15 min) so we never act on ancient setups.
    """
    while not stop_event.is_set():
        stop_event.wait(interval_seconds)
        if stop_event.is_set():
            break
        try:
            cutoff = (
                datetime.now(timezone.utc) - timedelta(seconds=lookback_seconds)
            ).isoformat()
            rows = (
                _db().table("signals")
                .select("*")
                .gte("created_at", cutoff)
                .execute()
            )
            for sig in (getattr(rows, "data", None) or []):
                if stop_event.is_set():
                    break
                sid = str(sig.get("signal_id") or "")
                if not sid:
                    continue
                existing = (
                    _db().table("executions")
                    .select("signal_id")
                    .eq("signal_id", sid)
                    .eq("account_id", account_id)
                    .limit(1)
                    .execute()
                )
                if getattr(existing, "data", None):
                    continue  # already handled (or claimed) — nothing to recover
                logger.warning(
                    f"[BACKSTOP] Recovering unprocessed signal_id={sid} "
                    f"symbol={sig.get('symbol')} — missed via Redis pub/sub"
                )
                _on_signal_received(
                    raw_message=sig,
                    broker=broker,
                    account_id=account_id,
                    account_label=account_label,
                    default_risk=default_risk,
                    default_rr_ratio=default_rr_ratio,
                    halt_flag=halt_flag,
                    monitor=monitor,
                )
        except Exception as e:
            logger.warning(f"[BACKSTOP] sweep failed: {e}")


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
        notify_worker_online(
            account_number=resolved["login"],
            server=resolved["server"],
            account_id=account_id,
        )

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

        # --- Resolve Redis endpoint ---
        redis_url = _resolve_redis_url(cfg)
        # Log the scheme (NOT the credentials) so the endpoint type is verifiable
        # in production: rediss:// / redis:// support pub/sub; an HTTP/REST URL
        # would not — and _resolve_redis_url already rejects that case.
        scheme = str(redis_url).split("://", 1)[0]
        logger.info(f"[WORKER] Redis endpoint scheme={scheme}:// channel={args.channel}")

        # --- Durability backstop: recovers signals missed by pub/sub ---
        backstop_thread = threading.Thread(
            target=_backstop_loop,
            args=(
                broker, account_id, account_label,
                resolved["risk_amount"], resolved["rr_ratio"],
                halt_flag, monitor, stop_event,
            ),
            daemon=True,
            name=f"backstop-{account_id[:8]}",
        )
        backstop_thread.start()
        logger.info("Backstop sweep thread started (interval=60s, lookback=900s)")

        # --- Resilient Redis listen loop ---
        # Managed Redis (Upstash etc.) silently drops idle pub/sub connections.
        # The old blocking pubsub.listen() would then stop yielding WITHOUT
        # raising, leaving the worker "alive" (heartbeat still writing) but deaf.
        # We now:
        #   - enable socket_keepalive + health_check_interval so dead sockets
        #     are detected, and
        #   - poll with get_message(timeout) inside a reconnect loop so a dropped
        #     connection re-subscribes instead of going silent.
        backoff = 1
        while not stop_event.is_set():
            pubsub = None
            try:
                redis_client = redis.Redis.from_url(
                    redis_url,
                    decode_responses=True,
                    socket_keepalive=True,
                    health_check_interval=30,
                    socket_connect_timeout=10,
                )
                pubsub = redis_client.pubsub(ignore_subscribe_messages=True)
                pubsub.subscribe(args.channel)
                logger.info(
                    f"[WORKER READY] account_id={account_id} login={resolved['login']} "
                    f"server={resolved['server']} channel={args.channel}"
                )
                backoff = 1  # reset after a clean (re)subscribe

                while not stop_event.is_set():
                    message = pubsub.get_message(
                        ignore_subscribe_messages=True, timeout=1.0
                    )
                    if message is None:
                        continue  # idle tick — lets health_check fire
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

            except Exception as e:
                logger.error(
                    f"[WORKER] Redis subscription dropped: {e} — "
                    f"reconnecting in {backoff}s (backstop still covering signals)"
                )
                time.sleep(backoff)
                backoff = min(backoff * 2, 30)
            finally:
                if pubsub is not None:
                    try:
                        pubsub.close()
                    except Exception:
                        pass

    except KeyboardInterrupt:
        logger.info("Shutdown signal received")

    except RuntimeError as exc:
        exit_code = EXIT_CONFIG_ERROR
        detail = f"Startup configuration error: {exc}"
        _set_account_status(account_id, "error", detail[:500])
        logger.exception(f"[WORKER FATAL] account={account_label} {detail}")
        notify_worker_offline(
            account_number=int(account_label) if account_label.isdigit() else 0,
            reason=detail[:200],
            account_id=account_id,
        )

    except Exception as exc:
        exit_code = EXIT_RUNTIME_ERROR
        detail = f"Worker crashed: {type(exc).__name__}: {exc}"
        _set_account_status(account_id, "error", detail[:500])
        logger.exception(f"[WORKER FATAL] account={account_label} {detail}")
        notify_worker_offline(
            account_number=int(account_label) if account_label.isdigit() else 0,
            reason=detail[:200],
            account_id=account_id,
        )

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
            notify_worker_offline(
                account_number=int(account_label) if account_label.isdigit() else 0,
                reason="Clean shutdown",
                account_id=account_id,
            )
        mt5.shutdown()
        logger.info("MT5 shutdown. Worker exited.")

    return exit_code
 
 
if __name__ == "__main__":
    raise SystemExit(main())
