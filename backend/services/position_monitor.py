"""
position_monitor.py
-------------------
Runs as a background thread inside each worker process.

Responsibilities:
  1. Breakeven management — polls open MT5 positions and moves SL to
     entry + buffer once unrealised PnL reaches rr_ratio × initial risk.
  2. Daily drawdown halt — compares current balance against the day-start
     snapshot and sets a shared halt flag when the loss limit is breached.
     The flag blocks new signal processing in worker.py for the rest of
     the calendar day (UTC).  Existing trades are left to run.

MT5-native: no Lumibot dependency.  All broker calls go through
MetaTrader5 directly so this module works inside worker subprocesses.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

import MetaTrader5 as mt5

from ..config.logger import setup_logger

logger = setup_logger(__name__)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass
class MonitorConfig:
    """Per-account monitor configuration loaded from broker_accounts row."""

    account_id: str                     # broker_accounts.id (UUID)
    account_number: int
    symbol: str

    # Risk / sizing
    rr_ratio: float = 3.0               # breakeven trigger: pnl >= sl_distance * rr_ratio
    breakeven_buffer_ticks: int = 10    # ticks beyond entry for the new SL
    max_daily_drawdown_pct: float = 0.02  # 2 % of day-start balance

    # Timing
    poll_interval_seconds: float = 5.0  # how often to check positions


# ---------------------------------------------------------------------------
# Shared halt flag — one instance lives inside each worker
# ---------------------------------------------------------------------------

class HaltFlag:
    """
    Thread-safe boolean flag.

    worker.py holds a reference and checks .is_halted() before processing
    any Redis signal.  position_monitor.py calls .halt() when drawdown
    limit is breached.  The flag resets automatically at the next UTC day.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._halted = False
        self._halt_date: Optional[str] = None   # 'YYYY-MM-DD' UTC

    def halt(self) -> None:
        with self._lock:
            self._halted = True
            self._halt_date = _today_utc()

    def is_halted(self) -> bool:
        with self._lock:
            if not self._halted:
                return False
            # Auto-reset at the next calendar day
            if _today_utc() != self._halt_date:
                self._halted = False
                self._halt_date = None
                return False
            return True

    def reset(self) -> None:
        """Manual reset — useful in tests or when operator overrides."""
        with self._lock:
            self._halted = False
            self._halt_date = None


# ---------------------------------------------------------------------------
# Internal position tracking
# ---------------------------------------------------------------------------

@dataclass
class TrackedPosition:
    """Snapshot of a position taken at fill time."""

    ticket: int
    symbol: str
    side: str                   # 'long' | 'short'
    entry_price: float
    sl_distance: float          # abs(entry - original_sl) in price units
    breakeven_moved: bool = False


# ---------------------------------------------------------------------------
# Day-start balance snapshot
# ---------------------------------------------------------------------------

class DailyEquityTracker:
    """
    Tracks the balance at the start of each UTC trading day.

    On first call (or after a day rollover) it snapshots the current MT5
    account balance.  Subsequent calls within the same day compare against
    that snapshot.
    """

    def __init__(self, max_drawdown_pct: float) -> None:
        self._max_drawdown_pct = max_drawdown_pct
        self._day_start_balance: Optional[float] = None
        self._snapshot_date: Optional[str] = None
        self._lock = threading.Lock()

    def is_limit_breached(self) -> tuple[bool, float, float]:
        """
        Returns (breached, current_balance, day_start_balance).
        Snapshots balance on first call of the day.
        """
        with self._lock:
            today = _today_utc()

            info = mt5.account_info()
            if info is None:
                logger.warning("DailyEquityTracker: mt5.account_info() returned None")
                return False, 0.0, 0.0

            current_balance = info.balance

            # New day — refresh snapshot
            if self._snapshot_date != today:
                self._day_start_balance = current_balance
                self._snapshot_date = today
                logger.info(
                    f"DailyEquityTracker: new day snapshot — "
                    f"balance={current_balance:.2f}"
                )
                return False, current_balance, current_balance

            loss = self._day_start_balance - current_balance
            loss_pct = loss / self._day_start_balance if self._day_start_balance else 0.0
            breached = loss_pct >= self._max_drawdown_pct

            return breached, current_balance, self._day_start_balance

    def force_snapshot(self, balance: float) -> None:
        """Called by worker at startup to seed today's snapshot from a known value."""
        with self._lock:
            self._day_start_balance = balance
            self._snapshot_date = _today_utc()


