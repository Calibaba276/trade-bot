# ICT 2022 Mentorship: EUR/USD (Forex) Execution Rules

Instrument-specific setup, entry, invalidation, stop-loss, and target logic for EUR/USD. This file assumes the shared session windows, risk caps, and checklist defined in [ICT_Core_Framework.md](./ICT_Core_Framework.md) — read that first.

---

## EUR/USD (Forex)

**A. HTF Bias & Correlation Anchor**
- Timeframes: Daily, 4-Hour (4H), 1-Hour (1H) (Episode 2, Episode 11).
- Correlation Anchor: Always evaluate the US Dollar Index (DXY) in parallel:
  - IF DXY is reaching for Buyside Liquidity: THEN EUR/USD Bias = Bearish (reaching for Sellside Liquidity) (Episode 11, Episode 12).
  - IF DXY is reaching for Sellside Liquidity: THEN EUR/USD Bias = Bullish (reaching for Buyside Liquidity).
- SMT Divergence: Compare EUR/USD against GBP/USD. If EUR/USD makes a lower low while GBP/USD makes a higher low at 02:00–04:00 AM or 08:30 AM NY: Bullish SMT is confirmed (Episode 11).

**B. Setup Trigger (Price Action Event)**
- Operational Windows: London Open (02:00 AM – 05:00 AM NY) or New York Open (07:00 AM – 10:00 AM NY) (Episode 2, Episode 11).
- Trigger Mechanism (The Judas Swing):
  - Bullish Day: Price creates a false decline below Asian Range Low (07:00 PM – 00:00 NY low) or previous day low between 02:00 and 04:00 AM NY (Episode 2).
  - Bearish Day: Price creates a false rally above Asian Range High or previous day high between 02:00 and 04:00 AM NY (Episode 2).

**C. LTF Confirmation & Entry**
- Timeframe: 5m or 15m (5m is standard for Forex in the 2022 Mentorship) (Episode 2, Episode 11).
- Displacement breaking an established 5m swing high/low with a clean FVG.
- Entry: Limit order at FVG boundary or 50% CE during 02:30–04:00 AM NY (London) or 08:30–10:00 AM NY (New York).

**D. Invalidation, Stop-Loss & Target Rules**
- Invalidation: Breach of the high/low that swept liquidity prior to filling the FVG; or DXY breaking market structure in the same direction (positive correlation anomaly) (Episode 11).
- Stop-Loss: Placed 2 to 3 pips outside the swing high/low that initiated displacement. Maximum allowed stop: 15–20 pips (Episode 2).
- Take-Profit: Opposing Asian / London session high/low, 80% ADR projection, or standard 20–30 pip day-trade scalp target (Episode 2, Episode 11).
