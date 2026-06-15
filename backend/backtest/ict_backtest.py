"""
Standalone backtest harness for the ICT Model strategy (backend/strategies/ict_model.py).

This is a faithful, dependency-light re-implementation of the decision logic in
ICTModel.on_trading_iteration. It does NOT import lumibot / supabase / MT5 (none of
which can run in this environment); instead it drives the exact same branching over
1-minute bars and then resolves each emitted signal against future price action.

Data source: Oanda EUR/USD 1-minute bars (2005-2020) from the GitHub-hosted
FutureSharks/financial-data dataset. Timestamps in the raw files are UTC; the live
strategy runs in Africa/Lagos (UTC+1, no DST), so we shift +1h to reproduce the
session windows the strategy keys off (06:00 range, 09:00 London, 13:30 NY, 16:00 close).

Modelling choices (documented so results are interpretable):
  * last_price            = close of the current 1-minute bar
  * get_historical_prices = the last N completed bars up to and incl. the current one
  * Entry                 = LIMIT order at the strategy's entry_price. It only becomes a
                            trade if price touches that level before the signal day ends
                            (unfilled signals are discarded; fill-rate is reported).
  * Outcome               = from the fill bar onward, scan bars and see whether SL or TP
                            is touched first (intrabar high/low). If a single bar straddles
                            both levels, it is counted as a LOSS (conservative). Trades that
                            resolve neither within MAX_HOLD_MIN are marked 'open'.
  * Risk                  = fixed $RISK per trade, reward = RISK * RR on a win.
"""

from __future__ import annotations

import glob
import os
from dataclasses import dataclass, field
from datetime import time, date

import pandas as pd

# ── Parameters (mirror backend/runners/ict.py production config) ──────────────
RR_RATIO = 3.0
RISK = 500.0           # $ risked per trade
BUFFER = 0.0002        # self.buffer in the strategy
MAX_HOLD_MIN = 3 * 24 * 60  # cap how long an open position is tracked (3 days)
HTF_BIAS_PERIOD = 20   # daily SMA lookback for the directional bias filter

DATA_ROOT = os.path.join(os.path.dirname(__file__), "..", "..", "_fxdata")


# ── Data loading ──────────────────────────────────────────────────────────────
def load_data(pair, years) -> pd.DataFrame:
    pattern = os.path.join(DATA_ROOT, pair, "*", f"oanda-{pair}-*.csv")
    paths = sorted(glob.glob(pattern))
    frames = []
    for p in paths:
        # filename: oanda-<PAIR>-<year>-<month>.csv  (pair contains an underscore)
        yr = int(os.path.basename(p).split("-")[2])
        if yr in years:
            frames.append(pd.read_csv(p))
    if not frames:
        raise SystemExit(f"No data files matched {pattern} for years {years}")
    df = pd.concat(frames, ignore_index=True)
    df["time"] = pd.to_datetime(df["time"])
    df = df.drop_duplicates("time").sort_values("time").reset_index(drop=True)
    # raw is UTC -> shift to Africa/Lagos (UTC+1) naive local time the strategy uses
    df["time"] = df["time"] + pd.Timedelta(hours=1)
    df = df.set_index("time")
    return df[["open", "high", "low", "close"]]


# ── Per-day strategy state (mirrors initialize/before_market_opens fields) ─────
@dataclass
class State:
    traded_london: bool = False
    traded_ny: bool = False
    last_range_date=None
    ny_range_date=None
    pdh=None
    pdl=None
    swept_high=None
    swept_low=None
    mss_swing_low=None
    mss_swing_high=None
    fvg_top=None
    fvg_bottom=None
    bearish_fvg_confirmed=False
    bullish_fvg_confirmed=False
    highest_sweep_point=None
    lowest_sweep_point=None
    london_low=None
    london_high=None
    pre_ny_low=None
    pre_ny_high=None
    ny_ote_hit_bullish=None
    ny_ote_hit_bearish=False
    daily_bias=None        # "bull" | "bear" | None
    session_scenario=None
    ny_range_high=None
    ny_range_low=None
    ny_sweep_high=False
    ny_sweep_low=False
    sweep_peak=None
    sweep_trough=None


