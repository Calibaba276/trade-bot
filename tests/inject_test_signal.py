"""
Test signal injector — fires one fake EURUSD signal through the full pipeline.

Usage (from the repo root on the VM):
    python tests/inject_test_signal.py

What it does:
  1. Builds a Verdict with realistic EURUSD prices
  2. Saves it to Supabase (signals table) — same path as the live strategy
  3. Publishes to Redis (signals channel) — worker picks it up immediately
  4. Prints the signal_id so you can track it in the executions table

If the worker is running you will see:
  - execution row created (status: pending → sent → filled/rejected)
  - execution_events rows for each step
  - Telegram notifications (if configured)

MT5 will reject the order if the market is closed — that is expected and still
proves the full pipeline works (you will see status=rejected in executions).
"""

import sys
from pathlib import Path

# Allow running from repo root without installing the package
sys.path.append(str(Path(__file__).resolve().parents[1]))

from backend.services.verdict import build_verdict, save_verdict, publish_verdict

# --- Fake but realistic EURUSD prices (NY session OTE long setup) ---
SYMBOL    = "EURUSDm"
DIRECTION = "buy"
ENTRY     = 1.08500
STOP_LOSS = 1.08200   # 30 pip SL
TP        = 1.09400   # ~90 pip TP (3:1 RR)
RISK      = 25.0      # matches default risk_amount in broker_accounts
RR        = 3.0
SCENARIO  = "ny_continuation_bullish"


def main():
    print("=== Trade-bot test signal injection ===")
    print(f"  Symbol:    {SYMBOL}")
    print(f"  Direction: {DIRECTION}")
    print(f"  Entry:     {ENTRY}")
    print(f"  SL:        {STOP_LOSS}")
    print(f"  TP:        {TP}")
    print(f"  Scenario:  {SCENARIO}")
    print()

    verdict = build_verdict(
        symbol=SYMBOL,
        direction=DIRECTION,
        entry=ENTRY,
        sl=STOP_LOSS,
        tp=TP,
        risk=RISK,
        rr=RR,
        scenario=SCENARIO,
    )

    print(f"signal_id: {verdict.signal_id}")
    print("Saving to Supabase...")
    payload = save_verdict(verdict)

    print("Publishing to Redis...")
    publish_verdict(payload)

    print()
    print("Done. Check:")
    print(f"  Supabase → signals      WHERE signal_id = '{verdict.signal_id}'")
    print(f"  Supabase → executions   WHERE signal_id = '{verdict.signal_id}'")
    print(f"  Supabase → execution_events WHERE signal_id = '{verdict.signal_id}'")
    print()
    print("Worker log should show [EXECUTED] or [REJECTED] within a few seconds.")


if __name__ == "__main__":
    main()
