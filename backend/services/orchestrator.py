# /home/runner/work/trade-bot/trade-bot/backend/runners/orchestrator.py
"""
orchestrator.py — Glass Box Trading Engine

Single entry point for the full engine. Spawns and supervises:

  1. One worker.py subprocess per runnable broker account — immediately at startup.
  2. One strategy runner per market, derived dynamically from the union of all
     accounts' enabled_markets columns — staggered at scheduled WAT times:
         EURUSD  → 08:40 WAT
         XAUUSD  → 08:45 WAT
     Only runners for markets that at least one account has enabled are launched.
     Markets with no runner module (NAS100, US30, …) are noted and skipped.

Responsibilities:
  - Query broker_accounts for all runnable accounts + their enabled_markets
  - Spawn workers immediately; spawn strategy runners at their scheduled time
  - Monitor all subprocesses — restart crashed workers/runners with backoff
  - Propagate clean shutdown (SIGINT / SIGTERM) to all subprocesses
  - Log a unified process table on startup and after every restart event

Usage:
    python -m backend.services.orchestrator
    python -m backend.services.orchestrator --channel signals --restart-limit 5
"""

import argparse
import signal
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta, time as dtime
from typing import Dict, List, Optional, Set

from backend.config.logger import setup_logger
from backend.config.markets import markets_for_plan
from backend.config.supaclient import supabase

logger = setup_logger("orchestrator")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

WORKER_MODULE         = "backend.services.worker"
POLL_INTERVAL         = 5      # seconds between health checks
BACKOFF_BASE          = 5      # initial restart delay in seconds
BACKOFF_MAX           = 300    # cap restart delay at 5 minutes
DEFAULT_RESTART_LIMIT = 10     # max restarts per subprocess (0 = unlimited)
STALE_HEARTBEAT_SEC   = 90
STALE_KILL_SEC        = 300
NON_RETRYABLE_EXIT_CODES = {78}

WAT = timezone(timedelta(hours=1), name="WAT")

# Full catalogue of strategy runners. Keys are canonical market names (matching
# broker_accounts.enabled_markets values). Only entries whose market appears in
# the union of all accounts' enabled_markets will be spawned.
# Add new runners here as they ship; hour/minute is the WAT launch time.
MARKET_RUNNER_CATALOGUE: Dict[str, dict] = {
    "EURUSD": {"module": "backend.runners.eurusd", "hour": 8, "minute": 40},
    "XAUUSD": {"module": "backend.runners.xauusd", "hour": 8, "minute": 45},
    # Future runners — declare here when the module exists:
    # "NAS100": {"module": "backend.runners.nas100", "hour": 8, "minute": 50},
    # "US30":   {"module": "backend.runners.us30",   "hour": 8, "minute": 55},
    # "SPX500": {"module": "backend.runners.spx500", "hour": 9, "minute":  0},
    # "BTCUSD": {"module": "backend.runners.btcusd", "hour": 9, "minute":  5},
    # "ETHUSD": {"module": "backend.runners.ethusd", "hour": 9, "minute": 10},
}


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class WorkerProcess:
    account_id:    str
    account_num:   str
    channel:       str
    process:       Optional[subprocess.Popen] = field(default=None, repr=False)
    restart_count: int = 0
    backoff:       float = BACKOFF_BASE
    last_restart:  Optional[datetime] = None
    disabled:      bool = False


@dataclass
class StrategyProcess:
    name:           str           # canonical market name, e.g. "EURUSD"
    module:         str           # python -m <module>
    scheduled_time: dtime         # WAT time to first spawn
    process:        Optional[subprocess.Popen] = field(default=None, repr=False)
    spawned:        bool = False  # True once first spawn has happened
    restart_count:  int = 0
    backoff:        float = BACKOFF_BASE
    last_restart:   Optional[datetime] = None
    disabled:       bool = False


# ---------------------------------------------------------------------------
# Supabase helpers
# ---------------------------------------------------------------------------

def _load_runnable_accounts() -> list[dict]:
    """Fetch all broker_accounts rows in a runnable state or force_spawn=true."""
    res = (
        supabase.table("broker_accounts")
        .select("id, account_number, status, force_spawn, plan, enabled_markets")
        .or_("status.in.(provisioned,authenticated,ready),force_spawn.eq.true")
        .execute()
    )
    return res.data or []


