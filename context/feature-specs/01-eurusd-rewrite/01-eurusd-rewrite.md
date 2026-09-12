# Glass Box Trading Engine — EURUSD Model Spec

**Status:** Finalized implementation spec — reflects all decisions reached to date.
**Scope:** Full rewrite of `eurusd_model.py` (ICT signal detection) + new `setup_filter.py` (setup selectivity layer)
**Does not cover:** `verdict.py`, `worker.py`, `position_monitor.py` — those stay as-is; this spec only produces the `Verdict` object and hands it off.

**Key decisions this spec locks in:**
- ICT detection logic follows the EURUSD execution rules in `.md/ict/ICT_EURUSD_Forex.md` plus the shared core framework: correlation-aware bias → session/range context → draw on liquidity → Judas Swing sweep → MSS/displacement → FVG/OB retracement entry, kept as pure pattern detection with no backtest-driven tuning
- Selectivity (which valid setups are actually worth trading) is handled entirely in a separate `setup_filter.py` module, with each of its 5 checks weighted by how much real evidence supports it — cooldown and confluence as hard gates, bias quality/liquidity-target/AMD-timing as soft-scored until backtest data earns them more trust
- All models are Pydantic, not dataclasses, for runtime validation and serialization
- All internal timestamps are UTC; killzone windows are defined in NY-local time (DST-aware) and converted at runtime — never hardcoded as a fixed clock string in any timezone
- Every filter evaluation, pass or reject, is written to a Supabase `audit_log` table — this is the evidentiary backbone of the "Verify, Don't Trust" positioning
- Parameter tuning is deferred until the backtest produces enough resolved trades to trust it, not decided upfront

---

## 1. Why this split exists

Two modules, two jobs, never blur them:

- **`eurusd_model.py`** — pure ICT pattern detection. Answers "does a valid setup exist right now?" This is the pure-strategy layer. Implement exactly as specified below — no backtest-driven tuning inside this file.
- **`setup_filter.py`** — selectivity layer. Answers "is this specific setup worth trading?" This is where thresholds live and where you'll iterate the most.

```
Market Data (MT5 candles)
        │
        ▼
┌─────────────────────┐
│  eurusd_model.py     │   Detects: bias, range, sweep, MSS, FVG, OB
│  (ICTModel class)     │   Output: Setup or None
└──────────┬───────────┘
           ▼
┌─────────────────────┐
│  setup_filter.py      │   Scores + gates: 5 checks below
│  (evaluate())          │   Output: FilterResult (pass/fail + reasons)
└──────────┬───────────┘
           ▼
   verdict_builder.py   →   Verdict dataclass   →   Redis   →   worker.py
```

Rationale from prior research: a self-reported backtest found a fully mechanical ICT bot (real pattern detectors, no selectivity judgment) lost money over a year (29.6% win rate, PF 0.81). The same patterns, filtered by judgment that said "no" 92% of the time, made money (40.4% win rate, PF 1.99). **The pattern detectors are not the edge. The filter is.** This is why `setup_filter.py` gets its own spec section with as much rigor as the detection logic.

---

## 2. Timezone Handling — UTC Internally, WAT for Display Only

### 2.1 The standard

**Every timestamp stored, compared, or computed against inside `eurusd_model.py` and `setup_filter.py` is UTC.** This is standard practice for a system that will eventually run across a 50-account fleet potentially spanning brokers/servers in different regions — one unambiguous internal clock, no exceptions.

