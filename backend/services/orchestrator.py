# /home/runner/work/trade-bot/trade-bot/backend/runners/orchestrator.py
"""
orchestrator.py — Glass Box Trading Engine

Spawns and manages one worker.py subprocess per broker account.
Responsibilities:
  1. Query broker_accounts for all accounts in a runnable state
  2. Spawn one `worker.py --account-id <uuid>` subprocess per account
  3. Monitor all subprocesses — restart crashed workers with backoff
  4. Propagate clean shutdown (SIGINT / SIGTERM) to all workers
  5. Log a process table on startup and after every restart

This process is the single entry point for running the full engine.
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
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, Optional

from backend.config.logger import setup_logger
from backend.config.supaclient import supabase

logger = setup_logger("orchestrator")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

WORKER_MODULE        = "backend.services.worker"   # run as `python -m <module>`
RUNNABLE_STATUSES    = {"provisioned", "authenticated", "ready"}
POLL_INTERVAL        = 5      # seconds between process health checks
BACKOFF_BASE         = 5      # initial restart delay in seconds
BACKOFF_MAX          = 300    # cap restart delay at 5 minutes
DEFAULT_RESTART_LIMIT = 10    # max restarts per worker before giving up (0 = unlimited)
STALE_HEARTBEAT_SEC  = 90     # seconds before a worker heartbeat is considered stale
STALE_KILL_SEC       = 300
NON_RETRYABLE_EXIT_CODES = {78}  # Worker startup/config errors (EX_CONFIG)

WAT = timezone(timedelta(hours=1), name="WAT")


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class WorkerProcess:
    """
    Tracks a single worker subprocess and its restart history.

    account_id   — broker_accounts.id (UUID)
    account_num  — human-readable MT5 login number for log clarity
    process      — the live subprocess.Popen handle (None before first spawn)
    restart_count — how many times this worker has been restarted
    backoff      — current restart delay in seconds (doubles on each crash)
    last_restart — WAT timestamp of the most recent spawn
    disabled     — True once restart_limit is hit; worker will not be respawned
    """
    account_id:    str
    account_num:   str
    channel:       str
    process:       Optional[subprocess.Popen] = field(default=None, repr=False)
    restart_count: int = 0
    backoff:       float = BACKOFF_BASE
    last_restart:  Optional[datetime] = None
    disabled:      bool = False


# ---------------------------------------------------------------------------
# Supabase helpers
# ---------------------------------------------------------------------------

def _load_runnable_accounts() -> list[dict]:
    """
    Fetch all broker_accounts rows in a runnable state OR manually forced to spawn.
    Returns a list of dicts — each dict is one account row.
    """
    res = (
        supabase.table("broker_accounts")
        .select("id, account_number, status, force_spawn")
        .or_("status.in.(provisioned,authenticated,ready),force_spawn.eq.true")
        .execute()
    )
    return res.data or []


def _clear_force_spawn_flag(account_id: str) -> None:
    """Clear manual spawn override flag after account worker is started."""
    try:
        supabase.table("broker_accounts").update(
            {"force_spawn": False}
        ).eq("id", account_id).execute()
    except Exception as e:
        logger.warning(f"Failed to clear force_spawn for account {account_id}: {e}")


def _mark_account_error(account_id: str, detail: str) -> None:
    """
    Flip an account to status=error when its worker hits the restart limit.
    The orchestrator will not attempt to spawn it again this session.
    """
    try:
        # Preserve existing cause detail from worker.py and append orchestrator state.
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
            {
                "status":        "error",
                "status_detail": final_detail[:500],
            }
        ).eq("id", account_id).execute()
    except Exception as e:
        logger.error(f"Failed to mark account {account_id} as error: {e}")


def _check_stale_heartbeats(workers: Dict[str, WorkerProcess]) -> None:
    """
    Cross-check broker_accounts.last_heartbeat against STALE_HEARTBEAT_SEC.
    A worker whose process is alive but whose heartbeat is stale has likely
    hung inside a blocking call. Log a warning — the orchestrator will detect
    the eventual process exit and restart it.
    """
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
                acct = workers.get(row["id"])
                label = acct.account_num if acct else row["id"]

                if age > STALE_KILL_SEC and acct and acct.process and acct.process.poll() is None:
                    logger.warning(
                        f"[STALE HEARTBEAT] account={label} last_heartbeat={age:.0f}s ago - "
                        f"killing hung worker"
                    )
                    acct.process.kill()
                    # Do not restart here — the monitor loop detects the exit
                    # on the next POLL_INTERVAL tick and calls _restart() with backoff.
                else:
                    logger.warning(
                        f"[STALE HEARTBEAT] account={label} last_heartbeat={age:.0f}s ago - "
                        f"worker may be hung"
                    )
    except Exception as e:
        logger.warning(f"Heartbeat check failed: {e}")


# ---------------------------------------------------------------------------
# Worker lifecycle
# ---------------------------------------------------------------------------

def _spawn(wp: WorkerProcess) -> None:
    """
    Launch a new worker subprocess for this account.
    Uses `python -m backend.services.worker` so the module path resolves
    correctly regardless of where the orchestrator is invoked from.
    """
    cmd = [
        sys.executable, "-m", WORKER_MODULE,
        "--account-id", wp.account_id,
        "--channel",    wp.channel,
    ]
    wp.process      = subprocess.Popen(cmd)
    wp.last_restart = datetime.now(WAT)
    logger.info(
        f"[SPAWN] account={wp.account_num} pid={wp.process.pid} "
        f"restarts={wp.restart_count}"
    )


def _restart(wp: WorkerProcess, restart_limit: int) -> None:
    """
    Apply backoff delay then respawn.
    If restart_limit is reached, mark the worker disabled and flip the
    account to status=error in Supabase so the dashboard surfaces it.
    """
    if restart_limit > 0 and wp.restart_count >= restart_limit:
        logger.error(
            f"[DISABLED] account={wp.account_num} hit restart limit "
            f"({restart_limit}) - giving up"
        )
        wp.disabled = True
        _mark_account_error(
            wp.account_id,
            f"Worker disabled after {restart_limit} restarts",
        )
        return

    logger.warning(
        f"[RESTART] account={wp.account_num} backoff={wp.backoff:.0f}s "
        f"restart #{wp.restart_count + 1}"
    )
    time.sleep(wp.backoff)

    wp.restart_count += 1
    wp.backoff        = min(wp.backoff * 2, BACKOFF_MAX)
    _spawn(wp)


def _shutdown_all(workers: Dict[str, WorkerProcess], timeout: int = 10) -> None:
    """
    Send SIGTERM to all live worker processes and wait for them to exit.
    Any process that doesn't exit within `timeout` seconds is killed.
    """
    logger.info(f"Shutting down {len(workers)} worker(s) …")

    for wp in workers.values():
        if wp.process and wp.process.poll() is None:
            logger.info(f"  SIGTERM -> account={wp.account_num} pid={wp.process.pid}")
            wp.process.terminate()

    deadline = time.monotonic() + timeout
    for wp in workers.values():
        if wp.process and wp.process.poll() is None:
            remaining = max(0, deadline - time.monotonic())
            try:
                wp.process.wait(timeout=remaining)
            except subprocess.TimeoutExpired:
                logger.warning(
                    f"  SIGKILL -> account={wp.account_num} pid={wp.process.pid} "
                    f"(did not exit within {timeout}s)"
                )
                wp.process.kill()

    logger.info("All workers stopped.")


# ---------------------------------------------------------------------------
# Process table
# ---------------------------------------------------------------------------

def _log_process_table(workers: Dict[str, WorkerProcess]) -> None:
    """
    Emit a human-readable summary of all managed workers.
    Printed at startup and after every restart event.
    """
    now = datetime.now(WAT).strftime("%Y-%m-%d %H:%M:%S WAT")
    lines = [f"\n{'-' * 60}", f"  Worker Process Table  -  {now}", f"{'-' * 60}"]
    for wp in workers.values():
        pid    = wp.process.pid if wp.process else "-"
        status = "DISABLED" if wp.disabled else (
            "RUNNING" if wp.process and wp.process.poll() is None else "DEAD"
        )
        lines.append(
            f"  {wp.account_num:<20} pid={str(pid):<8} "
            f"restarts={wp.restart_count:<4} status={status}"
        )
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
        logger.error("No runnable accounts found in broker_accounts - exiting")
        sys.exit(1)

    logger.info(f"Found {len(accounts)} runnable account(s)")

    # --- Build worker registry ---
    workers: Dict[str, WorkerProcess] = {}
    force_spawn_by_account_id: Dict[str, bool] = {}
    for acct in accounts:
        wp = WorkerProcess(
            account_id  = acct["id"],
            account_num = str(acct.get("account_number", acct["id"][:8])),
            channel     = channel,
        )
        workers[acct["id"]] = wp
        force_spawn_by_account_id[acct["id"]] = bool(acct.get("force_spawn"))

    # --- Initial spawn ---
    for account_id, wp in workers.items():
        _spawn(wp)
        if force_spawn_by_account_id.get(account_id):
            _clear_force_spawn_flag(account_id)

    _log_process_table(workers)

    # --- Signal handling - clean shutdown on SIGINT / SIGTERM ---
    shutdown_requested = False

    def _handle_signal(signum, frame):
        nonlocal shutdown_requested
        logger.info(f"Signal {signum} received - initiating shutdown")
        shutdown_requested = True

    signal.signal(signal.SIGINT,  _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    # --- Monitor loop ---
    heartbeat_check_counter = 0

    while not shutdown_requested:
        time.sleep(POLL_INTERVAL)

        restarted = False

        for wp in workers.values():
            if wp.disabled:
                continue

            exit_code = wp.process.poll() if wp.process else -1

            if exit_code is not None:
                # Process has exited
                logger.warning(
                    f"[DEAD] account={wp.account_num} pid={wp.process.pid} "
                    f"exit_code={exit_code}"
                )

                if exit_code in NON_RETRYABLE_EXIT_CODES:
                    wp.disabled = True
                    logger.error(
                        f"[DISABLED] account={wp.account_num} non-retryable exit "
                        f"code={exit_code} - restart skipped"
                    )
                    _mark_account_error(
                        wp.account_id,
                        f"Worker disabled due non-retryable startup failure (exit {exit_code})",
                    )
                    restarted = True
                    continue

                _restart(wp, restart_limit)
                restarted = True

        if restarted:
            _log_process_table(workers)

        # Check stale heartbeats every ~60s (60 / POLL_INTERVAL ticks)
        heartbeat_check_counter += 1
        if heartbeat_check_counter >= (60 // POLL_INTERVAL):
            _check_stale_heartbeats(workers)
            heartbeat_check_counter = 0

    # --- Clean shutdown ---
    _shutdown_all(workers)
    logger.info("Orchestrator exited cleanly.")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Glass Box orchestrator — manages all worker processes")
    parser.add_argument(
        "--channel",
        default="signals",
        help="Redis pub/sub channel workers subscribe to (default: signals)",
    )
    parser.add_argument(
        "--restart-limit",
        type=int,
        default=DEFAULT_RESTART_LIMIT,
        help="Max restarts per worker before disabling (0 = unlimited, default: 10)",
    )
    args = parser.parse_args()

    run(channel=args.channel, restart_limit=args.restart_limit)


if __name__ == "__main__":
    main()
