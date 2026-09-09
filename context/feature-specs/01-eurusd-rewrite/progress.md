# EURUSD Rewrite — Implementation Steps

## Current state

- [x] The live Supabase `audit_log` table is ready: required columns, constraints, indexes, RLS, and account-owner read policy were verified on 2026-09-09.
- [~] `backend/strategies/eurusd_model.py` is being built from scratch.
- [ ] Do not modify or use `backend/backtest/ict_backtest.py` for this work.

## Build order

Complete all of Steps 1–3 in `eurusd_model.py` before creating or editing `setup_filter.py`.

## Step completion rule

After completing and verifying one step, update this file with its status, changed files, and verification evidence. Then stop and wait for your explicit `NEXT` before beginning the following step.

### 1. Create the `eurusd_model.py` foundation — complete (2026-09-09)

Create `backend/strategies/eurusd_model.py` with:

- `SetupState` for the ICT sequence.
- Typed closed-candle and in-memory state records.
- Immutable Pydantic `Setup` model.
- UTC validation, NY-local killzone-to-UTC conversion, NY midnight-range boundaries, and WAT display helpers.

Do not import Lumibot, Supabase, Redis, MT5, Verdict, or database code yet. All strategy timestamps must be timezone-aware UTC; New York time is only for DST-aware session calculations.

Verify invalid timestamps are rejected, `Setup` is immutable, and EST/EDT plus NY midnight-to-03:00 boundaries are correct.

Changed files: `backend/strategies/eurusd_model.py`, `tests/test_eurusd_model.py`. All Step 1 records use Pydantic models; no dataclasses are used.

Verification: `pytest tests/test_eurusd_model.py` passed (8 tests): UTC validation, immutable `Setup`, EST/EDT NY killzone conversion, NY midnight-to-03:00 boundaries, and WAT display conversion.

### 2. Add all pure EURUSD ICT detection rules

Continue in `backend/strategies/eurusd_model.py`. Add deterministic functions that use only supplied closed candles:

1. Determine H4/Daily bias from confirmed swing structure; return no bias for conflicting or choppy structure.
2. Build and freeze the NY midnight-to-03:00 range; calculate premium, discount, and midpoint.
3. Select draw-on-liquidity in order: previous day, previous session, M15 equal highs/lows, then the opposite range side.
4. Detect a sweep only when price wicks through a level and closes back inside it. A close through the level is a breakout, never a sweep.
5. Confirm MSS only when a candle body closes through the counter-trend swing in the bias direction and meets the ATR displacement threshold.
6. Extract FVG and the last opposing-candle order block from the MSS impulse.

Verify every rule with fixtures, including future-candle sentinels that prove no lookahead is possible.

### 3. Complete the `EURUSDModel` state machine

Still in `backend/strategies/eurusd_model.py`, add the complete strategy flow:

`AWAITING_BIAS → AWAITING_RANGE → AWAITING_SWEEP → SWEPT_AWAITING_MSS → MSS_CONFIRMED_AWAITING_FVG → AWAITING_RETRACEMENT → SETUP_READY`

Implement these rules:

- Reset at NY-local midnight and after an unconfirmed-sweep invalidation.
- Consider longs only in discount and shorts only in premium.
- Tag London/NY-AM killzone alignment for later filtering; do not apply selectivity here.
- Use one deterministic entry trigger: FVG consequent-encroachment touch followed by a candle close in the bias direction. Use the OB boundary only if no FVG exists.
- Emit exactly one complete immutable `Setup` for a valid trigger.

Verify every state transition, resets, invalidations, duplicate-bar prevention, FVG-only/OB-only/both variants, and no-lookahead behavior.

### 4. Create `setup_filter.py`

Only after the EURUSD model is complete, create `backend/strategies/setup_filter.py`.

Add Pydantic filter models, the five configured checks, `evaluate()`, and `log_filter_result()` for the existing `audit_log` table. The filter receives only `Setup`, never raw candle data.

Start with cooldown, confluence, and R:R as hard gates. Keep bias quality and AMD timing as soft scores. Verify every pass/fail case and the audit insert payload.

### 5. Connect the completed strategy to execution

Update the minimal integration points only:

- Instantiate `EURUSDModel` from `backend/runners/eurusd.py`.
- Normalize broker candle timestamps to UTC before strategy evaluation.
- Audit every candidate with `setup_filter.evaluate()`.
- Build, save, and publish an existing Verdict only after the setup passes the filter.

Keep `worker.py`, `position_monitor.py`, Redis behavior, and existing Verdict persistence unchanged. Confirm the mapping from `Setup`/killzone values to existing Verdict scenarios before integrating.

Verify rejection, invalid configuration, audit failure, and Verdict-save failure all fail closed. A rejected setup must never create a Verdict.

## Fixed initial defaults

- London killzone: 02:00–05:00 New York time.
- NY AM killzone: 08:00–11:00 New York time.
- Maximum trades per day: 2.
- Minimum minutes between setups: 60.
- Maximum setups per killzone: 1.
- Minimum confluence categories: 2 of 3.
- Minimum MSS displacement: 1.5 ATR.
- Minimum R:R: 3.0.

Do not tune these values or alter hard/soft filter status during this implementation.

## Next step

Create the from-scratch `backend/strategies/eurusd_model.py` foundation in Step 1.
