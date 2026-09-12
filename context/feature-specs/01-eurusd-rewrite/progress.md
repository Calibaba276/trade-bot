# EURUSD Rewrite — Implementation Steps

## Current state

- [x] The live Supabase `audit_log` table is ready: required columns, constraints, indexes, RLS, and account-owner read policy were verified on 2026-09-09.
- [x] Steps 2–3 of `backend/strategies/eurusd_model.py` are completed and verified on 2026-09-12; Step 4 remains pending.
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

Status: complete (2026-09-12).

Changed files: `backend/strategies/eurusd_model.py`, `tests/test_eurusd_model.py`.

Added typed immutable evidence records and pure closed-candle functions for structure bias with contextual DXY/GBPUSD evidence, NY midnight and Asian ranges, ordered liquidity targets, wick-back-only sweeps, ATR/body-to-wick MSS confirmation with M5-first refinement, and FVG/order-block extraction. MSS evaluates only the newest closed candle using pre-candle ATR; M3/M1 requires explicit M5 confirmation; and midnight ranges reject incomplete or gapped candle coverage. Chronological input validation prevents future-candle use; no broker, database, or execution imports were added.

Verification: `$env:PYTHONPATH='.'; python -m pytest -q tests/test_eurusd_model.py` passed (15 tests); `python -m compileall -q backend/strategies/eurusd_model.py` and `git diff --check` passed. `ruff` was not available in the environment and was not run.

Continue in `backend/strategies/eurusd_model.py`. Add deterministic functions that use only supplied closed candles:

1. Determine Daily/H4/H1 bias from confirmed swing structure, record DXY inverse-correlation and GBP/USD SMT evidence when available, and return no bias only for conflicting/choppy EURUSD structure; DXY/SMT are contextual unless a clear DXY structural conflict trips session safety.
2. Build and freeze the NY midnight-to-03:00 range; separately mark the Asian range (19:00–00:00 NY); calculate premium, discount, and midpoint.
3. Select draw-on-liquidity in order: PDH/PDL and Asian range, previous session, M15 equal highs/lows, then the opposite range side.
4. Detect a sweep only when price wicks through a level and closes back inside it. A close through the level is a breakout, never a sweep.
5. Confirm MSS primarily on a closed M5 candle body through the counter-trend swing in the bias direction with 1.5 ATR plus 70% body-to-wick displacement thresholds; permit M3/M1 only as optional refinement after M5/context confirmation.
6. Extract FVG and the last opposing-candle order block from the MSS impulse; select the FVG boundary/CE entry, 2–3 pip protective offset, and a documented opposing-liquidity/ADR/scalp target.

Verify every rule with fixtures, including future-candle sentinels that prove no lookahead is possible.

### 3. Complete the `EURUSDModel` state machine

Status: complete (2026-09-12).

Changed files: `backend/strategies/eurusd_model.py`, `tests/test_eurusd_model.py`.

Added the pure `EURUSDModel` closed-candle state machine. It rejects duplicate and stale bars before state changes; fails closed when the selected M5, M3, or M1 interval is skipped; resets at the New York trading-date boundary; preserves confirmed bias/range context after an invalidated same-session sweep; enforces bullish-discount and bearish-premium sweep context; tags London/NY-AM killzones through the DST-aware NY-to-UTC helper; retains only the candle immediately before MSS, the MSS displacement candle, and the last opposing candle needed for order-block extraction; confirms the FVG with the following closed candle; requires the same retracement candle to touch the FVG CE or OB boundary and close with bias; falls back to the order-block boundary only when no FVG exists; validates directional stop/entry/target ordering; tracks a model-local bar sequence and the MSS displacement-leg swing as the 3-pip stop anchor, rejecting stops over 20 pips; and emits only one immutable `Setup` per trigger. M5 remains the primary MSS timeframe; M3/M1 continuity is supported only as optional refinement and still requires explicit prior M5/context confirmation.

Verification: `$env:PYTHONPATH='.'; python -m pytest -q tests/test_eurusd_model.py` passed (25 tests), including M3/M1 interval-continuity coverage; `python -m ruff check backend/strategies/eurusd_model.py tests/test_eurusd_model.py`, `python -m compileall -q backend/strategies/eurusd_model.py`, and `git diff --check` passed. Pyright could not run in the sandbox because Node was denied access to the user-profile parent directory.

Still in `backend/strategies/eurusd_model.py`, add the complete strategy flow:

`AWAITING_BIAS → AWAITING_RANGE → AWAITING_SWEEP → SWEPT_AWAITING_MSS → MSS_CONFIRMED_AWAITING_FVG → AWAITING_RETRACEMENT → SETUP_READY`

Implement these rules:

- Reset at NY-local midnight and after an unconfirmed-sweep invalidation.
- Consider longs only in discount and shorts only in premium.
- Tag London/NY-AM killzone alignment for later filtering; do not apply selectivity here.
- Use one deterministic entry trigger: FVG consequent-encroachment touch followed by a candle close in the bias direction. Use the OB boundary only if no FVG exists.
- Emit exactly one complete immutable `Setup` for a valid trigger.

Verify every state transition, resets, invalidations, duplicate-bar prevention, FVG-only/OB-only/both variants, and no-lookahead behavior.
- Also verify contextual DXY/GBP/USD SMT evidence, clear DXY-conflict invalidation, Asian-range and PDH/PDL sweeps, 07:00–10:00 NY killzone tagging with 08:30–10:00 NY preferred timing (not an exclusive gate), optional M3/M1 refinement, separate no-trade safety gates, and the 15–20 pip maximum stop rule.

### 4. Create `setup_filter.py`

Only after the EURUSD model is complete, create `backend/strategies/setup_filter.py`.

Add Pydantic filter models, the five configured checks, `evaluate()`, and `log_filter_result()` for the existing `audit_log` table. The filter receives only `Setup`, never raw candle data.

Start with cooldown, confluence, and R:R as hard gates. Keep bias quality and AMD timing as soft scores. Apply the separate session-safety gates before setup-quality scoring, and verify every pass/fail case plus the audit insert payload.

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
- NY AM killzone: 07:00–10:00 New York time; preferred entry sub-window 08:30–10:00 NY, not an exclusive gate.
- Maximum trades per day: 2.
- Minimum minutes between setups: 60.
- Maximum setups per killzone: 1.
- Minimum confluence categories: 2 of 3.
- Minimum MSS displacement: 1.5 ATR.
- Minimum R:R: 3.0.
- Displacement: body >= 1.5 ATR14 and body-to-wick ratio >= 70%.
- Stop offset: 2–3 pips beyond the displacement swing; reject above 20 pips.
- Target priority: opposing Asian/London liquidity, then 80% ADR, then 20–30 pip scalp fallback.
- DXY/SMT: contextual evidence; do not require confirmation for every EURUSD setup. Clear DXY structural conflict remains a separate safety invalidation.
- Execution refinement: M5 primary; M3/M1 optional only after the setup is already confirmed.
- Session safety: bank holidays, NFP Friday, FOMC decision afternoon, absent DOL, and exhausted ADR fail closed and are audit logged.

Do not tune these values or alter hard/soft filter status during this implementation.

## Next step

Implement Step 4, `setup_filter.py`, while retaining the existing `audit_log` requirements.