def _union_enabled_markets(accounts: list[dict]) -> Set[str]:
    """
    Compute the union of all enabled_markets across all runnable accounts.
    Falls back to plan defaults when an account's enabled_markets is empty.
    Returns canonical market names (e.g. {"EURUSD", "XAUUSD"}).
    """
    union: Set[str] = set()
    for acct in accounts:
        markets = acct.get("enabled_markets") or []
        if not markets:
            plan = str(acct.get("plan") or "starter").lower()
            markets = markets_for_plan(plan)
        union.update(str(m).upper() for m in markets)
    return union


def _clear_force_spawn_flag(account_id: str) -> None:
    try:
        supabase.table("broker_accounts").update(
            {"force_spawn": False}
        ).eq("id", account_id).execute()
    except Exception as e:
        logger.warning(f"Failed to clear force_spawn for account {account_id}: {e}")


def _mark_account_error(account_id: str, detail: str) -> None:
    try:
        existing_detail = ""
        current = (
            supabase.table("broker_accounts")
            .select("status_detail")
            .eq("id", account_id)
            .limit(1)
            .execute()
        )
        if getattr(current, "data", None):
            existing_detail = str(current.data[0].get("status_detail") or "").strip()

        final_detail = detail
        if existing_detail and detail not in existing_detail:
            final_detail = f"{existing_detail} | {detail}"

        supabase.table("broker_accounts").update(
            {"status": "error", "status_detail": final_detail[:500]}
        ).eq("id", account_id).execute()
    except Exception as e:
        logger.error(f"Failed to mark account {account_id} as error: {e}")


def _check_stale_heartbeats(workers: Dict[str, WorkerProcess]) -> None:
    account_ids = list(workers.keys())
    if not account_ids:
        return
    try:
        res = (
            supabase.table("broker_accounts")
            .select("id, last_heartbeat")
            .in_("id", account_ids)
            .execute()
        )
        now = datetime.now(timezone.utc)
        for row in (res.data or []):
            hb = row.get("last_heartbeat")
            if not hb:
                continue
            last = datetime.fromisoformat(hb.replace("Z", "+00:00"))
            age  = (now - last).total_seconds()
            if age > STALE_HEARTBEAT_SEC:
                acct  = workers.get(row["id"])
                label = acct.account_num if acct else row["id"]
                if age > STALE_KILL_SEC and acct and acct.process and acct.process.poll() is None:
                    logger.warning(
                        f"[STALE HEARTBEAT] account={label} last_heartbeat={age:.0f}s ago — "
                        f"killing hung worker"
                    )
                    acct.process.kill()
                else:
                    logger.warning(
                        f"[STALE HEARTBEAT] account={label} last_heartbeat={age:.0f}s ago — "
                        f"worker may be hung"
                    )
    except Exception as e:
        logger.warning(f"Heartbeat check failed: {e}")


# ---------------------------------------------------------------------------
# Worker lifecycle
# ---------------------------------------------------------------------------

def _spawn_worker(wp: WorkerProcess) -> None:
    cmd = [sys.executable, "-m", WORKER_MODULE, "--account-id", wp.account_id, "--channel", wp.channel]
    wp.process      = subprocess.Popen(cmd)
    wp.last_restart = datetime.now(WAT)
    logger.info(f"[SPAWN] account={wp.account_num} pid={wp.process.pid} restarts={wp.restart_count}")


def _restart_worker(wp: WorkerProcess, restart_limit: int) -> None:
    if restart_limit > 0 and wp.restart_count >= restart_limit:
        logger.error(f"[DISABLED] account={wp.account_num} hit restart limit ({restart_limit}) — giving up")
        wp.disabled = True
        _mark_account_error(wp.account_id, f"Worker disabled after {restart_limit} restarts")
        return

    logger.warning(f"[RESTART] account={wp.account_num} backoff={wp.backoff:.0f}s restart #{wp.restart_count + 1}")
    time.sleep(wp.backoff)
    wp.restart_count += 1
    wp.backoff        = min(wp.backoff * 2, BACKOFF_MAX)
    _spawn_worker(wp)


# ---------------------------------------------------------------------------
# Strategy runner lifecycle
# ---------------------------------------------------------------------------

def _spawn_strategy(sp: StrategyProcess) -> None:
    cmd = [sys.executable, "-m", sp.module]
    sp.process      = subprocess.Popen(cmd)
    sp.spawned      = True
    sp.last_restart = datetime.now(WAT)
    logger.info(
        f"[STRATEGY SPAWN] market={sp.name} module={sp.module} "
        f"pid={sp.process.pid} restarts={sp.restart_count}"
    )