**WAT (Africa/Lagos) is a rendering concern only** — used when displaying timestamps to you (dashboards, logs meant for human reading, the audit log's human-facing columns). It is never used as the basis for a `<`, `>`, or `==` comparison in the strategy logic itself. WAT is fixed at UTC+1 year-round with no daylight saving, so converting UTC → WAT for display is a trivial fixed offset — but that simplicity is exactly why it must not leak into logic that needs DST-awareness (see §2.2).

### 2.2a The trap this creates — read this before writing any time logic

ICT killzones are defined in **New York time**, and New York *does* observe DST (EDT = UTC-4 in summer, EST = UTC-5 in winter). All internal comparisons happen in UTC, and **UTC itself shifts relative to NY-local twice a year** (the NY offset from UTC moves between -4 and -5). That means a killzone window's UTC boundaries change twice a year too — this must be computed from the NY-local definition at runtime, never hardcoded as a fixed UTC (or WAT) range.

| Period | NY killzone (NY local) | NY→UTC offset | UTC window | WAT window (display only) |
|---|---|---|---|---|
| DST (EDT, roughly Mar–Nov) | 07:00–10:00 ET | UTC-4 | 11:00–14:00 UTC | 12:00–15:00 WAT |
| Standard (EST, roughly Nov–Mar) | 07:00–10:00 ET | UTC-5 | 12:00–15:00 UTC | 13:00–16:00 WAT |

**Never hand-type a UTC or WAT clock string into config for a killzone.** Store the NY-local definition only, and convert at runtime with a real timezone library — that's the only way DST transitions are handled automatically instead of via a manually maintained lookup table that will eventually be forgotten and go stale.

### 2.2b The only correct implementation: convert with real timezone objects, store/compare in UTC

```python
from zoneinfo import ZoneInfo
from datetime import datetime, time, timezone

NY_TZ = ZoneInfo("America/New_York")   # DST-aware — handles EDT/EST automatically
WAT_TZ = ZoneInfo("Africa/Lagos")      # fixed UTC+1, display only, never used in comparisons

def ny_killzone_window_utc(reference_date_utc: datetime, ny_start: time, ny_end: time) -> tuple[datetime, datetime]:
    """
    Given a reference UTC datetime and a killzone window defined in NY LOCAL
    time, return the equivalent window as UTC-aware datetimes. This is the
    ONLY safe pattern — never store a killzone boundary as a literal UTC or
    WAT clock string, always store the NY-local definition and convert at
    runtime so DST transitions are handled by zoneinfo automatically.
    """
    ny_date = reference_date_utc.astimezone(NY_TZ).date()
    start_ny = datetime.combine(ny_date, ny_start, tzinfo=NY_TZ)
    end_ny = datetime.combine(ny_date, ny_end, tzinfo=NY_TZ)
    return start_ny.astimezone(timezone.utc), end_ny.astimezone(timezone.utc)

def to_wat_for_display(dt_utc: datetime) -> datetime:
    """Convert a UTC-aware datetime to WAT purely for human-facing display/logs."""
    return dt_utc.astimezone(WAT_TZ)
```

**Config stores NY-local time only:**

```python
class KillzoneConfig(BaseModel):
    london_start_ny: time = time(2, 0)    # 2:00 AM ET
    london_end_ny: time = time(5, 0)      # 5:00 AM ET
    ny_am_start_ny: time = time(7, 0)
    ny_am_end_ny: time = time(10, 0)
```

**A comment noting the WAT-equivalent time next to these values is fine and encouraged for readability** (e.g. `# 8:00 AM ET ≈ 1:00-2:00 PM WAT depending on DST`) — comments don't execute, so they can't introduce the bug below. What must never happen is storing the *value itself* as a fixed UTC or WAT clock time (e.g. `ny_am_start_utc = time(12, 0)`). UTC doesn't shift, but NY's offset from UTC does (EDT vs EST), so a fixed UTC number for "NY AM open" is only correct for half the year and will silently drift out of alignment with the real session once DST changes — no crash, no error, just a killzone window quietly evaluating the wrong hour of the market for months. Keep the stored value NY-local as shown above; convert to UTC fresh at runtime via `ny_killzone_window_utc()` every time it's needed.

All candle timestamps from MT5 should be normalized to UTC on ingest and stay UTC through every internal computation. Convert to WAT only at the point of rendering — logs meant for you to read, dashboard timestamps, the audit log's display-facing column (§5).

### 2.2c Midnight range mark — pick which midnight you mean

The original ICT model marks the range from **midnight New York** to **London open (03:00 ET)**.

- **Original ICT Choice (matches original ICT teaching):** midnight-to-03:00 in **NY local time**, converted to UTC for storage and WAT for display.

Recommendation: **use Original ICT Choice** The ICT model's session logic is built around NY market microstructure (that's where USD liquidity concentrates), not around any particular trader's home timezone. Redefining the range to WAT midnight would be changing the strategy, not just translating a display — and that's exactly the kind of undocumented curve-fit risk you've flagged wanting to avoid. Store and compute from NY midnight (converted to UTC internally); render in WAT for your own readability only.

This NY-midnight-to-03:00 range is the premium/discount context range. It is not the only liquidity pool: EURUSD detection must also mark the Asian range (19:00–00:00 NY) and previous-day high/low for the instrument-specific Judas Swing. A sweep of the Asian low/PDL supports a bullish reversal; a sweep of the Asian high/PDH supports a bearish reversal.

---

## 3. `eurusd_model.py` — ICT Detection Layer

### 3.1 Class structure

```python
class EURUSDModel(Strategy):
    """
    Pure ICT pattern detection for EURUSD, following the 2022 Mentorship
    model structure (Huddleston). No selectivity logic lives here —
    that's setup_filter.py's job. All internal timestamps stored as
    timezone-aware datetimes; WAT used for logging/display, NY-local
    used for killzone and range-boundary computation (see §2).
    """
```

### 3.2 Timeframe roles (fixed, not configurable — this is structural to the model)

| Timeframe | Role |
|---|---|
| Daily / H4 | HTF bias determination |
| H1 | Range context, premium/discount zoning |
| M15 | Liquidity pool mapping (session highs/lows, equal highs/lows) |
| M5 / M3 / M1 | MSS confirmation, FVG/OB extraction, entry trigger |

### 3.3 State machine — sequence of steps every bar must evaluate

```python
class SetupState(str, Enum):
    AWAITING_BIAS = "awaiting_bias"
    AWAITING_RANGE = "awaiting_range"          # midnight-to-London range not yet closed
    AWAITING_SWEEP = "awaiting_sweep"
    SWEPT_AWAITING_MSS = "swept_awaiting_mss"
    MSS_CONFIRMED_AWAITING_FVG = "mss_confirmed_awaiting_fvg"
    AWAITING_RETRACEMENT = "awaiting_retracement"
    SETUP_READY = "setup_ready"                # candidate handed to setup_filter.py
```

State resets to `AWAITING_BIAS` at the start of each new trading day (00:00 NY local — see §2.2c) or if the setup invalidates (e.g., price closes back beyond the sweep extreme without ever confirming MSS — the read was wrong, stand down for that session).

### 3.4 Step-by-step logic

