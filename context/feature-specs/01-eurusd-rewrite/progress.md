# EURUSD Rewrite — Implementation Steps

## Current state

- [x] The live Supabase `audit_log` table is ready: required columns, constraints, indexes, RLS, and account-owner read policy were verified on 2026-09-09.
- [x] Steps 2–3 were verified on 2026-09-12; Step 4 and its review corrections
  were verified on 2026-09-15. Step 5 integration remains pending.
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

Status: complete after review corrections (2026-09-15).

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

Status: complete (2026-09-12).

Changed files: `backend/strategies/setup_filter.py`,
`backend/strategies/eurusd_model.py`, `tests/test_setup_filter.py`, and
`tests/test_eurusd_model.py`.

Added immutable Pydantic v2 filter configuration, context, check, and result
contracts; fail-closed bank-holiday, NFP, FOMC, absent-DOL, exhausted-ADR,
DXY-conflict, and chronology safety gates; accepted-setup selectivity; honest
three-category confluence; directional minimum 3.0 R:R; soft bias-quality and
AMD-timing scores; deterministic exact-candidate and sweep/MSS narrative keys;
and append-only `audit_log` serialization through an injected Supabase client.
Audit insert failures raise and must block execution.

Post-review corrections require session-safety and strategy-selectivity state to
be explicitly resolved and complete before a setup can pass; make bias-quality
and AMD-timing promotion functional through validated score thresholds; and
reject NaN/infinite setup numbers at the immutable `Setup` construction
boundary before filtering or audit serialization.

Following owner review of the ICT 2022 model, the speculative fixed 60-minute
cooldown was removed. Rejected candidates do not consume killzone quota. Only
accepted setups count toward the one-per-killzone limit, exact candidates cannot
be evaluated twice, and an accepted sweep/MSS narrative cannot be entered twice.
A genuinely new narrative may still qualify less than 60 minutes later, subject
to the daily and killzone caps.

Verification: `$env:PYTHONPATH='.'; python -m pytest -q
tests/test_setup_filter.py tests/test_eurusd_model.py` passed (53 tests);
`python -m ruff check backend/strategies/setup_filter.py
backend/strategies/eurusd_model.py tests/test_setup_filter.py
tests/test_eurusd_model.py`, focused Pyright, `compileall`, and `git diff
--check` passed.

Only after the EURUSD model is complete, create `backend/strategies/setup_filter.py`.

Add Pydantic filter models, the five configured checks, `evaluate()`, and `log_filter_result()` for the existing `audit_log` table. The filter receives only `Setup`, never raw candle data.

Start with structural selectivity, confluence, and R:R as hard gates. Keep bias
quality and AMD timing as soft scores. Apply the separate session-safety gates
before setup-quality scoring, and verify every pass/fail case plus the audit
insert payload.

### 5. Connect the completed strategy to execution

Update the minimal integration points only:

- Instantiate `EURUSDModel` from `backend/runners/eurusd.py`.
- Normalize broker candle timestamps to UTC before strategy evaluation.
- Audit every candidate with `setup_filter.evaluate()`.
- Build, save, and publish an existing Verdict only after the setup passes the filter.
- Resolve daily/killzone selectivity from strategy-level accepted setups; never
  suppress the shared market signal using one account's trade history.
- Because `audit_log` is account-owned, write the same strategy-level filter
  outcome as an account-scoped audit projection for every eligible account.
  `account_id` scopes audit visibility only and must not influence evaluation.

Keep `worker.py`, `position_monitor.py`, Redis behavior, and existing Verdict persistence unchanged. Confirm the mapping from `Setup`/killzone values to existing Verdict scenarios before integrating.

Verify rejection, invalid configuration, audit failure, and Verdict-save failure all fail closed. A rejected setup must never create a Verdict.

### 6. Build shared `TradingConditions`

Status: planned future work; do not implement until Steps 1–5 are verified and
the owner explicitly authorizes this step with `NEXT`.

**Boundary with Lumibot:** Lumibot remains authoritative for the configured
market schedule and strategy lifecycle. It owns the `24/5` forex schedule,
weekend/market-closed handling, `on_trading_iteration()` timing, and the current
strategy time from `self.get_datetime()`. `TradingConditions` must not duplicate
those responsibilities.

**Missing calendar coverage only:** After Lumibot reports that the market is
open, `backend/services/trading_conditions.py` resolves only the economic-event
and liquidity-calendar restrictions Lumibot does not provide:

- the official NFP/US Employment Situation release day;
- the configured FOMC decision event window; and
- explicit US and EUR/Eurozone holiday-liquidity blocks that are not expressed
  by Lumibot's generic forex schedule.

It must populate only the calendar-derived portion of
`SessionSafetyContext`, using the existing `is_nfp_release_day` contract so
rescheduled official releases cannot be missed. DOL selection, ADR exhaustion,
DXY conflict, and all ICT pattern evidence remain closed-candle
strategy/filter calculations; they are not responsibilities of
`TradingConditions`.

The resolver must refresh calendar data outside Lumibot's per-minute trading
iteration, return a local cached result during strategy evaluation, and fail
closed when its sources are unavailable, stale, malformed, or incomplete.
Use official BLS and Federal Reserve schedules plus an explicit holiday policy;
do not treat Lumibot's market-session calendar as a complete economic calendar.

**Decision order:** Lumibot market closed means no strategy evaluation. If
Lumibot reports open, unresolved/stale `TradingConditions` data fails closed;
a resolved blocked event rejects and audits the candidate; only a resolved,
clear result proceeds to the strategy filter.

Verify official-source parsing with deterministic fixtures; Lumibot-closed
short-circuiting without a calendar lookup; NFP release-day, FOMC-window, and
holiday-policy blocks; stale-cache and source-failure rejection; and that no
Verdict can be created when the calendar-derived context is unresolved.

### 7. Final step: modularize the reusable filter framework for future strategies

Status: planned future work; do not implement before Steps 5 and 6 are
verified.

**Why this exists:** Every strategy needs the same disciplined plumbing:
fail-closed safety-context validation, candidate/audit identity, per-session
quotas, deduplication, hard/soft gate orchestration, and append-only audit
logging. Rewriting those mechanics for each instrument would create divergent
trade-safety behavior and make later strategies harder to verify. At the same
time, forcing EURUSD's ICT confluence, DXY, and AMD rules onto instruments
with different market behavior would be incorrect.

**Implementation:** Retain `backend/strategies/setup_filter.py` as the shared
framework. Extract EURUSD-only checks and configuration into
`backend/strategies/eurusd_filter_rules.py`. The shared filter accepts an
instrument-specific rule set/configuration while continuing to construct the
same `FilterResult` and append the same audit record. Future strategies add
their own `<instrument>_filter_rules.py` only when their rules differ; they
reuse `TradingConditions` and the shared filter framework.

**Acceptance criteria:** EURUSD produces identical pass/reject outcomes and
audit payloads for the existing fixture suite after extraction; shared
framework tests cover unresolved context, quotas, deduplication, hard/soft
gate behavior, and audit-write failure; and a small fake second-instrument
rule set proves a new strategy can plug in without copying the framework.

## Fixed initial defaults

- London killzone: 02:00–05:00 New York time.
- NY AM killzone: 07:00–10:00 New York time; preferred entry sub-window 08:30–10:00 NY, not an exclusive gate.
- Maximum strategy-level accepted setups per day: 2; per-account execution
  limits remain worker responsibilities.
- No fixed time cooldown: deduplicate exact candidates and accepted sweep/MSS narratives.
- Maximum setups per killzone: 1.
- Minimum confluence categories: 2 of 3.
- Minimum MSS displacement: 1.5 ATR.
- Minimum R:R: 3.0.
- Displacement: body >= 1.5 ATR14 and body-to-wick ratio >= 70%.
- Stop offset: 2–3 pips beyond the displacement swing; reject above 20 pips.
- Target priority: opposing Asian/London liquidity, then 80% ADR, then 20–30 pip scalp fallback.
- DXY/SMT: contextual evidence; do not require confirmation for every EURUSD setup. Clear DXY structural conflict remains a separate safety invalidation.
- Execution refinement: M5 primary; M3/M1 optional only after the setup is already confirmed.
- Session safety: Lumibot owns `24/5`/market-closed scheduling;
  `TradingConditions` later supplies only missing holiday, NFP/Employment
  Situation, and FOMC calendar restrictions; strategy/filter calculations own
  absent DOL, exhausted ADR, and DXY conflict. Every unresolved or blocked gate
  fails closed and is audit logged.

`TradingConditions` is deliberately deferred until after verified EURUSD
execution integration. Filter modularization is the final planned step after
`TradingConditions`; both complete before any additional strategy is added.

Do not tune these values or alter hard/soft filter status during this implementation.

## Next step

Implement Step 5, connecting the completed strategy and filter to the existing execution boundary.
