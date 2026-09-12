# ICT 2022 Mentorship: Core Framework (Sessions, Risk, Checklist)

*A fully rule-based, reproducible execution framework reverse-engineered from Inner Circle Trader's 2022 Mentorship playlist.*

This is the shared foundation used by every instrument. Instrument-specific entry/exit logic lives in its own file:
- [Indices — ES, NQ, YM](./ICT_Indices_ES_NQ_YM.md)
- [EUR/USD — Forex](./ICT_EURUSD_Forex.md)

---

## 1. Pre-Session Preparation (All Instruments)

### 1.1 Time & Session Windows (All Times in New York EST / EDT)

ICT emphasizes that time is the primary filter; price action occurring outside defined algorithmic windows is considered erratic and should be ignored (Episode 1, Episode 3).

**Economic Calendar Review** (Check daily at 07:00–08:00 AM NY):
- Open Forex Factory or equivalent calendar. Filter strictly for High-Impact (Red Folder) events for USD, EUR, or GBP (Episode 2, Episode 12).
- IF Red Folder news is scheduled for 08:30 AM: THEN no execution prior to 08:30:00 AM. Let the release inject volatility; begin looking for setups only after initial post-release displacement (Episode 8).
- IF Red Folder news is scheduled for 10:00 AM: THEN expect the primary session swing or reversal to trigger right at or immediately following 10:00 AM (Episode 11).

**Operational Session Kill Zones:**
- London Kill Zone (Forex primarily): 02:00 AM – 05:00 AM NY (Episode 2).
- New York AM Kill Zone (Forex & Index Futures): 08:30 AM – 11:00 AM NY (Episode 1, Episode 3).
- New York PM Kill Zone (Index Futures primarily): 01:30 PM – 04:00 PM NY (Episode 12, Episode 17).
- Strict Terminal Cutoff: Any open day-trade position must be closed by 11:30 AM (for AM session) or 04:00 PM (for PM session). Holding through the 11:30 AM – 01:00 PM lunch consolidation is forbidden (Episode 16).

### 1.2 Macro & Higher Timeframe (HTF) Framework

Executed daily prior to the session open (Episode 1, Episode 2, Episode 5):

```
Step 1: Check Monthly & Weekly Chart
        └── Identify nearest Buyside Liquidity (BSL) or Sellside Liquidity (SSL) pool,
            or unfilled HTF Fair Value Gap (FVG).

Step 2: Check Daily Chart (Primary Filter for Day Trading)
        ├── Determine Daily Bias based on:
        │   ├── Has price recently swept a significant Swing High (BSL) or Swing Low (SSL)?
        │   └── Is price expanding toward an opposing unfilled Daily FVG or Old High/Low?
        └── IF Daily candle has tagged an HTF Key Level / FVG from above and rejected:
            THEN Daily Bias = BULLISH.
            IF Daily candle has tagged an HTF Key Level / FVG from below and rejected:
            THEN Daily Bias = BEARISH.

Step 3: Define "Draw on Liquidity" (DOL)
        └── The DOL is the specific, unreached level price is mathematically reaching toward:
            - Old High / Old Low (Daily / 4H / 1H)
            - Equal Highs (EQH) / Equal Lows (EQL)
            - Clean HTF Fair Value Gap (FVG) / Imbalance (SIBI / BISI)
```

### 1.3 Absolute "No-Trade" Conditions (Hard Filter)

Set system state to NO-TRADE if any of the following apply (Episode 2, Episode 12, Episode 24):

1. **Condition A (Bank Holidays):** US or UK bank holidays (low institutional participation).
2. **Condition B (NFP Friday):** Non-Farm Payroll Friday morning; ICT recommends standing aside entirely on NFP Fridays due to extreme slippage and whipsaws (Episode 12).
3. **Condition C (FOMC Afternoon):** FOMC Interest Rate Decision afternoons (02:00 PM – 02:30 PM NY); high likelihood of erratic gap expansions (Episode 24).
4. **Condition D (Absence of DOL):** IF Daily chart is consolidating in the dead center of a historical range with no clean liquidity pools or imbalances within reachable range, THEN stand aside.
5. **Condition E (Exhausted ADR):** IF Daily Average True Range (ADR) or projected expansion target has already been fully delivered during London prior to 08:30 AM NY, THEN stand aside.

---

## 3. Systematic Trade & Risk Management Rules

### 3.1 Maximum Risk Per Trade

- Hard Cap: Maximum 1.0% account equity risk per trade; conservative default is 0.5% (Episode 1, Episode 12).
- Formula: `Position Size = (Account Equity * Risk %) / (Stop Distance * Point/Pip Value)`.
- Daily Max Loss: IF two consecutive trades hit full stop-loss within the same calendar day: THEN terminate trading for the day (Episode 12).

### 3.2 Breakeven (BE) Logic

Stop-loss is moved to entry price (plus 1 tick/pip to cover commissions) ONLY AFTER price fulfills both criteria (Episode 1, Episode 5, Episode 13):