**Step 1 — HTF Bias and Correlation (`determine_bias`)**
- Input: Daily, H4, H1 EURUSD candles plus contemporaneous DXY candles; GBP/USD candles are optional only when available for SMT confirmation.
- Logic: identify confirmed EURUSD swing structure on Daily/H4/H1. Bias = bullish if the sequence shows higher-high + higher-low; bearish if lower-high + lower-low. A conflicting or choppy structure returns no bias.
- DXY is a contextual inverse-correlation anchor: DXY reaching buyside liquidity supports EURUSD bearish bias; DXY reaching sellside liquidity supports EURUSD bullish bias. Record the relationship when DXY data is available, but do not require DXY confirmation for every EURUSD setup. A clear DXY market-structure conflict is a risk warning and may invalidate the candidate under the session-safety policy.
- If GBP/USD makes a higher low while EURUSD makes a lower low during 02:00–04:00 NY or at 08:30 NY, record bullish SMT; mirror the rule for bearish SMT. SMT is recorded as evidence/confluence, not fabricated when GBP/USD data is absent.
- Reject (return `bias=None`) if EURUSD structure is conflicting or choppy. A missing or non-confirming DXY/SMT signal does not by itself reject an otherwise valid EURUSD setup; preserve it as evidence for the setup filter and audit record.
- Output: `bias: Literal["bullish", "bearish"] | None`, plus `bias_swing_count: int` (for the filter layer's bias-quality check later).

**Step 2 — Midnight Range Mark (`mark_range`)**
- At 00:00 NY local, start tracking high/low (see §2.2c for why NY local, not WAT).
- Freeze the range at 03:00 NY local (London open). Store as `range_high`, `range_low`.
- This range defines your **premium/discount midpoint**: `range_mid = (range_high + range_low) / 2`.
- Premium = price above `range_mid`. Discount = price below `range_mid`.
- **Hard filter, not optional:** only evaluate long setups when price is in discount; only evaluate short setups when price is in premium. If bias is bullish but price is currently in premium, wait — do not force the trade.

**Step 3 — Draw on Liquidity (`identify_target_liquidity`)**
- Candidate pools, in priority order: previous day high/low (PDH/PDL) and Asian range high/low (19:00–00:00 NY) > previous London/session high/low > M15 equal highs/equal lows > the opposite side of the NY-midnight range.
- Store the selected pool as `target_liquidity_level` and `target_liquidity_type` (string label, e.g. `"prev_day_high"`) — the filter layer needs to know *which kind* of pool this is to judge quality later.

**Step 4 — Liquidity Sweep Detection (`detect_sweep`)**
- A sweep = price **wicks through** a marked liquidity level (Asian range, PDH/PDL, previous session, or the range boundary) and **does not close beyond it** on that candle. For a bullish setup the sweep must be below sellside liquidity; for a bearish setup it must be above buyside liquidity.
- A close beyond the level is a breakout, not a sweep — do not treat it as a sweep signal.
- On sweep detected: record `sweep_time` (store as UTC internally, render WAT/NY as needed), `sweep_extreme_price`, `sweep_level_type`. Transition state to `SWEPT_AWAITING_MSS`.
- **Killzone tag (informational only at this layer):** use `ny_killzone_window_utc()` (§2.2b) to check whether `sweep_time` (UTC) falls inside London (02:00–05:00 NY) or New York (07:00–10:00 NY). Store as `sweep_in_killzone: bool` and `killzone_label: str | None`. The 08:30–10:00 NY period is the preferred New York sub-window, not the only permitted entry period. Do not reject here — this tag feeds `setup_filter.py`'s checks, not a hard gate in the detection layer.

**Step 5 — MSS Confirmation (`confirm_mss`)**
- Use M5 as the primary execution timeframe after the sweep (M15 may provide established swing context; do not use forming candles). M3/M1 may be used only as optional refinement after the higher-timeframe sweep and directional displacement are already confirmed; they must not manufacture a setup absent on M5/context.
- MSS = a candle **closes** (full body, not wick) beyond the most recent counter-trend swing point, in the direction of `bias`.
- Require a clean displacement candle: body size ≥ 1.5× ATR14 and body-to-wick ratio ≥ 70%; expose both as explicit constants, with no backtest tuning in this rewrite.
- On confirmation: record `mss_time`, `mss_candle_index`, `mss_swing_point`. Transition to `MSS_CONFIRMED_AWAITING_FVG`.
- **Invalidation:** if price closes back beyond `sweep_extreme_price` before MSS confirms, abandon this setup. After confirmation, invalidate if the swept extreme is breached before the FVG is filled, or if DXY breaks structure against the trade. Return to `AWAITING_SWEEP`/`AWAITING_BIAS` as appropriate.

**Step 6 — Extract FVG and Order Block (`extract_fvg_and_order_block`)**
- FVG: on the MSS displacement leg, take the 3-candle sequence. Bullish FVG = gap between candle 1 high and candle 3 low (candle 2 the impulsive one). Bearish = mirror.
- Compute `fvg_high`, `fvg_low`, `fvg_ce = (fvg_high + fvg_low) / 2`.
- Order Block: walk backward from the MSS displacement candle to the last opposing candle. Bullish OB = last bearish candle before the bullish impulse; mark its high/low.
- Both FVG and OB should exist for a clean setup — if only one exists, still proceed but tag `extract_fvg_and_order_block` so the filter's confluence count can weigh it correctly (see §4.4 — these are correlated, not independent, signals).

**Step 7 — Await Retracement (`check_retracement`)**
- Watch for price returning into the FVG or OB zone.
- Entry trigger (pick ONE, keep deterministic): price retraces to the FVG boundary or 50% CE (CE is preferred for a larger gap; use the boundary for a small gap) and a closed M5 candle—or an approved M3/M1 refinement candle after M5/context confirmation—confirms in the direction of `bias`. Use the OB boundary only when no FVG exists.
- Stop: place 2–3 EURUSD pips beyond the swing extreme that initiated displacement; reject the candidate if the stop distance exceeds 15–20 pips (use the configured hard maximum, never silently widen it).
- Target: use the selected opposing Asian/London liquidity or PDH/PDL first; if unavailable, use the 80% ADR projection or the documented 20–30 pip scalp target. Store the exact selected target and its source in `Setup`.
- On trigger: build `Setup` object, transition to `SETUP_READY`, hand off to `setup_filter.py`.

### 3.5 `Setup` — Pydantic model (contract between the two modules)

```python
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Literal, Optional

class Setup(BaseModel):
    timestamp: datetime          # UTC-aware, always. Convert to WAT only when displaying.
    instrument: Literal["EURUSD"] = "EURUSD"
    direction: Literal["long", "short"]

    # From Step 1
    bias: Literal["bullish", "bearish"]
    bias_swing_count: int = Field(ge=0)

    # From Step 2
    range_high: float
    range_low: float
    range_mid: float
    entry_zone: Literal["premium", "discount"]

    # From Step 3
    target_liquidity_level: float
    target_liquidity_type: str

    # From Step 4
    sweep_time: datetime
    sweep_extreme_price: float
    sweep_level_type: str
    sweep_in_killzone: bool
    killzone_label: Optional[str] = None
    dxy_bias_alignment: Optional[Literal["bullish", "bearish"]] = None
    smt_signal: Optional[Literal["bullish", "bearish"]] = None

    # From Step 5
    mss_time: datetime
    mss_candle_index: int
    sweep_candle_index: int
    mss_displacement_atr_multiple: float = Field(ge=0)

    # From Step 6
    fvg_high: Optional[float] = None
    fvg_low: Optional[float] = None
    fvg_ce: Optional[float] = None
    ob_high: Optional[float] = None
    ob_low: Optional[float] = None
    extract_fvg_and_order_block: Literal["fvg_only", "ob_only", "both"]

    # From Step 7
    entry_price: float
    stop_price: float
    target_price: float
    stop_distance_pips: float = Field(gt=0, le=20)
    target_type: Literal["opposing_asian_liquidity", "opposing_london_liquidity", "previous_day_high", "previous_day_low", "adr_80", "scalp_20_30_pips"]

    model_config = {"frozen": True}  # immutable once built — matches the "single handoff point" contract
```

**Why Pydantic over dataclass here:** you get runtime validation for free (e.g. `bias_swing_count: int = Field(ge=0)` rejects a negative count at construction time instead of silently propagating a bug downstream into `setup_filter.py`), plus `.model_dump()` / `.model_dump_json()` for the audit log in §5 without writing custom serialization. `model_config = {"frozen": True}` enforces the "immutable handoff, never reach back into raw candle data" rule structurally, not just by convention.

This model is the single handoff point. `setup_filter.py` only ever receives this — it never reaches back into raw candle data. Keeps the boundary clean.

---

## 4. `setup_filter.py` — Selectivity Layer

### 4.0 Separate hard session-safety gates

The five setup-quality checks below remain the selectivity layer. Separately, the evaluator must fail closed when a configured session-safety condition applies: US/UK bank holiday, NFP Friday, FOMC decision afternoon, no reachable draw on liquidity, exhausted ADR before the preferred New York sub-window, or a clear DXY structural conflict. These are safety/session gates, not confluence votes, and every blocked candidate must still be written to `audit_log` with the rejection reason.

### 4.1 Design contract — Pydantic throughout

```python
from pydantic import BaseModel, Field
from typing import Optional

class FilterCheckResult(BaseModel):
    check_name: str
    passed: bool
    score: float = Field(ge=0.0, le=1.0)
    weight: float = Field(ge=0.0)
    reason: str

class FilterResult(BaseModel):
    setup: Setup
    passed: bool                    # True only if all HARD gates passed
    composite_score: float
    checks: list[FilterCheckResult]
    rejected_by: Optional[str] = None   # name of the first hard-gate check that failed, if any
```

Every check function has this signature:

```python
def check_name(setup: Setup, context: "FilterContext", config: "FilterConfig") -> FilterCheckResult:
    ...
```

```python
class FilterContext(BaseModel):
    """Session-level state individual checks need but that isn't part of the immutable Setup."""
    trades_taken_today: int = 0
    last_setup_time: Optional[datetime] = None
    last_setup_killzone: Optional[str] = None
    setups_this_killzone: int = 0
```

### 4.2 Evidence-based weighting — this is the important part

The five candidate checks do **not** have equal evidentiary support. Build the pipeline so trust level is explicit in config, not implied by code structure:

| Check | Evidence level | Default mode |
|---|---|---|
| Cooldown / selectivity | Strongest support found | **Hard gate** |
| Confluence count (honest, non-correlated) | Moderate support, real overfitting risk if miscounted | **Hard gate**, conservative threshold |
| Bias quality | No direct evidence either way | **Soft score only** — log it, don't block on it yet |
| Liquidity target sanity | No direct evidence either way | **Soft score only** |
| AMD/manipulation timing | No direct evidence either way | **Soft score only** |

This table itself lives in `FilterConfig.hard_gate_checks` (a set of check names) — so you can promote a soft check to a hard gate later purely by changing config, once your own backtest data earns it that trust, not before.

### 4.3 Check 1 — Cooldown / Selectivity (hard gate)

**Rule:** limit trade frequency to force the same discipline that separated the winning backtest (92% refusal rate) from the losing one (fired on every valid pattern).

```python
def check_cooldown(setup: Setup, context: FilterContext, config: "FilterConfig") -> FilterCheckResult:
    if context.trades_taken_today >= config.max_trades_per_day:
        return FilterCheckResult(check_name="check_cooldown", passed=False, score=0.0, weight=1.0,
            reason=f"Daily trade cap reached ({config.max_trades_per_day})")

    if context.last_setup_time is not None:
        minutes_since_last = (setup.timestamp - context.last_setup_time).total_seconds() / 60
        if minutes_since_last < config.min_minutes_between_setups:
            return FilterCheckResult(check_name="check_cooldown", passed=False, score=0.0, weight=1.0,
                reason=f"Cooldown active: {minutes_since_last:.0f}m since last setup, need {config.min_minutes_between_setups}m")

    if context.last_setup_killzone == setup.killzone_label and context.setups_this_killzone >= config.max_setups_per_killzone:
        return FilterCheckResult(check_name="check_cooldown", passed=False, score=0.0, weight=1.0,
            reason=f"Killzone setup cap reached for {setup.killzone_label}")

    return FilterCheckResult(check_name="check_cooldown", passed=True, score=1.0, weight=1.0, reason="Cooldown clear")
```

**Config defaults (starting point — tune via backtest, not guess):**
- `max_trades_per_day: int = 2`
- `min_minutes_between_setups: int = 60`
- `max_setups_per_killzone: int = 1`

### 4.4 Check 2 — Confluence Count (hard gate, counted honestly)

**Critical correction from research:** FVG, OB, and premium/discount are correlated — they tend to co-occur because they're all downstream of the same displacement move. Do not count them as independent votes. Group into 3 real independent categories:

```python
def check_confluence(setup: Setup, context: FilterContext, config: "FilterConfig") -> FilterCheckResult:
    categories_met = 0
    details = []

    # Category 1: Structure quality (MSS strength)
    if setup.mss_displacement_atr_multiple >= config.min_displacement_atr:
        categories_met += 1
        details.append("structure")

    # Category 2: Liquidity quality (sweep type + target quality)
    if setup.sweep_level_type in config.high_quality_liquidity_types:
        categories_met += 1
        details.append("liquidity")

    # Category 3: Timing (killzone alignment)
    if setup.sweep_in_killzone:
        categories_met += 1
        details.append("timing")

    passed = categories_met >= config.min_confluence_categories
    score = categories_met / 3.0

    return FilterCheckResult(
        check_name="check_confluence", passed=passed, score=score, weight=1.0,
        reason=f"{categories_met}/3 independent categories met: {', '.join(details)}"
    )
```

Note: FVG/OB presence and premium-discount alignment are **not** separate categories here — they're folded into "structure quality" since they're mechanically linked to the same MSS event. This is the direct fix for the confluence-stacking overfitting risk flagged in research (stacking correlated signals inflates confidence without adding information).

**Config defaults:**
- `min_confluence_categories: int = 2` (out of 3 — require at least 2 of structure/liquidity/timing)
- `min_displacement_atr: float = 1.5`
- `high_quality_liquidity_types: list[str] = ["prev_day_high", "prev_day_low", "prev_session_high", "prev_session_low"]` (external range liquidity — stronger per research; equal-highs/lows on M15 alone = internal, weaker, excluded from "high quality" by default)

### 4.5 Check 3 — Bias Quality (soft score, not a gate — yet)

```python
def check_bias_quality(setup: Setup, context: FilterContext, config: "FilterConfig") -> FilterCheckResult:
    score = min(setup.bias_swing_count / config.ideal_bias_swing_count, 1.0)

    return FilterCheckResult(
        check_name="check_bias_quality", passed=True, score=score, weight=config.bias_quality_weight,
        reason=f"Bias swing count: {setup.bias_swing_count} (ideal: {config.ideal_bias_swing_count})"
    )
```

**Config defaults:**
- `ideal_bias_swing_count: int = 3`
- `bias_quality_weight: float = 0.5` (contributes to composite score, doesn't gate)

### 4.6 Check 4 — Liquidity Target Sanity (soft score, except the R:R half)

```python
def check_liquidity_target(setup: Setup, context: FilterContext, config: "FilterConfig") -> FilterCheckResult:
    reward_distance = abs(setup.target_price - setup.entry_price)
    risk_distance = abs(setup.entry_price - setup.stop_price)
    rr_ratio = reward_distance / risk_distance if risk_distance > 0 else 0

    passed = rr_ratio >= config.min_reward_risk_ratio  # this half CAN be a hard gate — it's arithmetic, not a judgment call
    score = min(rr_ratio / config.target_reward_risk_ratio, 1.0)

    return FilterCheckResult(
        check_name="check_liquidity_target", passed=passed, score=score, weight=config.liquidity_target_weight,
        reason=f"R:R = {rr_ratio:.2f} (min required: {config.min_reward_risk_ratio})"
    )
```

**Note:** the R:R arithmetic check is safe to hard-gate (it's not a judgment-based threshold, it's a structural requirement from the ICT model itself — 1:3 minimum per Huddleston's own teaching). Keep the *pool-quality* half of this check (is the target a stale/old level) as soft-scored only, since "how old is too old" has no evidence behind it yet — that half isn't implemented in this skeleton, add it as a separate scored component if you want it.

**Config defaults:**
- `min_reward_risk_ratio: float = 3.0` (matches the 2022 model's stated minimum)
- `target_reward_risk_ratio: float = 4.0` (score saturates above this)
- `liquidity_target_weight: float = 0.5`

### 4.7 Check 5 — AMD/Manipulation Timing (soft score)

```python
def check_amd_timing(setup: Setup, context: FilterContext, config: "FilterConfig") -> FilterCheckResult:
    if not setup.sweep_in_killzone:
        return FilterCheckResult(check_name="check_amd_timing", passed=True, score=0.0, weight=config.amd_timing_weight,
            reason="Sweep occurred outside defined killzone window")

    candles_to_mss = setup.mss_candle_index - setup.sweep_candle_index
    score = 1.0 if candles_to_mss <= config.max_candles_sweep_to_mss else 0.3

    return FilterCheckResult(
        check_name="check_amd_timing", passed=True, score=score, weight=config.amd_timing_weight,
        reason=f"Sweep-to-MSS: {candles_to_mss} candles (clean if ≤{config.max_candles_sweep_to_mss})"
    )
```

**Config defaults:**
- `max_candles_sweep_to_mss: int = 5` (aligns with "rapid reversal within one to five candles" from liquidity sweep research)
- `amd_timing_weight: float = 0.5`

### 4.8 `evaluate()` — the orchestrator

```python
FILTER_CHAIN = [
    check_cooldown,
    check_confluence,
    check_bias_quality,
    check_liquidity_target,
    check_amd_timing,
]

def evaluate(setup: Setup, context: FilterContext, config: "FilterConfig") -> FilterResult:
    results = []
    rejected_by = None

    for check_fn in FILTER_CHAIN:
        result = check_fn(setup, context, config)
        results.append(result)
        if not result.passed and config.is_hard_gate(result.check_name):
            rejected_by = result.check_name
            break

    passed = rejected_by is None
    composite_score = (
        sum(r.score * r.weight for r in results) / sum(r.weight for r in results)
        if results else 0.0
    )

    return FilterResult(
        setup=setup,
        passed=passed,
        composite_score=composite_score,
        checks=results,
        rejected_by=rejected_by
    )
```

### 4.9 `FilterConfig` — Pydantic model, everything tunable lives here

```python
class FilterConfig(BaseModel):
    # Per-check hard-gate/soft-score mode
    hard_gate_checks: set[str] = {"check_cooldown", "check_confluence", "check_liquidity_target"}

    # Cooldown
    max_trades_per_day: int = 2
    min_minutes_between_setups: int = 60
    max_setups_per_killzone: int = 1

    # Confluence
    min_confluence_categories: int = 2
    min_displacement_atr: float = 1.5
    high_quality_liquidity_types: list[str] = [
        "prev_day_high", "prev_day_low", "prev_session_high", "prev_session_low"
    ]

    # Bias quality (soft)
    ideal_bias_swing_count: int = 3
    bias_quality_weight: float = 0.5

    # Liquidity target
    min_reward_risk_ratio: float = 3.0
    target_reward_risk_ratio: float = 4.0
    liquidity_target_weight: float = 0.5

    # AMD timing (soft)
    max_candles_sweep_to_mss: int = 5
    amd_timing_weight: float = 0.5

    # Killzone windows — NY LOCAL time, never WAT (see §2.2b)
    london_start_ny: time = time(2, 0)
    london_end_ny: time = time(5, 0)
    ny_am_start_ny: time = time(7, 0)
    ny_am_end_ny: time = time(10, 0)

    def is_hard_gate(self, check_name: str) -> bool:
        return check_name in self.hard_gate_checks
```

Loaded per-account/per-instrument from Supabase, same pattern as `max_daily_drawdown_pct` — not hardcoded, so you can A/B different filter configs across your account fleet without a redeploy. Pydantic gives you `FilterConfig(**row_from_supabase)` with validation for free — a malformed config value from the DB raises immediately instead of silently misbehaving at 3am.

---

## 5. Audit Logging — Schema First, Then Implementation

**Recommendation: Supabase table, not a local file.** You already use Supabase for MT5 credentials and account data, so this fits your existing infrastructure rather than adding a new moving part. It's also queryable — "show me every setup rejected by `check_cooldown` last Tuesday across all 50 accounts" is a SQL query, not a grep through log files scattered across your fleet.

**Build order:** the table has to exist before either module can write to it, so this is step one — hand the migration below to whichever agent/process provisions your Supabase schema, get it applied, then implement `eurusd_model.py` and `setup_filter.py` against a confirmed-live table rather than a planned one.

### 5.1 Migration SQL

```sql
-- audit_log: every setup_filter.py evaluation, pass or reject.
-- Most rows will never become trades — that's expected and is the point
-- (Glass Box requirement: "why didn't it take that obvious trade" must
-- be answerable after the fact).
--
-- Timezone convention: every timestamptz column is stored/queried in UTC
-- (Postgres timestamptz is always UTC internally regardless of session
-- timezone — that's enforced by the column type itself, not a convention
-- that can drift). Convert to WAT at the display layer only, if needed —
-- nothing in this table stores a WAT-rendered value.

create table if not exists audit_log (
    id                      uuid primary key default gen_random_uuid(),

    -- Identity / routing
    account_id              uuid not null references broker_accounts(id),
    instrument              text not null,
    direction               text not null check (direction in ('long', 'short')),

    -- Timing (UTC)
    timestamp               timestamptz not null,   -- from Setup.timestamp — authoritative
    sweep_timestamp         timestamptz,
    mss_timestamp           timestamptz,
    killzone_label          text,                    -- e.g. 'london', 'ny_am', null if outside all killzones

    -- Filter outcome
    passed                  boolean not null,
    rejected_by             text,
    composite_score         double precision not null,
    checks_detail           jsonb not null,          -- full [FilterCheckResult, ...] list

    -- Setup context (denormalized from Setup for queryability without
    -- unpacking jsonb on every dashboard query — raw_setup below remains
    -- the full source of truth if these ever disagree)
    bias                    text,
    bias_swing_count        integer,
    entry_zone              text check (entry_zone in ('premium', 'discount')),
    target_liquidity_type   text,
    sweep_level_type        text,
    extract_fvg_and_order_block           text check (extract_fvg_and_order_block in ('fvg_only', 'ob_only', 'both')),
    entry_price             double precision,
    stop_price              double precision,
    target_price            double precision,
    reward_risk_ratio       double precision,       -- computed once, stored, avoids recompute on every query

    -- Full fidelity backup — reconstructs exactly what the model saw
    raw_setup               jsonb not null,

    created_at              timestamptz not null default now()
);

-- Query patterns this needs to support well:
--   "every reject by a given check, for a given account, in a date range"
--   "every setup for an account today" (dashboard/replay use case)
--   "every setup during the london killzone, regardless of account"
--   "average R:R of passed setups vs rejected setups" (evaluating filter usefulness)
create index if not exists idx_audit_log_account_time
    on audit_log (account_id, timestamp desc);

create index if not exists idx_audit_log_rejected_by
    on audit_log (rejected_by)
    where rejected_by is not null;

create index if not exists idx_audit_log_killzone
    on audit_log (killzone_label)
    where killzone_label is not null;

create index if not exists idx_audit_log_instrument_time
    on audit_log (instrument, timestamp desc);

comment on table audit_log is
    'Every setup_filter.py evaluation for EURUSD (and later instruments) — pass or reject. Source of truth for "why did/didn''t the engine take this trade." All timestamptz columns are UTC; convert to WAT at the display layer only.';
```

**Notes for whoever applies this:**
- Assumes a `broker_accounts` table with a `uuid` primary key already exists (per your existing Supabase schema for account data) — adjust the FK if the actual table/column name differs.
- `instrument` is left as free `text` rather than an enum/check-constraint, since XAUUSD and others will write to this same table later per your multi-instrument architecture — don't constrain it to `'EURUSD'` only.
- No WAT column exists in this table at all — WAT conversion happens only at whatever layer renders these rows for a human (dashboard, report), using `timestamp AT TIME ZONE 'Africa/Lagos'` in SQL or the Python `to_wat_for_display()` helper (§2.2b) at read time.
- The denormalized setup-context columns (`bias`, `entry_zone`, `reward_risk_ratio`, etc.) trade a little redundancy for the ability to run SQL aggregates directly (e.g. "average R:R of passed vs rejected setups") without unpacking `raw_setup` jsonb on every query. `raw_setup` remains the full-fidelity backup if these ever need reconciling.
- No `updated_at` — rows are append-only, never mutated after insert. If you ever need to correct a row, insert a new one rather than editing history; that's part of what makes "audit" mean anything.
- RLS (row-level security) policies aren't included here since that depends on how your Supabase project currently scopes access to `broker_accounts` — mirror whatever policy pattern that table already uses.

### 5.2 Column reference

| Column | Type | Notes |
|---|---|---|
| `id` | uuid, PK | |
| `account_id` | uuid, FK → broker_accounts | which account this evaluation ran for |
| `instrument` | text | `"EURUSD"` today, other instruments later |
| `direction` | text | `"long"` / `"short"` |
| `timestamp` | timestamptz | authoritative — from `Setup.timestamp`, UTC |
| `sweep_timestamp` | timestamptz, nullable | from `Setup.sweep_time`, UTC |
| `mss_timestamp` | timestamptz, nullable | from `Setup.mss_time`, UTC |
| `killzone_label` | text, nullable | `"london"` / `"ny_am"` / null |
| `passed` | boolean | did the setup clear all hard gates |
| `rejected_by` | text, nullable | which check rejected it, if any |
| `composite_score` | float | |
| `checks_detail` | jsonb | full `[FilterCheckResult, ...]` list, serialized |
| `bias` | text, nullable | `"bullish"` / `"bearish"` |
| `bias_swing_count` | integer, nullable | |
| `entry_zone` | text, nullable | `"premium"` / `"discount"` |
| `target_liquidity_type` | text, nullable | e.g. `"prev_day_high"` |
| `sweep_level_type` | text, nullable | |
| `extract_fvg_and_order_block` | text, nullable | `"fvg_only"` / `"ob_only"` / `"both"` |
| `entry_price` | float, nullable | |
| `stop_price` | float, nullable | |
| `target_price` | float, nullable | |
| `reward_risk_ratio` | float, nullable | precomputed, avoids recompute per query |
| `raw_setup` | jsonb | the full `Setup`, serialized — full-fidelity reconstruction |
| `created_at` | timestamptz | insert time |

### 5.3 Write pattern (implement once the table above is live)

```python
def log_filter_result(result: FilterResult, account_id: str, supabase_client) -> None:
    setup = result.setup
    risk_distance = abs(setup.entry_price - setup.stop_price)
    reward_distance = abs(setup.target_price - setup.entry_price)
    rr_ratio = reward_distance / risk_distance if risk_distance > 0 else None

    supabase_client.table("audit_log").insert({
        "account_id": account_id,
        "instrument": setup.instrument,
        "direction": setup.direction,

        "timestamp": setup.timestamp.isoformat(),
        "sweep_timestamp": setup.sweep_time.isoformat(),
        "mss_timestamp": setup.mss_time.isoformat(),
        "killzone_label": setup.killzone_label,

        "passed": result.passed,
        "rejected_by": result.rejected_by,
        "composite_score": result.composite_score,
        "checks_detail": [c.model_dump() for c in result.checks],

        "bias": setup.bias,
        "bias_swing_count": setup.bias_swing_count,
        "entry_zone": setup.entry_zone,
        "target_liquidity_type": setup.target_liquidity_type,
        "sweep_level_type": setup.sweep_level_type,
        "extract_fvg_and_order_block": setup.extract_fvg_and_order_block,
        "entry_price": setup.entry_price,
        "stop_price": setup.stop_price,
        "target_price": setup.target_price,
        "reward_risk_ratio": rr_ratio,

        "raw_setup": setup.model_dump(mode="json"),
    }).execute()
```

`setup.timestamp` must already be UTC-aware by the time it reaches this function (enforced upstream in `eurusd_model.py`, §2.2b). Nothing here converts to WAT — if a dashboard needs WAT-rendered timestamps, that conversion happens at read time in whatever queries or displays this table, not on write.

**Write this for every evaluated setup, pass or reject** — most records will never become trades, and that's the point. It's your evidence trail for "why didn't it take that obvious trade," which is core to the Glass Box positioning. If write volume ever becomes a concern at 50-account scale, batch inserts (accumulate a list, flush every N seconds) rather than dropping the practice of logging rejects.

**Sequencing for the agent doing this work:** apply the migration in §5.1 first and confirm the table exists in Supabase → then build `Setup`/`FilterResult` Pydantic models (§3.5, §4.1) → then implement `log_filter_result()` above and wire it into `evaluate()`'s call site → then build out the rest of `eurusd_model.py`/`setup_filter.py` logic. Writing against a schema that doesn't exist yet just means redoing the integration later.

---

## 6. Parameter Budget — Plain Explanation

**What "parameter" means here:** any number in `FilterConfig` you could turn up or down — `max_trades_per_day`, `min_reward_risk_ratio`, and so on. Every one of those is a knob.

**Why it matters:** the more knobs you have, the easier it becomes to accidentally find a combination that happens to look great on *your specific backtest window* purely by chance — not because it reflects anything real about the market. That's overfitting. It'll show a beautiful equity curve in testing and then lose money live, because you tuned to noise in the past, not a repeatable pattern.

**The rule of thumb from research:** you want roughly 10 to 20 real backtested trades for every knob you're tuning, before you trust that the tuning found something real rather than luck.

**Worked example for this spec:**

Knobs introduced across both files:
1. `min_displacement_atr`
2. `min_confluence_categories`
3. `max_trades_per_day`
4. `min_minutes_between_setups`
5. `max_setups_per_killzone`
6. `min_reward_risk_ratio`
7. `max_candles_sweep_to_mss`
8. `ideal_bias_swing_count`

**8 knobs total.**

8 knobs × 10-20 trades per knob = **you need 80 to 160 resolved trades in your backtest** before treating any tuning of these numbers as meaningful. If you run a backtest with 40 trades and find "wow, `max_trades_per_day = 3` performs way better than `2`" — that's not trustworthy yet. You don't have enough data to tell the difference between a real finding and coincidence. Keep collecting trades (or backtest a longer period) before locking in a value.

**Practical takeaway:** don't tune all 8 knobs at once against a small backtest. Either (a) gather enough trades first, or (b) fix most knobs at sensible defaults and only tune 1-2 at a time against what data you have, moving to the rest once you have more trades banked.

**Sequencing for this build specifically:** the defaults given in §4.3–§4.7 are starting points, not final values — ship the feature with those defaults first. Once `eurusd_model.py` and `setup_filter.py` are implemented and wired to the audit log (§5), run the backtest to accumulate resolved trades, then use that data to find the right values for these 8 parameters. Don't hand-tune them before the backtest exists — there's nothing to tune against yet, and guessing at "better" values now just means re-deciding them later anyway once real numbers are available.

---

## 7. What this spec deliberately does NOT decide for you

- **NY killzone boundary:** the EURUSD source strategy uses **07:00–10:00 ET**, with **08:30–10:00 ET as the preferred sub-window**, not an exclusive entry rule. M5 remains the primary execution timeframe; M3/M1 are optional refinements only after the setup is already confirmed. Any later timing or timeframe change requires a reviewed strategy decision and backtest evidence.

- **Whether `min_confluence_categories` should be 2 or 3 — shipping default: 2.**

  Reasoning:

  - There are only 3 possible categories (structure, liquidity, timing), so requiring all 3 means a setup fails if even one soft dimension is weak — a very tight gate before any backtest data exists to justify it
  - Starting at 2 lets the model generate enough trade volume to actually learn whether 3 is warranted
  - Starting at 3 risks producing too few trades to tell "correctly strict" apart from "starving the system"
  - Loosen-then-tighten is safer than tighten-then-discover-you-have-no-data

  Treat 2 as a placeholder — once backtesting begins, this is tunable in `FilterConfig` like any other parameter.

- **Whether soft-scored checks (bias quality, liquidity target pool-age, AMD timing) should ever graduate to hard gates — don't decide this now, and don't set an arbitrary graduation rule** (e.g. "after 100 trades, promote it").

  Reasoning:

  - Nothing in general trading research or ICT literature says which of these three actually deserves to be a hard gate — that's specific to how your own setups perform
  - Once you hit the resolved-trade threshold in §6, the process is: look at `composite_score` distributions for winners vs losers in `audit_log`
  - If a soft check's score correlates strongly with outcome (e.g. low bias-quality scores cluster with losses), that's evidence to promote it to `hard_gate_checks`
  - If it doesn't correlate with anything, leave it soft indefinitely — that's a legitimate outcome, not a failure to decide

- **Which of the two midnight-range conventions (§2.2c) to use if you later decide Option A doesn't suit your fleet** — flagged here as a documented, deliberate choice rather than an oversight