# ---------------------------------------------------------------------------
# Position monitor — main class
# ---------------------------------------------------------------------------

class PositionMonitor(threading.Thread):
    """
    Background thread.  One instance per worker process.

    Usage (inside worker.py):
        halt_flag = HaltFlag()
        monitor   = PositionMonitor(config, halt_flag, supabase_client)
        monitor.daemon = True
        monitor.start()

        # Register a position after fill is confirmed:
        monitor.track(TrackedPosition(...))

        # Before processing a Redis signal:
        if halt_flag.is_halted():
            <discard signal>
    """

    def __init__(
        self,
        config: MonitorConfig,
        halt_flag: HaltFlag,
        supabase,                           # supabase-py client
    ) -> None:
        super().__init__(name=f"monitor-{config.account_number}", daemon=True)
        self.config = config
        self.halt_flag = halt_flag
        self.supabase = supabase

        self._equity_tracker = DailyEquityTracker(config.max_daily_drawdown_pct)
        self._positions: dict[int, TrackedPosition] = {}   # ticket → TrackedPosition
        self._positions_lock = threading.Lock()
        self._stop_event = threading.Event()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def track(self, position: TrackedPosition) -> None:
        """Register a newly filled position for monitoring."""
        with self._positions_lock:
            self._positions[position.ticket] = position
        logger.info(
            f"[MONITOR] Tracking ticket={position.ticket} "
            f"{position.side} entry={position.entry_price:.5f} "
            f"sl_distance={position.sl_distance:.5f}"
        )

    def untrack(self, ticket: int) -> None:
        """Remove a closed/expired position."""
        with self._positions_lock:
            self._positions.pop(ticket, None)

    def seed_day_start_balance(self, balance: float) -> None:
        self._equity_tracker.force_snapshot(balance)

    def stop(self) -> None:
        self._stop_event.set()

    # ------------------------------------------------------------------
    # Thread loop
    # ------------------------------------------------------------------

    def run(self) -> None:
        logger.info(f"[MONITOR] Started for account {self.config.account_number}")
        while not self._stop_event.is_set():
            try:
                self._check_drawdown()
                self._check_breakeven()
                self._prune_closed_positions()
            except Exception as exc:
                logger.exception(f"[MONITOR] Unhandled error in monitor loop: {exc}")
            time.sleep(self.config.poll_interval_seconds)
        logger.info(f"[MONITOR] Stopped for account {self.config.account_number}")

    # ------------------------------------------------------------------
    # Drawdown check
    # ------------------------------------------------------------------

    def _check_drawdown(self) -> None:
        if self.halt_flag.is_halted():
            return  # already halted, nothing to do

        breached, current, day_start = self._equity_tracker.is_limit_breached()
        if not breached:
            return

        loss_pct = (day_start - current) / day_start * 100
        logger.warning(
            f"[DRAWDOWN HALT] account={self.config.account_number} "
            f"day_start={day_start:.2f} current={current:.2f} "
            f"loss={loss_pct:.2f}% >= limit={self.config.max_daily_drawdown_pct * 100:.1f}%"
        )

        self.halt_flag.halt()
        self._write_drawdown_halt_event(current, day_start, loss_pct)
        self._flip_account_status("halted", f"Daily drawdown {loss_pct:.2f}% exceeded limit")

    def _write_drawdown_halt_event(
        self, current: float, day_start: float, loss_pct: float
    ) -> None:
        try:
            self.supabase.table("execution_events").insert({
                "account_id": self.config.account_id,
                "signal_id": None,
                "execution_id": None,
                "event_type": "drawdown_halt",
                "detail": {
                    "day_start_balance": day_start,
                    "current_balance": current,
                    "loss_pct": round(loss_pct, 4),
                    "limit_pct": self.config.max_daily_drawdown_pct * 100,
                },
                "occurred_at": _now_iso(),
            }).execute()
        except Exception as exc:
            logger.error(f"[MONITOR] Failed to write drawdown_halt event: {exc}")

    def _flip_account_status(self, status: str, detail: str) -> None:
        try:
            self.supabase.table("broker_accounts").update({
                "status": status,
                "status_detail": detail,
                "updated_at": _now_iso(),
            }).eq("id", self.config.account_id).execute()
        except Exception as exc:
            logger.error(f"[MONITOR] Failed to update broker_accounts status: {exc}")

    # ------------------------------------------------------------------
    # Breakeven check
    # ------------------------------------------------------------------

    def _check_breakeven(self) -> None:
        with self._positions_lock:
            tickets = [t for t, p in self._positions.items() if not p.breakeven_moved]

        if not tickets:
            return

        symbol_info = mt5.symbol_info(self.config.symbol)
        if symbol_info is None:
            logger.warning(f"[MONITOR] symbol_info returned None for {self.config.symbol}")
            return

        tick_size = symbol_info.point
        buffer = tick_size * self.config.breakeven_buffer_ticks

        for ticket in tickets:
            with self._positions_lock:
                pos = self._positions.get(ticket)
            if pos is None:
                continue

            self._evaluate_breakeven(pos, buffer)

    def _evaluate_breakeven(self, pos: TrackedPosition, buffer: float) -> None:
        # Fetch live MT5 position to get current unrealised PnL in price terms
        mt5_positions = mt5.positions_get(ticket=pos.ticket)
        if not mt5_positions:
            return  # position closed already — will be pruned next cycle

        mt5_pos = mt5_positions[0]

        # Current price (bid for longs, ask for shorts — conservative)
        tick = mt5.symbol_info_tick(pos.symbol)
        if tick is None:
            return

        if pos.side == "long":
            current_price = tick.bid
            pnl_in_price = current_price - pos.entry_price
            trigger = pos.sl_distance * self.config.rr_ratio
            if pnl_in_price < trigger:
                return
            new_sl = pos.entry_price + buffer

        else:  # short
            current_price = tick.ask
            pnl_in_price = pos.entry_price - current_price
            trigger = pos.sl_distance * self.config.rr_ratio
            if pnl_in_price < trigger:
                return
            new_sl = pos.entry_price - buffer

        # Only move SL if it's actually an improvement
        if pos.side == "long" and new_sl <= mt5_pos.sl:
            return
        if pos.side == "short" and new_sl >= mt5_pos.sl:
            return

        self._send_sl_modify(pos, mt5_pos, new_sl)

    def _send_sl_modify(
        self, pos: TrackedPosition, mt5_pos, new_sl: float
    ) -> None:
        request = {
            "action":   mt5.TRADE_ACTION_SLTP,
            "position": pos.ticket,
            "symbol":   pos.symbol,
            "sl":       new_sl,
            "tp":       mt5_pos.tp,           # preserve existing TP
        }

        result = mt5.order_send(request)

        if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
            retcode = result.retcode if result else "None"
            logger.error(
                f"[BREAKEVEN] Failed to modify SL ticket={pos.ticket} "
                f"retcode={retcode}"
            )
            return

        old_sl = mt5_pos.sl
        logger.info(
            f"[BREAKEVEN] ticket={pos.ticket} {pos.side} {pos.symbol} "
            f"SL {old_sl:.5f} → {new_sl:.5f} (entry={pos.entry_price:.5f})"
        )

        # Mark as done — one-shot
        with self._positions_lock:
            if pos.ticket in self._positions:
                self._positions[pos.ticket].breakeven_moved = True

        self._write_breakeven_event(pos, old_sl, new_sl)

    def _write_breakeven_event(
        self, pos: TrackedPosition, old_sl: float, new_sl: float
    ) -> None:
        try:
            self.supabase.table("execution_events").insert({
                "account_id": self.config.account_id,
                "signal_id": None,
                "execution_id": None,
                "event_type": "breakeven_moved",
                "detail": {
                    "ticket":      pos.ticket,
                    "symbol":      pos.symbol,
                    "side":        pos.side,
                    "entry_price": pos.entry_price,
                    "old_sl":      old_sl,
                    "new_sl":      new_sl,
                    "rr_at_trigger": self.config.rr_ratio,
                },
                "occurred_at": _now_iso(),
            }).execute()
        except Exception as exc:
            logger.error(f"[MONITOR] Failed to write breakeven_moved event: {exc}")

    # ------------------------------------------------------------------
    # Prune closed positions
    # ------------------------------------------------------------------

    def _prune_closed_positions(self) -> None:
        with self._positions_lock:
            tickets = list(self._positions.keys())

        for ticket in tickets:
            if not mt5.positions_get(ticket=ticket):
                with self._positions_lock:
                    self._positions.pop(ticket, None)
                logger.info(f"[MONITOR] Pruned closed position ticket={ticket}")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _today_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()