def _restart_strategy(sp: StrategyProcess, restart_limit: int) -> None:
    if restart_limit > 0 and sp.restart_count >= restart_limit:
        logger.error(f"[STRATEGY DISABLED] market={sp.name} hit restart limit ({restart_limit}) — giving up")
        sp.disabled = True
        return

    logger.warning(f"[STRATEGY RESTART] market={sp.name} backoff={sp.backoff:.0f}s restart #{sp.restart_count + 1}")
    time.sleep(sp.backoff)
    sp.restart_count += 1
    sp.backoff        = min(sp.backoff * 2, BACKOFF_MAX)
    _spawn_strategy(sp)


# ---------------------------------------------------------------------------
# Shutdown
# ---------------------------------------------------------------------------

def _shutdown_all(workers: Dict[str, WorkerProcess], strategies: List[StrategyProcess], timeout: int = 10) -> None:
    all_procs: list[tuple[str, Optional[subprocess.Popen]]] = (
        [(f"account={wp.account_num}", wp.process) for wp in workers.values()] +
        [(f"strategy={sp.name}",       sp.process) for sp in strategies]
    )
    logger.info(f"Shutting down {len(all_procs)} subprocess(es) …")
    for label, proc in all_procs:
        if proc and proc.poll() is None:
            logger.info(f"  SIGTERM -> {label} pid={proc.pid}")
            proc.terminate()

    deadline = time.monotonic() + timeout
    for label, proc in all_procs:
        if proc and proc.poll() is None:
            remaining = max(0, deadline - time.monotonic())
            try:
                proc.wait(timeout=remaining)
            except subprocess.TimeoutExpired:
                logger.warning(f"  SIGKILL -> {label} pid={proc.pid} (did not exit within {timeout}s)")
                proc.kill()

    logger.info("All subprocesses stopped.")


# ---------------------------------------------------------------------------
# Process table
# ---------------------------------------------------------------------------

