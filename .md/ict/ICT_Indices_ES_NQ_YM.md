# ICT 2022 Mentorship: Indices Execution Rules (ES / NQ / YM)

Instrument-specific setup, entry, invalidation, stop-loss, and target logic for the US index futures triad. This file assumes the shared session windows, risk caps, and checklist defined in [ICT_Core_Framework.md](./ICT_Core_Framework.md) — read that first.

---

## S&P 500 E-mini Futures (ES)

**A. HTF Bias & Draw on Liquidity (DOL)**
- Primary Timeframes: Daily and 1-Hour (1H) (Episode 1, Episode 4).
- Rule: Mark Previous Day High (PDH), Previous Day Low (PDL), Overnight High/Low (00:00–08:30 AM), and prominent 1H FVGs.
- IF 1H structure makes higher highs/lows and price is below an unviolated Buyside Liquidity pool: THEN Bias = Bullish (Longs only).
- IF 1H structure makes lower highs/lows and price is above an unviolated Sellside Liquidity pool: THEN Bias = Bearish (Shorts only).

**B. Setup Trigger (Price Action Event)**
- Execution Timeframe: 1-Minute (1m) or 5-Minute (5m) (Episode 1, Episode 2, Episode 5).
- Long Trigger: Time between 08:30 AM and 11:00 AM NY. Price sweeps Sellside Liquidity (SSL) — either previous session low, overnight low, or a prominent intra-morning swing low.
- Short Trigger: Time between 08:30 AM and 11:00 AM NY. Price sweeps Buyside Liquidity (BSL) — either previous session high, overnight high, or a prominent intra-morning swing high.

**C. Lower Timeframe (LTF) Confirmation**

Following the sweep, wait for Displacement and Market Structure Shift (MSS) on the 1m or 5m chart (Episode 1, Episode 2, Episode 3):
- Displacement Criteria: Energetic, wide-range candles closing decisively in the opposite direction of the sweep.
- MSS Definition: A candle close strictly above the swing high preceding the sweep (for Longs), or strictly below the swing low preceding the sweep (for Shorts).
- FVG Formation: The displacement leg must create a clean 3-candle Fair Value Gap (BISI for Longs: Candle 3 Low > Candle 1 High; SIBI for Shorts: Candle 3 High < Candle 1 Low).

**D. SMT Divergence Filter (Indices Specific)**
- Compare ES against NQ and YM at the point of the sweep (Episode 7, Episode 10).
- IF NQ sweeps its swing high/low, but ES fails to sweep its corresponding level (forming a higher low or lower high): THEN ES demonstrates SMT Accumulation/Distribution. This confirms high-probability institutional presence.

**E. Entry Rule**
- Place a Limit Order at the boundary of the FVG (Candle 3 Low for BISI; Candle 3 High for SIBI) or at Consequent Encroachment (CE = 50% midpoint of the FVG) (Episode 1, Episode 4).
- Execution Window: Must fill before 11:00 AM NY. If unfilled by 11:00 AM, cancel the order.

**F. Invalidation Rule (Pre-Entry)**
- IF price violates the displacement swing extreme before tagging the FVG: THEN Setup is INVALID.
- IF price reaches the primary DOL before retracing to the FVG: THEN Cancel the limit order immediately (move completed; asymmetric risk/reward lost) (Episode 3, Episode 12).
- IF a full candle body closes beyond the opposing boundary of the FVG prior to entry: THEN Setup is INVALID (Episode 4).

**G. Stop-Loss Placement Rule**
- Hard Stop: Placed 1 to 2 ticks outside the displacement swing low (Long) or swing high (Short) (Episode 1, Episode 2).
- Conservative Stop Alternative: Placed just outside Candle 1 of the FVG formation if displacement anchor is exceptionally wide (Episode 4).

**H. Take-Profit & Target Logic**
- Primary Target: Opposing clean liquidity pool (relative equal highs/lows) or HTF 1H/Daily FVG.
- Minimum Fixed Target: 12 to 15 index points on ES (Episode 1).
- Scaling Rule: Close 75%–80% at +10 to +12 points or at the first internal swing; leave a 20%–25% runner for the major DOL (Episode 5, Episode 13).

---

## NASDAQ 100 E-mini Futures (NQ)

**A. HTF Bias & Draw on Liquidity (DOL)**
- Follows identical macro framework to ES: 1H / Daily structure determines direction toward external liquidity pools or unfilled imbalances (Episode 1, Episode 6).

**B. Setup Trigger (Price Action Event)**
- Window: 08:30 AM – 11:00 AM NY (AM session) or 01:30 PM – 03:00 PM NY (PM session) (Episode 6, Episode 17).
- Instrument Characteristic: NQ routinely runs stops much deeper than ES. A sweep of 20–40 points past an old high/low is normal before a valid displacement reversal forms (Episode 6).

**C. Lower Timeframe (LTF) Confirmation**
- Timeframe: 1m or 5m chart (Episode 1, Episode 8).
- High-velocity displacement closing beyond internal fractal structure, leaving a pronounced FVG.
- SMT Divergence Confirmation: NQ frequently leads or diverges. IF ES makes a new high and NQ fails to make a new high: THEN NQ confirms Bearish SMT Divergence (Episode 7, Episode 10).

**D. Entry Rule**
- Limit order placed at the nearest boundary of the FVG or at its 50% CE (Episode 8).
- NQ Calibration: Given NQ's volatility ($20/point per full contract, $2/point on micro), entries at 50% CE are preferred whenever the FVG exceeds 20 points in height to limit stop risk (Episode 8).

**E. Invalidation Rule (Pre-Entry)**
- IF price reaches terminal session objective prior to filling the FVG: THEN Cancel order.
- IF a 1-minute candle body closes completely through the FVG opposite edge: THEN Cancel entry order.

**F. Stop-Loss Placement Rule**
- Placed 1 point (4 ticks) beyond the extreme displacement swing high/low (Episode 1, Episode 8).
- Max Algorithmic Cap: If required stop exceeds 35–40 NQ points on a 1m chart, the setup is deemed sub-optimal; reduce contract size or invalidate trade (Episode 8).

**G. Take-Profit & Target Logic**
- Target 1 (Scalp / Partials): +40 to +50 points on NQ (equivalent to 10–12 points on ES) (Episode 8).
- Target 2 (Terminal Target): Unfilled 15m/1H FVG or Old Session High/Low (Episode 13).

---

## Dow Jones E-mini Futures (YM)

**A. HTF Bias & Instrument Role**
- Daily and 1H chart alignment. YM is evaluated primarily as a component of the US Index triad (ES, NQ, YM) (Episode 7).

**B. Setup Trigger & SMT Divergence**
- Role of YM: ICT routinely utilizes YM as an SMT divergence validator rather than a standalone primary vehicle (Episode 7, Episode 10).
- IF ES and NQ make new highs during the 08:30–10:00 AM window, but YM fails to make a new high: THEN YM confirms institutional distribution (bearish). Confirm short entries across the index triad.

**C. LTF Confirmation & Entry**
- Timeframe: 5m or 1m chart.
- Displacement breaking market structure + creation of a bearish FVG. Entry at FVG lower threshold (Episode 7).

**D. Invalidation, Stop-Loss & Target Rules**
- Invalidation: Candle body closure above the high that formed the SMT divergence.
- Stop-Loss: Placed 5 ticks above the swing high (or below swing low for longs).
- Take-Profit: Prior day swing lows, clean double bottoms, or overnight session lows. YM standard scalp objective: 75–100 points (Episode 7).