@dataclass
class Signal:
    dt: object
    direction: str
    entry: float
    sl: float
    tp: float
    scenario: str
    rr: float = RR_RATIO
    # resolution (filled later)
    filled: bool = False
    fill_dt: object = None
    outcome: str = "unfilled"   # unfilled | win | loss | open
    pnl: float = 0.0


def calc_tp(entry, sl, direction, rr):
    risk = abs(entry - sl)
    if risk <= 0:
        return None
    return entry + risk * rr if direction == "buy" else entry - risk * rr


# ── The ported decision logic ─────────────────────────────────────────────────
class Sim:
    def __init__(self, df: pd.DataFrame):
        self.df = df
        self.idx = df.index
        self.high = df["high"].values
        self.low = df["low"].values
        self.close = df["close"].values
        self.n = len(df)
        self.s = State()
        self.signals: list[Signal] = []

        # ICT daily bias: previous completed daily candle's close vs its range
        # midpoint. shift(1) => yesterday's candle decides today's bias (no
        # look-ahead). bull if close >= midpoint else bear.
        daily = df.resample("1D").agg(high=("high", "max"), low=("low", "min"),
                                      close=("close", "last")).dropna()
        mid = (daily["high"] + daily["low"]) / 2.0
        bias_today = (daily["close"] >= mid).map({True: "bull", False: "bear"})
        bias_prev = bias_today.shift(1)
        self.bias_for_date = {ts.date(): v for ts, v in bias_prev.items()}

    def _bias_allows(self, direction):
        if self.s.daily_bias is None:
            return False
        return self.s.daily_bias == ("bull" if direction == "buy" else "bear")

    def hist(self, i, N):
        """Last N completed bars up to and including bar i (like get_historical_prices)."""
        lo = max(0, i - N + 1)
        return self.df.iloc[lo:i + 1]

    def _emit(self, dt, direction, entry, sl, liquidity, scenario):
        """ICT target = opposing liquidity pool; require >= RR_RATIO (min 1:3),
        else skip the trade."""
        risk = abs(entry - sl)
        if risk <= 0 or liquidity is None:
            return False
        if direction == "buy":
            if liquidity <= entry:
                return False
            rr = (liquidity - entry) / risk
        else:
            if liquidity >= entry:
                return False
            rr = (entry - liquidity) / risk
        if rr < RR_RATIO:
            return False
        self.signals.append(Signal(dt=dt, direction=direction, entry=float(entry),
                                   sl=float(sl), tp=float(liquidity), scenario=scenario,
                                   rr=float(rr)))
        return True

    def run(self):
        prev_date = None
        for i in range(self.n):
            dt = self.idx[i]
            d = dt.date()
            ct = dt.time()
            if d != prev_date:
                self.s = State()        # before_market_opens reset
                prev_date = d
            self.step(i, dt, d, ct)
        self.resolve()
        return self.signals

    def step(self, i, dt, current_date, current_time):
        s = self.s
        last_price = self.close[i]

        # After 9:00, capture 06:00-08:59 high/low as PDH/PDL
        if current_time >= time(9, 0) and s.last_range_date != current_date:
            df = self.hist(i, 200)
            morning = df.between_time("06:00", "08:59")
            if not morning.empty:
                s.pdh = float(morning["high"].max())
                s.pdl = float(morning["low"].min())
                s.last_range_date = current_date
                b = self.bias_for_date.get(current_date)
                if b is not None and not (isinstance(b, float) and pd.isna(b)):
                    s.daily_bias = b
            else:
                return

        if not (s.pdh and s.pdl):
            return

        # ── LONDON 09:00-11:00 ────────────────────────────────────────────────
        if time(9, 0) <= current_time < time(11, 0) and not s.traded_london:
            if s.london_low is None or last_price < s.london_low:
                s.london_low = last_price
            if s.london_high is None or last_price > s.london_high:
                s.london_high = last_price

            bar_high, bar_low = self.high[i], self.low[i]

            # BEARISH: step1 sweep above high (wick-based)
            if bar_high > s.pdh:
                s.swept_high = True
                if s.highest_sweep_point is None or bar_high > s.highest_sweep_point:
                    s.highest_sweep_point = bar_high

            # step2 reverse below high, scan swing low
            if s.swept_high and last_price < s.pdh and s.mss_swing_low is None:
                lows = self.hist(i, 20)["low"].values
                for k in range(len(lows) - 2, 0, -1):
                    if lows[k] < lows[k - 1] and lows[k] < lows[k + 1] and lows[k] > s.pdl:
                        s.mss_swing_low = float(lows[k])
                        break
                if s.mss_swing_low is None:
                    return

            # step3 break below swing low -> FVG check
            if s.mss_swing_low and last_price < s.mss_swing_low and not s.bearish_fvg_confirmed:
                df = self.hist(i, 5)
                if len(df) < 3:
                    return
                c1 = float(df.iloc[-3]["low"])
                c2 = float(df.iloc[-1]["high"])
                if c1 > c2:
                    s.fvg_top = c1
                    s.fvg_bottom = c2
                    s.bearish_fvg_confirmed = True
                    s.bullish_fvg_confirmed = False
                else:
                    return

            # bearish execution
            if s.bearish_fvg_confirmed and s.highest_sweep_point is not None and self._bias_allows("sell"):
                entry = s.fvg_bottom
                sl = s.highest_sweep_point + BUFFER
                if self._emit(dt, "sell", entry, sl, s.pdl, "london_bearish"):
                    s.traded_london = True

            # BULLISH: step1 sweep below low (wick-based, elif chained as in source)
            elif bar_low < s.pdl:
                s.swept_low = True
                if s.lowest_sweep_point is None or bar_low < s.lowest_sweep_point:
                    s.lowest_sweep_point = bar_low

            # step2 reverse above low, scan swing high
            if s.swept_low and last_price > s.pdl and s.mss_swing_high is None:
                highs = self.hist(i, 20)["high"].values
                for k in range(len(highs) - 2, 0, -1):
                    if highs[k] > highs[k - 1] and highs[k] > highs[k + 1] and highs[k] < s.pdh:
                        s.mss_swing_high = float(highs[k])
                        break
                if s.mss_swing_high is None:
                    return

            # step3 break above swing high -> FVG
            if s.mss_swing_high and last_price > s.mss_swing_high and not s.bullish_fvg_confirmed:
                df = self.hist(i, 5)
                if len(df) < 3:
                    return
                c1 = float(df.iloc[-3]["high"])
                c2 = float(df.iloc[-1]["low"])
                if c1 < c2:
                    s.fvg_top = c2
                    s.fvg_bottom = c1
                    s.bullish_fvg_confirmed = True
                    s.bearish_fvg_confirmed = False
                else:
                    return

            # bullish execution (elif as in source)
            elif s.bullish_fvg_confirmed and s.lowest_sweep_point is not None and self._bias_allows("buy"):
                entry = s.fvg_top
                sl = s.lowest_sweep_point - BUFFER
                if self._emit(dt, "buy", entry, sl, s.pdh, "london_bullish"):
                    s.traded_london = True

        # Keep tracking London sweep state 11:00-13:30 (wick-based sweeps)
        if time(11, 0) <= current_time < time(13, 30):
            if s.london_low is None or last_price < s.london_low:
                s.london_low = last_price
            if s.london_high is None or last_price > s.london_high:
                s.london_high = last_price
            if self.high[i] > s.pdh:
                s.swept_high = True
                if s.highest_sweep_point is None or self.high[i] > s.highest_sweep_point:
                    s.highest_sweep_point = self.high[i]
            if self.low[i] < s.pdl:
                s.swept_low = True
                if s.lowest_sweep_point is None or self.low[i] < s.lowest_sweep_point:
                    s.lowest_sweep_point = self.low[i]

        # NY reset at 13:30
        if current_time == time(13, 30):
            s.mss_swing_low = None
            s.mss_swing_high = None
            s.bearish_fvg_confirmed = False
            s.bullish_fvg_confirmed = False
            s.fvg_top = None
            s.fvg_bottom = None

        # pre-NY range 05:00-13:30
        if time(5, 0) <= current_time < time(13, 30):
            if s.pre_ny_low is None or last_price < s.pre_ny_low:
                s.pre_ny_low = last_price
            if s.pre_ny_high is None or last_price > s.pre_ny_high:
                s.pre_ny_high = last_price

        # ── NY 13:30-16:00 ────────────────────────────────────────────────────
        if time(13, 30) <= current_time <= time(16, 0) and not s.traded_ny:
            if s.pre_ny_low is None or s.pre_ny_high is None:
                return

            london_remained_in_range = (
                s.london_high is not None and s.london_low is not None
                and s.london_high <= s.pdh and s.london_low >= s.pdl
                and not s.swept_high and not s.swept_low
            )

            # SCENARIO A: continuation
            if s.swept_high or s.swept_low:
                if s.swept_high:
                    if s.highest_sweep_point is None:
                        return
                    range_dist = s.highest_sweep_point - s.pre_ny_low
                    if range_dist <= 0:
                        return
                    ote_62 = s.pre_ny_high - range_dist * 0.62
                    ote_79 = s.pre_ny_high - range_dist * 0.79
                    if ote_79 <= last_price <= ote_62:
                        s.ny_ote_hit_bearish = True
                    else:
                        return
                    if s.ny_ote_hit_bearish and s.mss_swing_low is None:
                        lows = self.hist(i, 20)["low"].values
                        for k in range(len(lows) - 2, 0, -1):
                            if lows[k] < lows[k - 1] and lows[k] < lows[k + 1]:
                                s.mss_swing_low = float(lows[k])
                                break
                    if s.mss_swing_low and last_price < s.mss_swing_low and self._bias_allows("sell"):
                        entry = s.mss_swing_low
                        sl = s.highest_sweep_point + BUFFER
                        if self._emit(dt, "sell", entry, sl, s.pre_ny_low, "ny_continuation_bearish"):
                            s.traded_ny = True

                elif s.swept_low:
                    if s.lowest_sweep_point is None:
                        return
                    range_dist = s.pre_ny_high - s.lowest_sweep_point
                    if range_dist <= 0:
                        return
                    ote_62 = s.pre_ny_low + range_dist * 0.62
                    ote_79 = s.pre_ny_low + range_dist * 0.79
                    if ote_62 <= last_price <= ote_79:
                        s.ny_ote_hit_bullish = True
                    if s.ny_ote_hit_bullish and s.mss_swing_high is None:
                        highs = self.hist(i, 20)["high"].values
                        for k in range(len(highs) - 2, 0, -1):
                            if highs[k] > highs[k - 1] and highs[k] > highs[k + 1]:
                                s.mss_swing_high = float(highs[k])
                                break
                    if s.mss_swing_high is None:
                        return
                    if s.mss_swing_high and last_price > s.mss_swing_high and not s.traded_ny and self._bias_allows("buy"):
                        entry = s.mss_swing_high
                        sl = s.lowest_sweep_point - BUFFER
                        if self._emit(dt, "buy", entry, sl, s.pre_ny_high, "ny_continuation_bullish"):
                            s.traded_ny = True

            # SCENARIO B: london ranged
            elif london_remained_in_range:
                if current_time >= time(13, 30) and s.ny_range_date != current_date:
                    df = self.hist(i, 600)
                    session = df.between_time("05:00", "12:59")
                    if not session.empty:
                        s.ny_range_high = float(session["high"].max())
                        s.ny_range_low = float(session["low"].min())
                        s.ny_range_date = current_date
                    if s.ny_range_high is None or s.ny_range_low is None:
                        return

                if self.high[i] > s.ny_range_high:
                    s.ny_sweep_high = True
                    s.sweep_peak = max(s.sweep_peak if s.sweep_peak else 0, self.high[i])
                elif self.low[i] < s.ny_range_low:
                    s.ny_sweep_low = True
                    s.sweep_trough = min(s.sweep_trough if s.sweep_trough else float("inf"), self.low[i])

                if s.ny_sweep_high and last_price < s.ny_range_high and not s.traded_ny:
                    lows = self.hist(i, 20)["low"].values
                    for k in range(len(lows) - 2, 0, -1):
                        if lows[k] < lows[k - 1] and lows[k] < lows[k + 1]:
                            s.mss_swing_low = float(lows[k])
                            break
                    if s.mss_swing_low is None:
                        return
                    if s.mss_swing_low and last_price < s.mss_swing_low and not s.bearish_fvg_confirmed:
                        df = self.hist(i, 5)
                        if len(df) < 3:
                            return
                        c1 = float(df.iloc[-3]["low"])
                        c2 = float(df.iloc[-1]["high"])
                        if c1 > c2:
                            s.fvg_top = c1
                            s.fvg_bottom = c2
                            s.bearish_fvg_confirmed = True
                            s.bullish_fvg_confirmed = False
                        else:
                            return
                    if s.bearish_fvg_confirmed and self._bias_allows("sell"):
                        entry = s.mss_swing_low
                        sl = s.sweep_peak + BUFFER
                        if self._emit(dt, "sell", entry, sl, s.ny_range_low, "ny_range_bearish"):
                            s.traded_ny = True

                elif s.ny_sweep_low and last_price > s.ny_range_low and not s.traded_ny:
                    highs = self.hist(i, 20)["high"].values
                    for k in range(len(highs) - 2, 0, -1):
                        if highs[k] > highs[k - 1] and highs[k] > highs[k + 1]:
                            s.mss_swing_high = float(highs[k])
                            break
                    if s.mss_swing_high and last_price > s.mss_swing_high:
                        df = self.hist(i, 5)
                        if df is not None and not df.empty and len(df) >= 3:
                            c1 = float(df.iloc[-3]["high"])
                            c2 = float(df.iloc[-1]["low"])
                            if c2 > c1:
                                s.fvg_top = c2
                                s.fvg_bottom = c1
                                s.bullish_fvg_confirmed = True
                                s.bearish_fvg_confirmed = False
                            else:
                                return
                        if s.bullish_fvg_confirmed and self._bias_allows("buy"):
                            entry = s.mss_swing_high
                            sl = s.sweep_trough - BUFFER
                            if self._emit(dt, "buy", entry, sl, s.ny_range_high, "ny_range_bullish"):
                                s.traded_ny = True

    # ── Resolve each limit signal against future price ────────────────────────
    def resolve(self):
        pos = {ts: k for k, ts in enumerate(self.idx)}
        for sig in self.signals:
            i0 = pos[sig.dt]
            day = sig.dt.date()
            # 1) find fill: price touches entry before end of signal day
            fill_i = None
            for j in range(i0 + 1, self.n):
                if self.idx[j].date() != day:
                    break
                if self.low[j] <= sig.entry <= self.high[j]:
                    fill_i = j
                    break
            if fill_i is None:
                sig.outcome = "unfilled"
                continue
            sig.filled = True
            sig.fill_dt = self.idx[fill_i]
            # 2) race SL vs TP from fill bar onward
            end = min(self.n, fill_i + MAX_HOLD_MIN)
            for j in range(fill_i, end):
                hi, lo = self.high[j], self.low[j]
                if sig.direction == "buy":
                    hit_sl = lo <= sig.sl
                    hit_tp = hi >= sig.tp
                else:
                    hit_sl = hi >= sig.sl
                    hit_tp = lo <= sig.tp
                if hit_sl and hit_tp:
                    sig.outcome, sig.pnl = "loss", -RISK   # conservative
                    break
                if hit_sl:
                    sig.outcome, sig.pnl = "loss", -RISK
                    break
                if hit_tp:
                    sig.outcome, sig.pnl = "win", RISK * sig.rr
                    break
            else:
                sig.outcome = "open"