1. Price achieves a minimum of 1:1 Risk-to-Reward (R:R) OR tags the first internal liquidity pool / FVG.
2. First partial profit tranche (50% to 75%) has been executed.

**Negative Constraint:** Do NOT move stop-loss to breakeven prematurely. Price must be given room to retrace into the FVG a second time if needed (Episode 4, Episode 13).

### 3.3 Scaling Out (Partials) Protocol

```
Entry Execution: 100% position size
    │
    ├── Milestone 1: Price reaches +10-12 ES pts / +40-50 NQ pts / +20 EUR pips
    │   ├── Action: Close 50% to 75% of total position
    │   └── Action: Adjust Stop-Loss to Breakeven (Entry Price + 1 tick/pip)
    │
    └── Milestone 2: Price reaches Primary Draw on Liquidity (DOL) / Old Session Extreme
        ├── Action: Close remaining 20% to 25% of position
        └── Action: Flat position; cancel all outstanding resting orders
```

### 3.4 Mid-Flight Invalidation & Early Exit Rules

Exit an open position manually at market BEFORE Stop-Loss or Take-Profit is hit under these explicit conditions (Episode 4, Episode 16, Episode 26):

- **FVG Inversion Violation:** If price closes a candle body completely outside the opposite boundary of the entry FVG, the gap has inverted. Close position immediately at market (Episode 4).
- **Time-Stop Rule:** If entering during the 08:30–11:00 AM NY window and the trade has not delivered or shown energetic expansion toward the target by 11:15 AM: close the trade at market. Do not hold positions into the 11:30 AM lunch lull (Episode 16).
- **SMT Structural Failure:** If a strong SMT divergence forms directly against your trade direction at an opposing major key level, close the position immediately (Episode 10).

---

## 4. Ambiguity Log & Automation Verification Flags

**AMBIGUITY 1 — DISPLACEMENT:**
Displacement Threshold: ICT describes displacement visually as "energetic candles" and "obvious intent" (Episode 1, 2). For automation, enforce: Candle Body >= 1.5 × 20-period ATR AND Body-to-Wick Ratio >= 70%.

**EVOLUTION / CONFLICT — MSS:**
Market Structure Shift (Wick vs. Body): In early episodes (Ep 1, 2), ICT accepts wicks breaking swing points. In later episodes (Ep 4, 12), he mandates that wicks do the sweeping while candle bodies confirm the structural break. The final mechanized rule strictly requires a candle body close.

**AMBIGUITY 2 — NESTED FVGS:**
Multiple Nested FVGs: Displacement legs frequently create 2 or 3 overlapping FVGs across 1m–5m timeframes (Ep 5, 8). Automated rule: Anchor to the 5m FVG if present; otherwise, select the 1m FVG falling within 50%–61.8% retracement (discount/premium) of the displacement swing.

**RULE REFINEMENT — CE VS BOUNDARY:**
Consequent Encroachment (50%) vs Boundary Entry: IF the FVG height is <= 10 ticks on ES (or <= 15 pts on NQ), enter at the outer boundary. IF the FVG height is large, place the limit strictly at 50% CE to optimize risk-to-reward.

---

## 5. Master Daily Trader Execution Checklist

```
[ ] 07:30 AM NY: Open Economic Calendar
    [ ] Any Red Folder events at 08:30 AM or 10:00 AM? Note exact times.
    [ ] Verify neither Bank Holiday nor NFP Friday nor FOMC afternoon.

[ ] 08:00 AM NY: Chart Setup (Daily & 1-Hour)
    [ ] Mark Previous Day High (PDH) and Previous Day Low (PDL).
    [ ] Mark Midnight (00:00 AM NY) Open price level.
    [ ] Mark Overnight (Asia/London) High and Low.
    [ ] Determine primary Draw on Liquidity (DOL).

[ ] 08:30 AM – 11:00 AM NY: Live Execution Window
    [ ] STEP 1: Wait for liquidity sweep of an established High/Low into DOL.
    [ ] STEP 2: Verify SMT Divergence across ES / NQ / YM (or EUR / GBP / DXY).
    [ ] STEP 3: Wait for Displacement Leg with a 1m or 5m candle body close (MSS).
    [ ] STEP 4: Confirm 3-candle Fair Value Gap (FVG) creation within displacement.
    [ ] STEP 5: Place Limit Order at FVG boundary or 50% CE.
    [ ] STEP 6: Place Stop-Loss 1-2 ticks outside the displacement swing extreme.
    [ ] STEP 7: Check Max Risk <= 1% of account equity.

[ ] Post-Entry Management:
    [ ] IF target not hit and FVG closes candle body on wrong side: EXIT AT MARKET.
    [ ] IF price reaches 1:1 R:R / first internal pool: TAKE 50-75% PARTIALS & MOVE SL TO BE.
    [ ] IF clock hits 11:15 AM NY and position is stagnant: CLOSE AT MARKET.
    [ ] Terminate trading session by 11:30 AM NY.
```