def _log_process_table(workers: Dict[str, WorkerProcess], strategies: List[StrategyProcess]) -> None:
    now = datetime.now(WAT).strftime("%Y-%m-%d %H:%M:%S WAT")
    lines = [f"\n{'-' * 60}", f"  Process Table  -  {now}", f"{'-' * 60}"]

    lines.append("  [WORKERS]")
    for wp in workers.values():
        pid    = wp.process.pid if wp.process else "-"
        status = "DISABLED" if wp.disabled else (
            "RUNNING" if wp.process and wp.process.poll() is None else "DEAD"
        )
        lines.append(f"    {wp.account_num:<20} pid={str(pid):<8} restarts={wp.restart_count:<4} status={status}")

    lines.append("  [STRATEGIES]")
    for sp in strategies:
        pid = sp.process.pid if sp.process else "-"
        if sp.disabled:
            status = "DISABLED"
        elif not sp.spawned:
            status = f"WAITING (scheduled {sp.scheduled_time.strftime('%H:%M')} WAT)"
        elif sp.process and sp.process.poll() is None:
            status = "RUNNING"
        else:
            status = "DEAD"
        lines.append(f"    {sp.name:<20} pid={str(pid):<8} restarts={sp.restart_count:<4} status={status}")

    lines.append(f"{'-' * 60}")
    logger.info("\n".join(lines))


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def run(channel: str, restart_limit: int) -> None:
    logger.info("Orchestrator starting …")

    # --- Load accounts ---
    accounts = _load_runnable_accounts()
    if not accounts:
        logger.error("No runnable accounts found in broker_accounts — exiting")
        sys.exit(1)

    logger.info(f"Found {len(accounts)} runnable account(s)")

    # --- Determine which strategy runners to launch ---
    active_markets = _union_enabled_markets(accounts)
    logger.info(f"Union of enabled_markets across all accounts: {sorted(active_markets)}")

    strategies: List[StrategyProcess] = []
    for market, cfg in MARKET_RUNNER_CATALOGUE.items():
        if market not in active_markets:
            logger.info(f"[STRATEGY SKIP] market={market} — not in any account's enabled_markets")
            continue
        sp = StrategyProcess(
            name           = market,
            module         = cfg["module"],
            scheduled_time = dtime(cfg["hour"], cfg["minute"]),
        )
        strategies.append(sp)
        logger.info(
            f"[STRATEGY QUEUED] market={market} module={cfg['module']} "
            f"scheduled={sp.scheduled_time.strftime('%H:%M')} WAT"
        )

    # Warn about enabled markets that have no runner yet
    for market in sorted(active_markets):
        if market not in MARKET_RUNNER_CATALOGUE:
            logger.info(f"[STRATEGY SKIP] market={market} — no runner module in catalogue yet")

    # --- Build worker registry ---
    workers: Dict[str, WorkerProcess] = {}
    force_spawn_flags: Dict[str, bool] = {}
    for acct in accounts:
        wp = WorkerProcess(
            account_id  = acct["id"],
            account_num = str(acct.get("account_number", acct["id"][:8])),
            channel     = channel,
        )
        workers[acct["id"]] = wp
        force_spawn_flags[acct["id"]] = bool(acct.get("force_spawn"))

    # --- Spawn workers immediately ---
    for account_id, wp in workers.items():
        _spawn_worker(wp)
        if force_spawn_flags.get(account_id):
            _clear_force_spawn_flag(account_id)

    _log_process_table(workers, strategies)

    # Log countdown for each pending strategy
    now_wat = datetime.now(WAT)
    for sp in strategies:
        sched_today = now_wat.replace(
            hour=sp.scheduled_time.hour, minute=sp.scheduled_time.minute,
            second=0, microsecond=0,
        )
        if now_wat < sched_today:
            wait_min = (sched_today - now_wat).total_seconds() / 60
            logger.info(
                f"[STRATEGY COUNTDOWN] market={sp.name} "
                f"starts at {sp.scheduled_time.strftime('%H:%M')} WAT (in {wait_min:.1f} min)"
            )
        else:
            logger.info(
                f"[STRATEGY COUNTDOWN] market={sp.name} "
                f"scheduled time {sp.scheduled_time.strftime('%H:%M')} WAT already passed — "
                f"will spawn immediately on first poll"
            )

    # --- Signal handling ---
    shutdown_requested = False

    def _handle_signal(signum, frame):
        nonlocal shutdown_requested
        logger.info(f"Signal {signum} received — initiating shutdown")
        shutdown_requested = True

    signal.signal(signal.SIGINT,  _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    # --- Monitor loop ---
    heartbeat_check_counter = 0

    while not shutdown_requested:
        time.sleep(POLL_INTERVAL)
        restarted = False
        now_time  = datetime.now(WAT).time()

        # --- Spawn strategy runners when their scheduled time arrives ---
        for sp in strategies:
            if sp.spawned or sp.disabled:
                continue
            if now_time >= sp.scheduled_time:
                logger.info(
                    f"[STRATEGY TIME] market={sp.name} "
                    f"scheduled time {sp.scheduled_time.strftime('%H:%M')} WAT reached — spawning"
                )
                _spawn_strategy(sp)
                restarted = True

        # --- Monitor workers ---
        for wp in workers.values():
            if wp.disabled:
                continue
            process = wp.process
            exit_code = process.poll() if process else -1
            if exit_code is not None:
                pid = process.pid if process else "-"
                logger.warning(f"[DEAD] account={wp.account_num} pid={pid} exit_code={exit_code}")
                if exit_code in NON_RETRYABLE_EXIT_CODES:
                    wp.disabled = True
                    logger.error(f"[DISABLED] account={wp.account_num} non-retryable exit code={exit_code} — restart skipped")
                    _mark_account_error(wp.account_id, f"Worker disabled due non-retryable startup failure (exit {exit_code})")
                else:
                    _restart_worker(wp, restart_limit)
                restarted = True

        # --- Monitor strategy runners ---
        for sp in strategies:
            if not sp.spawned or sp.disabled:
                continue
            process = sp.process
            exit_code = process.poll() if process else -1
            if exit_code is not None:
                pid = process.pid if process else "-"
                logger.warning(f"[STRATEGY DEAD] market={sp.name} pid={pid} exit_code={exit_code}")
                _restart_strategy(sp, restart_limit)
                restarted = True

        if restarted:
            _log_process_table(workers, strategies)

        # Stale heartbeat check every ~60 s
        heartbeat_check_counter += 1
        if heartbeat_check_counter >= (60 // POLL_INTERVAL):
            _check_stale_heartbeats(workers)
            heartbeat_check_counter = 0

    # --- Clean shutdown ---
    _shutdown_all(workers, strategies)
    logger.info("Orchestrator exited cleanly.")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Glass Box orchestrator — manages all worker and strategy processes"
    )
    parser.add_argument("--channel", default="signals",
                        help="Redis pub/sub channel workers subscribe to (default: signals)")
    parser.add_argument("--restart-limit", type=int, default=DEFAULT_RESTART_LIMIT,
                        help="Max restarts per subprocess before disabling (0 = unlimited, default: 10)")
    args = parser.parse_args()
    run(channel=args.channel, restart_limit=args.restart_limit)


if __name__ == "__main__":
    main()