# ── Reporting ─────────────────────────────────────────────────────────────────
def report(signals, pair="EUR_USD"):
    total = len(signals)
    filled = [s for s in signals if s.filled]
    wins = [s for s in filled if s.outcome == "win"]
    losses = [s for s in filled if s.outcome == "loss"]
    opens = [s for s in filled if s.outcome == "open"]
    resolved = wins + losses
    net = sum(s.pnl for s in filled)
    wr = (len(wins) / len(resolved) * 100) if resolved else 0.0
    avg_rr = (sum(s.rr for s in resolved) / len(resolved)) if resolved else 0.0

    print("=" * 68)
    print(" ICT MODEL BACKTEST — {} 1m (Oanda) — target=opposing liquidity, min RR {:.1f}, ${:.0f}/trade".format(pair.replace("_", "/"), RR_RATIO, RISK))
    print("=" * 68)
    print(f" Signals generated      : {total}")
    print(f" Signals filled (limit) : {len(filled)}  ({len(filled)/total*100:.1f}% fill rate)" if total else " no signals")
    print(f" Unfilled (discarded)   : {total - len(filled)}")
    print(f" Resolved (win/loss)    : {len(resolved)}   |  still open: {len(opens)}")
    print("-" * 68)
    print(f" Wins                   : {len(wins)}")
    print(f" Losses                 : {len(losses)}")
    print(f" Win rate (resolved)    : {wr:.1f}%   (avg RR={avg_rr:.2f}; breakeven win% = {100/(1+avg_rr):.1f}%)" if resolved else " Win rate: n/a")
    print(f" Expectancy / trade     : ${ (net/len(resolved)) if resolved else 0:.2f}")
    print(f" Net P&L                : ${net:,.0f}")
    print("=" * 68)

    # by scenario
    print("\n By scenario (resolved trades):")
    scns = {}
    for s in resolved:
        scns.setdefault(s.scenario, []).append(s)
    for name, lst in sorted(scns.items()):
        w = sum(1 for x in lst if x.outcome == "win")
        print(f"   {name:26s} n={len(lst):3d}  win%={w/len(lst)*100:5.1f}  pnl=${sum(x.pnl for x in lst):>8,.0f}")

    # by year
    print("\n By year (resolved trades):")
    yrs = {}
    for s in resolved:
        yrs.setdefault(s.dt.year, []).append(s)
    for y, lst in sorted(yrs.items()):
        w = sum(1 for x in lst if x.outcome == "win")
        print(f"   {y}  n={len(lst):3d}  win%={w/len(lst)*100:5.1f}  pnl=${sum(x.pnl for x in lst):>8,.0f}")

    # equity curve stats (max drawdown over chronological resolved trades)
    eq = 0.0
    peak = 0.0
    maxdd = 0.0
    curve = []
    for s in sorted(resolved, key=lambda x: x.fill_dt):
        eq += s.pnl
        peak = max(peak, eq)
        maxdd = min(maxdd, eq - peak)
        curve.append((s.fill_dt, eq))
    print(f"\n Max drawdown (closed-trade equity): ${maxdd:,.0f}")
    if resolved:
        print(f" Final equity (cumulative)         : ${eq:,.0f}")

    # Transaction-cost sensitivity. position_size(units) = RISK / |entry-sl|.
    # Round-trip cost in $ = spread(price) * units. EURUSD: 1 pip = 0.0001.
    print("\n Cost sensitivity (round-trip spread applied to every filled trade):")
    for pips in (0.0, 0.5, 1.0, 1.5):
        spread = pips * 0.0001
        cost = 0.0
        for s in resolved:
            units = RISK / abs(s.entry - s.sl)
            cost += spread * units
        print(f"   spread {pips:>3.1f} pip -> net P&L ${net - cost:>10,.0f}   (costs ${cost:>9,.0f})")
    return curve


def main():
    years = {2018, 2019, 2020}
    pairs = ["EUR_USD", "GBP_USD"]
    for pair in pairs:
        print(f"\nLoading {pair} 1m data for {sorted(years)} ...")
        df = load_data(pair, years)
        print(f"Loaded {len(df):,} bars  {df.index[0]} -> {df.index[-1]} (UTC+1)")
        sim = Sim(df)
        signals = sim.run()
        report(signals, pair)


if __name__ == "__main__":
    main()
