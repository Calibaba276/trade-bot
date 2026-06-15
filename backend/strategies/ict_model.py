from datetime import time

from lumibot.entities import Asset
from lumibot.strategies.strategy import Strategy

from .common import _calculate_take_profit, _manage_risk_controls
from backend.services.verdict import build_verdict, save_verdict, publish_verdict
from backend.services.frontend_emitter import (
    _pair,
    emit_candle,
    emit_trade_event,
    emit_candles_from_df,
)

from ..config.logger import setup_logger

logger = setup_logger(__name__)


class ICTModel(Strategy):
    """
    ICT Model Coded as Observed... HOPE IT WORKS!!!
    """

    def initialize(self):
        self.symbol = self.parameters.get("symbol")
        self.sleeptime = "1M"
        self.set_market("24/5")
        self.risk_amount = self.parameters.get("risk_amount")
        self.rr_ratio = float(self.parameters.get("rr_ratio", 3.0) or 3.0)
        self.breakeven_buffer_ticks = int(self.parameters.get("breakeven_buffer_ticks", 10) or 10)
        self.asset = Asset(symbol=self.symbol, asset_type="forex")
        self.buffer = 0.0002

        # Higher-timeframe directional bias filter. Only setups aligned with the
        # daily trend are taken (bull bias -> longs only, bear bias -> shorts only).
        self.htf_bias_period = int(self.parameters.get("htf_bias_period", 20) or 20)
        self.daily_bias = None  # "bull" | "bear" | None, recomputed each day

        self.traded_london = False
        self.traded_ny = False
        self.last_range_date = None
        self.ny_range_date = None
        self.pdh = None
        self.pdl = None
        self.swept_high = None
        self.swept_low = None
        self.mss_swing_low = None
        self.mss_swing_high = None
        self.fvg_top = None
        self.fvg_bottom = None
        self.bearish_fvg_confirmed = False
        self.bullish_fvg_confirmed = False
        self.highest_sweep_point = None
        self.lowest_sweep_point = None
        self.london_low = None
        self.london_high = None
        self.pre_ny_low = None
        self.pre_ny_high = None
        self.ny_ote_hit_bullish = None
        self.ny_ote_hit_bearish = False

        # --- SCENARIO B: RANGE VARIABLES ---
        self.session_scenario = None
        self.liquidity_high = None
        self.liquidity_low = None
        self.ny_range_high = None
        self.ny_range_low = None
        self.ny_sweep_high = False
        self.ny_sweep_low = False
        self.sweep_peak = None
        self.sweep_trough = None

        # Drawdown protection state (used by non-MT5 fallback risk controls)
        self.max_daily_drawdown_pct = float(self.parameters.get("max_daily_drawdown_pct", 0.02) or 0.02)
        self.daily_equity_start = None
        self.last_trade_date = None

        # Frontend emitter identifiers — None in backtest or when account has no user yet
        self.user_id: str | None = self.parameters.get("user_id")
        self.account_id: str | None = self.parameters.get("account_id")
        self.pair_normalized: str = _pair(self.symbol or "")

    # ──────────────────────────────────────────────────────────────────────────
    # Frontend emit helpers (all no-ops when user_id is not configured)
    # ──────────────────────────────────────────────────────────────────────────

    def _emit_bars(self, df=None) -> None:
        """Emit OHLCV candles to Supabase. When df (>=60 rows) is provided,
        resample to all 4 timeframes; otherwise fetch 1 bar for the 1m candle."""
        if not self.user_id:
            return
        try:
            if df is not None and len(df) >= 60:
                emit_candles_from_df(self.user_id, self.account_id, self.pair_normalized, df)
            else:
                bar_df = self.get_historical_prices(self.asset, 1, "minute")
                if bar_df is None or bar_df.empty:
                    return
                bar = bar_df.iloc[-1]
                bar_ms = int(bar_df.index[-1].timestamp() * 1000)
                emit_candle(
                    self.user_id, self.account_id, self.pair_normalized, "1m",
                    bar_ms,
                    float(bar["open"]), float(bar["high"]),
                    float(bar["low"]), float(bar["close"]),
                    float(bar.get("volume", 0)),
                )
        except Exception as exc:
            logger.warning(f"[BARS EMIT] {exc}")

    def _emit_mss(self, swing_price: float, direction: str) -> None:
        if not self.user_id:
            return
        emit_trade_event(
            self.user_id, self.account_id,
            self.pair_normalized, "1m",
            "pattern_detected",
            pattern="MSS",
            price=swing_price,
            high=swing_price,
            low=swing_price,
            metadata={"direction": direction},
        )

    def _emit_fvg(self) -> None:
        if not self.user_id or self.fvg_top is None or self.fvg_bottom is None:
            return
        emit_trade_event(
            self.user_id, self.account_id,
            self.pair_normalized, "1m",
            "pattern_detected",
            pattern="FVG",
            price=(self.fvg_top + self.fvg_bottom) / 2,
            high=self.fvg_top,
            low=self.fvg_bottom,
        )

    def _emit_entry(self, verdict, entry_price: float, sl: float, tp: float) -> None:
        if not self.user_id:
            return
        emit_trade_event(
            self.user_id, self.account_id,
            self.pair_normalized, "1m",
            "entry",
            price=entry_price,
            high=tp,
            low=sl,
            metadata={
                "signal_id": verdict.signal_id,
                "direction": verdict.direction,
                "scenario": verdict.scenario,
                "rr_ratio": verdict.reward_risk_ratio,
            },
        )

    # ──────────────────────────────────────────────────────────────────────────
    # ICT enhancements: HTF bias filter + wick-based liquidity sweep detection
    # ──────────────────────────────────────────────────────────────────────────

    def _compute_daily_bias(self, current_date):
        """ICT daily bias from the previous completed daily candle (draw on
        liquidity proxy): bullish if it closed in the upper half of its range
        (closing above the midpoint => buyside is the likely draw), else bearish.
        Only the side aligned with the bias is traded."""
        try:
            ddf = self.get_historical_prices(self.asset, 5, "day")
        except Exception:
            return None
        if ddf is None or ddf.empty or "close" not in ddf.columns:
            return None
        # use the last daily candle strictly before today (no look-ahead)
        try:
            prev = ddf[ddf.index.date < current_date]
        except Exception:
            prev = ddf.iloc[:-1]
        if prev is None or prev.empty:
            prev = ddf.iloc[:-1] if len(ddf) > 1 else ddf
        if prev.empty:
            return None
        row = prev.iloc[-1]
        hi, lo, close = float(row["high"]), float(row["low"]), float(row["close"])
        mid = (hi + lo) / 2.0
        return "bull" if close >= mid else "bear"

    def _bias_allows(self, direction):
        """True only when the trade direction agrees with the daily bias."""
        if self.daily_bias is None:
            return False
        return self.daily_bias == ("bull" if direction == "buy" else "bear")

    def _current_bar_hl(self):
        """High/low of the latest 1m bar — used for wick-based sweep detection so
        a liquidity grab that pierces a level and snaps back is not missed."""
        try:
            df = self.get_historical_prices(self.asset, 1, "minute")
        except Exception:
            return None, None
        if df is None or df.empty:
            return None, None
        return float(df.iloc[-1]["high"]), float(df.iloc[-1]["low"])

    def before_market_opens(self):
        self.traded_london = False
        self.traded_ny = False
        self.last_range_date = None
        self.ny_range_date = None
        self.pdh = None
        self.pdl = None
        self.swept_high = None
        self.swept_low = None
        self.mss_swing_low = None
        self.mss_swing_high = None
        self.fvg_top = None
        self.fvg_bottom = None
        self.bearish_fvg_confirmed = False
        self.bullish_fvg_confirmed = False
        self.highest_sweep_point = None
        self.lowest_sweep_point = None
        self.london_low = None
        self.london_high = None
        self.pre_ny_low = None
        self.pre_ny_high = None
        self.ny_ote_hit_bullish = None
        self.ny_ote_hit_bearish = False
        self.daily_bias = None

        # --- SCENARIO B: RANGE VARIABLES ---
        self.session_scenario = None
        self.ny_range_high = None
        self.ny_range_low = None
        self.ny_sweep_high = False
        self.ny_sweep_low = False
        self.sweep_peak = None
        self.sweep_trough = None

    def on_trading_iteration(self):
        dt = self.get_datetime()
        current_time = dt.time()
        current_date = dt.date()

        # Emit latest 1m bar to frontend on every tick
        self._emit_bars()

        if _manage_risk_controls(self, current_date, current_time):
            return

        # After 9 AM, capture the 6:00–9:00 AM session high/low as PDH/PDL
        if current_time >= time(9, 0) and self.last_range_date != current_date:
            try:
                df = self.get_historical_prices(self.asset, 200, "minute")
            except Exception:
                logger.warning(f" --- {current_time} Failed to fetch Historical Prices ---")
                return

            # Backfill all 4 timeframes from the 200-bar fetch
            self._emit_bars(df)

            morning_data = df.between_time("06:00", "08:59")

            if not morning_data.empty:
                self.pdh = float(morning_data["high"].max())
                self.pdl = float(morning_data["low"].min())
                self.last_range_date = current_date
                self.daily_bias = self._compute_daily_bias(current_date)
                logger.info(f"--- {current_date} - {current_time} From 6:00 - 8:59am: High={self.pdh}, Low={self.pdl} | Daily bias: {self.daily_bias} ---")
            else:
                logger.warning(f" --- {current_date} Market is Closed (No Data) --- ")
                return

        if self.pdh and self.pdl:
            last_price = self.get_last_price(self.asset)

            if time(9, 0) <= current_time < time(11, 0) and not self.traded_london:
                if self.london_low is None or last_price < self.london_low:
                    self.london_low = last_price
                if self.london_high is None or last_price > self.london_high:
                    self.london_high = last_price

                # -- BEARISH --

                bar_high, bar_low = self._current_bar_hl()

                # BEARISH MSS
                # Step 1: Detect sweep above the high (wick-based)
                if bar_high is not None and bar_high > self.pdh:
                    self.swept_high = True

                    if self.highest_sweep_point is None or bar_high > self.highest_sweep_point:
                        self.highest_sweep_point = bar_high

                    logger.info(f" --- {current_time} - [BEARISH BIAS] -- Price wick swept the High ---")

                # Step 2: Price reverses below high — scan for swing low
                if self.swept_high and last_price < self.pdh and self.mss_swing_low is None:
                    df = self.get_historical_prices(self.asset, 20, "minute")
                    if df is None or df.empty:
                        logger.error(f"{current_time} -- [ERROR] Bearish swing scan: DataFrame is None or empty")
                        return
                    if "low" not in df.columns:
                        logger.error(f"{current_time} -- [ERROR] Bearish swing scan: missing 'low' column")
                        return
                    lows = df["low"].values

                    for i in range(len(lows) - 2, 0, -1):
                        if lows[i] < lows[i - 1] and lows[i] < lows[i + 1] and lows[i] > self.pdl:
                            self.mss_swing_low = float(lows[i])
                            logger.info(f" --- {current_time} -- Bearish MSS: Swing Low identified at {self.mss_swing_low} ---")
                            self._emit_mss(self.mss_swing_low, "bearish")
                            break
                    if self.mss_swing_low is None:
                        logger.warning(f"{current_time} -- [STEP 2 NOT COMPLETE - BEARISH] Price reversed below PDH but no valid swing low found, skipping")
                        return

                # Step 3: Price breaks below the swing low — MSS Confirmed
                if self.mss_swing_low and last_price < self.mss_swing_low and not self.bearish_fvg_confirmed:
                    # Getting candles to check for a bearish FVG
                    df = self.get_historical_prices(self.asset, 5, "minute")
                    if df is None or df.empty:
                        logger.error(f"{current_time} -- [ERROR] Bearish FVG check: DataFrame is None or empty")
                        return
                    if len(df) < 3:
                        logger.error(f"{current_time} -- [ERROR] Bearish FVG check: insufficient rows: got {len(df)}, need 3")
                        return
                    if "low" not in df.columns or "high" not in df.columns:
                        logger.error(f"{current_time} -- [ERROR] Bearish FVG check: missing required columns (low/high)")
                        return

                    # The Low and High Candles
                    c1 = float(df.iloc[-3]["low"])
                    c2 = float(df.iloc[-1]["high"])

                    if c1 > c2:
                        self.fvg_top = c1
                        self.fvg_bottom = c2

                        self.bearish_fvg_confirmed = True
                        self.bullish_fvg_confirmed = False
                        logger.info(f"--- MSS & FVG CONFIRMED ---")
                        logger.info(f"Entry Zone: {self.fvg_bottom} - {self.fvg_top}")
                        self._emit_fvg()
                    else:
                        # If no FVG is formed, ICT traders usually wait for a secondary break
                        logger.warning("Price broke swing low but no displacement (FVG) found. Skipping entry.")
                        return

                # Trade Execution (BEARISH)
                if self.bearish_fvg_confirmed and self.highest_sweep_point is not None and self._bias_allows("sell"):
                    entry_price = self.fvg_bottom
                    sl = self.highest_sweep_point + self.buffer
                    tp = _calculate_take_profit(entry_price, sl, "sell", self.rr_ratio)
                    risk = sl - entry_price

                    if tp is None:
                        logger.warning(f" --- {current_time} [BEARISH TRADE SKIPPED] Invalid TP calculation ---")
                        return

                    verdict = build_verdict(
                        symbol=self.asset.symbol, direction="sell", entry=entry_price, sl=sl, tp=tp, risk=risk, rr=self.rr_ratio, scenario="london_bearish"
                    )
                    try:
                        payload = save_verdict(verdict)
                        publish_verdict(payload)
                        self._emit_entry(verdict, entry_price, sl, tp)
                    except Exception as e:
                        logger.error(f" --- [SIGNAL ERROR]: {e} --- ")
                        return

                    self.traded_london = True
                    logger.info(f" --- {current_time} [SELL ORDER] Price: {entry_price} | SL: {sl} | TP: {tp} | RR: {self.rr_ratio:.2f} ---")

                # -- BULLISH --

                # BULLISH MSS
                # Step 1: Detect sweep below the low (wick-based)
                elif bar_low is not None and bar_low < self.pdl:
                    self.swept_low = True

                    if self.lowest_sweep_point is None or bar_low < self.lowest_sweep_point:
                        self.lowest_sweep_point = bar_low

                    logger.info(f" --- {current_time} [BULLISH BIAS] Price wick swept the Low ---")

                # Step 2: Price reverses above low — scan for swing high
                if self.swept_low and last_price > self.pdl and self.mss_swing_high is None:
                    df = self.get_historical_prices(self.asset, 20, "minute")
                    if df is None or df.empty:
                        logger.error(f"{current_time} -- [ERROR] Bullish swing scan: DataFrame is None or empty")
                        return
                    if "high" not in df.columns:
                        logger.error(f"{current_time} -- [ERROR] Bullish swing scan: missing 'high' column")
                        return

                    highs = df["high"].values
                    for i in range(len(highs) - 2, 0, -1):
                        if highs[i] > highs[i - 1] and highs[i] > highs[i + 1] and highs[i] < self.pdh:
                            self.mss_swing_high = float(highs[i])
                            logger.info(f" --- {current_time} [BULLISH MSS] Swing High identified at {self.mss_swing_high} ---")
                            self._emit_mss(self.mss_swing_high, "bullish")
                            break
                    if self.mss_swing_high is None:
                        logger.warning(f" --- {current_time} [STEP 2 NOT COMPLETE - BULLISH] Price reversed above PDL but no valid swing high found, skipping ---")
                        return

                # Step 3: Price breaks above the swing high — MSS Confirmed
                if self.mss_swing_high and last_price > self.mss_swing_high and not self.bullish_fvg_confirmed:
                    # Getting candles to check for a bullish FVG
                    df = self.get_historical_prices(self.asset, 5, "minute")
                    if df is None or df.empty:
                        logger.error(f" --- {current_time} [ERROR] Bullish FVG check: DataFrame is None or empty ---")
                        return
                    if len(df) < 3:
                        logger.error(f" --- {current_time} [ERROR] Bullish FVG check: insufficient rows: got {len(df)}, need 3 ---")
                        return
                    if "high" not in df.columns or "low" not in df.columns:
                        logger.error(f" --- {current_time} [ERROR] Bullish FVG check: missing required columns (high/low) ---")
                        return

                    # The Low and High Candles
                    c1 = float(df.iloc[-3]["high"])
                    c2 = float(df.iloc[-1]["low"])

                    if c1 < c2:
                        self.fvg_top = c2
                        self.fvg_bottom = c1

                        self.bullish_fvg_confirmed = True
                        self.bearish_fvg_confirmed = False
                        logger.info(f" --- {current_time} [MSS & FVG CONFIRMED] ---")
                        logger.info(f"Entry Zone: {self.fvg_bottom} - {self.fvg_top}")
                        self._emit_fvg()
                    else:
                        # If no FVG is formed, ICT traders usually wait for a secondary break
                        logger.warning(f" --- {current_time} [FVG NOT FOUND] Price broke swing high but no displacement (FVG) found. Skipping entry. ---")
                        return

                # Trade Execution (BULLISH)
                elif self.bullish_fvg_confirmed and self.lowest_sweep_point is not None and self._bias_allows("buy"):
                    entry_price = self.fvg_top
                    sl = self.lowest_sweep_point - self.buffer
                    risk = entry_price - sl
                    tp = _calculate_take_profit(entry_price, sl, "buy", self.rr_ratio)
                    if tp is None:
                        logger.warning(f" --- {current_time} [BULLISH TRADE SKIPPED] Invalid TP calculation ---")
                        return

                    verdict = build_verdict(
                        symbol=self.asset.symbol, direction="buy", entry=entry_price, sl=sl, tp=tp, risk=risk, rr=self.rr_ratio, scenario="london_bullish"
                    )
                    try:
                        payload = save_verdict(verdict)
                        publish_verdict(payload)
                        self._emit_entry(verdict, entry_price, sl, tp)
                    except Exception as e:
                        logger.error(f" --- [SIGNAL ERROR]: {e} --- ")
                        return

                    self.traded_london = True
                    logger.info(f" --- {current_time} [BUY ORDER] Price: {entry_price} | SL: {sl} | TP: {tp} ---")

            # Keep tracking London sweep state until NY open so Scenario A/B uses complete data.
            if time(11, 0) <= current_time < time(13, 30):
                if self.london_low is None or last_price < self.london_low:
                    self.london_low = last_price
                    logger.info(f" --- LONDON LOW: {self.london_low} [LONDON REMAINED IN RANGE] --- ")
                if self.london_high is None or last_price > self.london_high:
                    self.london_high = last_price
                    logger.info(f" --- LONDON HIGH: {self.london_high} [LONDON REMAINED IN RANGE] --- ")

                track_high, track_low = self._current_bar_hl()
                if track_high is not None and track_high > self.pdh:
                    self.swept_high = True
                    if self.highest_sweep_point is None or track_high > self.highest_sweep_point:
                        self.highest_sweep_point = track_high
                        logger.info(f" --- HIGHEST SWEEP POINT: {self.highest_sweep_point} [LIQUIDITY SWEPT DURING LONDON] ")

                if track_low is not None and track_low < self.pdl:
                    self.swept_low = True
                    if self.lowest_sweep_point is None or track_low < self.lowest_sweep_point:
                        self.lowest_sweep_point = track_low
                        logger.info(f" --- LOWEST SWEEP POINT: {self.lowest_sweep_point} [LIQUIDITY SWEPT DURING LONDON] ")

            # --- NEW YORK SESSION RESET ---
            # At the start of NY session, clear the technical markers from London
            if current_time == time(13, 30):
                self.mss_swing_low = None
                self.mss_swing_high = None
                self.bearish_fvg_confirmed = False
                self.bullish_fvg_confirmed = False
                self.fvg_top = None
                self.fvg_bottom = None
                logger.info("--- NY Session Started: Technical Markers Reset ---")

            # Build the pre-NY range and keep it fixed once NY session starts.
            if time(5, 0) <= current_time < time(13, 30):
                if self.pre_ny_low is None or last_price < self.pre_ny_low:
                    self.pre_ny_low = last_price
                    logger.info(f" --- PRE NY LOW: {self.pre_ny_low} [LIQUIDITY SWEPT DURING LONDON]")
                if self.pre_ny_high is None or last_price > self.pre_ny_high:
                    self.pre_ny_high = last_price
                    logger.info(f" --- PRE NY HIGH: {self.pre_ny_high} [LIQUIDITY SWEPT DURING LONDON] ")

            # SCENARIO A: NEW YORK CONTINUATION
            # NY SESSION EXECUTION (13:30 - 16:00)
            if time(13, 30) <= current_time <= time(16, 0) and not self.traded_ny:
                last_price = self.get_last_price(self.asset)

                if self.pre_ny_low is None or self.pre_ny_high is None:
                    logger.warning("PRE_NY_LOW or PRE_NY_HIGH: NOT FOUND")
                    return

                london_remained_in_range = (
                    self.pdh is not None
                    and self.pdl is not None
                    and self.london_high is not None
                    and self.london_low is not None
                    and self.london_high <= self.pdh
                    and self.london_low >= self.pdl
                    and not self.swept_high
                    and not self.swept_low
                )

                # SCENARIO A
                if self.swept_high or self.swept_low:
                    # BEARISH CONTINUATION LOGIC
                    if self.swept_high:
                        if self.highest_sweep_point is None:
                            logger.warning("HIGHEST SWEEP POINT: NOT FOUND")
                            return

                        # Calculate the OTE Levels
                        range_dist = self.highest_sweep_point - self.pre_ny_low
                        if range_dist <= 0:
                            logger.warning("RANGE DISTANCE - LOW RETURNING...")
                            return

                        ote_62 = self.pre_ny_high - (range_dist * 0.62)
                        ote_79 = self.pre_ny_high - (range_dist * 0.79)

                        logger.info(f"NY Continuation Zone (OTE): {round(ote_79, 5)} - {round(ote_62, 5)}")

                        # Wait for price to reach the OTE Zone
                        if ote_79 <= last_price <= ote_62:
                            self.ny_ote_hit_bearish = True
                            logger.info(f"{current_time} -- NY Scenario A Bearish: Price entered Premium OTE Zone ({round(ote_62, 5)} - {round(ote_79, 5)}) --")
                        else:
                            logger.warning(f"{current_time} -- NY Scenario A Bearish: Price never enter Premium OTE Zone ({round(ote_62, 5)} - {round(ote_79, 5)}) --")
                            return

                        # Confirm MSS in Lower Timeframe (M1)
                        if self.ny_ote_hit_bearish and self.mss_swing_low is None:
                            df = self.get_historical_prices(self.asset, 20, "minute")
                            lows = df["low"].values

                            for i in range(len(lows) - 2, 0, -1):
                                if lows[i] < lows[i - 1] and lows[i] < lows[i + 1]:
                                    self.mss_swing_low = float(lows[i])
                                    self._emit_mss(self.mss_swing_low, "bearish")
                                    break

                        # Entry on MSS confirmation
                        if self.mss_swing_low and last_price < self.mss_swing_low and self._bias_allows("sell"):
                            entry_price = self.mss_swing_low
                            sl = self.highest_sweep_point + self.buffer
                            risk = sl - entry_price
                            tp = _calculate_take_profit(entry_price, sl, "sell", self.rr_ratio)

                            if tp is None:
                                logger.warning(f"{current_time} --- [BEARISH NY CONTINUATION TRADE SKIPPED] Invalid TP calculation --- ")
                                return

                            verdict = build_verdict(
                                symbol=self.asset.symbol, direction="sell", entry=entry_price, sl=sl, tp=tp, risk=risk, rr=self.rr_ratio, scenario="ny_continuation_bearish"
                            )
                            try:
                                payload = save_verdict(verdict)
                                publish_verdict(payload)
                                self._emit_entry(verdict, entry_price, sl, tp)
                            except Exception as e:
                                logger.error(f" --- [SIGNAL ERROR]: {e} --- ")
                                return

                            self.traded_ny = True
                            logger.info(f"{current_time} --- [SELL ORDER - NY CONTINUATION] Price: {entry_price} | SL: {sl} | TP: {tp} | RR: {self.rr_ratio:.2f} --- ")
                            
                    elif self.swept_low:
                        if self.lowest_sweep_point is None:
                            logger.warning("LOWEST SWEEP POINT: NOT FOUND")
                            return

                        # Calculate the OTE Levels
                        range_dist = self.pre_ny_high - self.lowest_sweep_point
                        if range_dist <= 0:
                            logger.warning("RANGE DISTANCE - LOW RETURNING...")
                            return

                        ote_62 = self.pre_ny_low + (range_dist * 0.62)
                        ote_79 = self.pre_ny_low + (range_dist * 0.79)

                        logger.info(f"NY Continuation Zone (OTE): {round(ote_62, 5)} - {round(ote_79, 5)}")

                        # Wait for price to reach the OTE Zone
                        if ote_62 <= last_price <= ote_79:
                            self.ny_ote_hit_bullish = True
                            logger.info(f"{current_time} -- NY Scenario A Bullish: Price entered Premium OTE Zone ({round(ote_62, 5)} - {round(ote_79, 5)}) --")

                        # Confirm MSS in Lower Timeframe (M1)
                        if self.ny_ote_hit_bullish and self.mss_swing_high is None:
                            df = self.get_historical_prices(self.asset, 20, "minute")
                            highs = df["high"].values

                            for i in range(len(highs) - 2, 0, -1):
                                if highs[i] > highs[i - 1] and highs[i] > highs[i + 1]:
                                    self.mss_swing_high = float(highs[i])
                                    self._emit_mss(self.mss_swing_high, "bullish")
                                    break

                        if self.mss_swing_high is None:
                            logger.warning(f"{current_time} -- [STEP 2 NOT COMPLETE - BULLISH NY] Price entered OTE but no valid swing high found, skipping")
                            return

                        # Entry on MSS confirmation
                        if self.mss_swing_high and last_price > self.mss_swing_high and not self.traded_ny and self._bias_allows("buy"):
                            entry_price = self.mss_swing_high
                            sl = self.lowest_sweep_point - self.buffer
                            risk = entry_price - sl
                            tp = _calculate_take_profit(entry_price, sl, "buy", self.rr_ratio)

                            if tp is None:
                                logger.warning(f"{current_time} --- [BULLISH NY CONTINUATION TRADE SKIPPED] Invalid TP calculation ---")
                                return

                            verdict = build_verdict(
                                symbol=self.asset.symbol, direction="buy", entry=entry_price, sl=sl, tp=tp, risk=risk, rr=self.rr_ratio, scenario="ny_continuation_bullish"
                            )
                            try:
                                payload = save_verdict(verdict)
                                publish_verdict(payload)
                                self._emit_entry(verdict, entry_price, sl, tp)
                            except Exception as e:
                                logger.error(f" --- [SIGNAL ERROR]: {e} --- ")
                                return

                            self.traded_ny = True
                            logger.info(f"{current_time} --- [BUY ORDER - NY CONTINUATION] Price: {entry_price} | SL: {sl} | TP: {tp} ---")
                            
                # SCENARIO B: LONDON REMAINED IN A RANGE
                elif london_remained_in_range:
                    if current_time >= time(13, 30) and self.ny_range_date != current_date:
                        try:
                            df = self.get_historical_prices(self.asset, 600, "minute")
                        except Exception as e:
                            logger.error(f"{current_time} -- [ERROR] Failed to fetch historical prices for NY Scenario B: {e}")
                            return

                        session_data = df.between_time("05:00", "12:59")

                        if not session_data.empty:
                            self.ny_range_high = float(session_data["high"].max())
                            self.ny_range_low = float(session_data["low"].min())
                            self.ny_range_date = current_date
                            logger.info(f"--- {current_date} - {current_time} From 5:00 - 12:59am: High={self.ny_range_high}, Low={self.ny_range_low} ---")

                        if self.ny_range_high is None or self.ny_range_low is None:
                            logger.warning("NY Scenario B Range: NOT FOUND")
                            return

                    # Wait for sweep of the absolute 06:00-14:00 range high or low (wick-based)
                    nb_high, nb_low = self._current_bar_hl()
                    if nb_high is not None and nb_high > self.ny_range_high:
                        self.ny_sweep_high = True
                        self.sweep_peak = max(self.sweep_peak if self.sweep_peak else 0, nb_high)
                    elif nb_low is not None and nb_low < self.ny_range_low:
                        self.ny_sweep_low = True
                        self.sweep_trough = min(self.sweep_trough if self.sweep_trough else float("inf"), nb_low)

                    # BEARISH
                    # Observe MSS and Identify FVG (BULLISH)
                    if self.ny_sweep_high and last_price < self.ny_range_high and not self.traded_ny:
                        df = self.get_historical_prices(self.asset, 20, "minute")

                        if df is None or df.empty:
                            logger.error(f"{current_time} -- [ERROR] Bearish swing scan: DataFrame is None or empty")
                            return
                        if "low" not in df.columns:
                            logger.error(f"{current_time} -- [ERROR] Bearish swing scan: missing 'low' column")
                            return
                        lows = df["low"].values

                        for i in range(len(lows) - 2, 0, -1):
                            if lows[i] < lows[i - 1] and lows[i] < lows[i + 1]:
                                self.mss_swing_low = float(lows[i])
                                logger.info(f"{current_time} -- Bearish MSS: Swing Low identified at {self.mss_swing_low}")
                                self._emit_mss(self.mss_swing_low, "bearish")
                                break
                        if self.mss_swing_low is None:
                            logger.warning(f"{current_time} -- [STEP 2 NOT COMPLETE - BEARISH] Price reversed below PDH but no valid swing low found, skipping")
                            return

                        if self.mss_swing_low and last_price < self.mss_swing_low and not self.bearish_fvg_confirmed:
                            # Getting candles to check for a bearish FVG
                            df = self.get_historical_prices(self.asset, 5, "minute")

                            if df is None or df.empty:
                                logger.error(f"{current_time} -- [ERROR] Bearish FVG check: DataFrame is None or empty")
                                return
                            if len(df) < 3:
                                logger.error(f"{current_time} -- [ERROR] Bearish FVG check: insufficient rows: got {len(df)}, need 3")
                                return
                            if "low" not in df.columns or "high" not in df.columns:
                                logger.error(f"{current_time} -- [ERROR] Bearish FVG check: missing required columns (low/high)")
                                return

                            # The Low and High Candles
                            c1 = float(df.iloc[-3]["low"])
                            c2 = float(df.iloc[-1]["high"])

                            if c1 > c2:
                                self.fvg_top = c1
                                self.fvg_bottom = c2

                                self.bearish_fvg_confirmed = True
                                self.bullish_fvg_confirmed = False
                                logger.info(f"--- MSS & FVG CONFIRMED ---")
                                logger.info(f"Entry Zone: {self.fvg_bottom} - {self.fvg_top}")
                                self._emit_fvg()
                            else:
                                # If no FVG is formed, ICT traders usually wait for a secondary break
                                logger.warning("Price broke swing low but no displacement (FVG) found. Skipping entry.")
                                return

                        if self.bearish_fvg_confirmed and self._bias_allows("sell"):
                            entry_price = self.mss_swing_low
                            sl = self.sweep_peak + self.buffer
                            risk = sl - entry_price
                            tp = _calculate_take_profit(entry_price, sl, "sell", self.rr_ratio)

                            if tp is None:
                                logger.warning(f"{current_time} -- [BEARISH TRADE SKIPPED] Invalid TP calculation")
                                return

                            verdict = build_verdict(
                                symbol=self.asset.symbol, direction="sell", entry=entry_price, sl=sl, tp=tp, risk=risk, rr=self.rr_ratio, scenario="ny_continuation_bearish"
                            )
                            try:
                                payload = save_verdict(verdict)
                                publish_verdict(payload)
                                self._emit_entry(verdict, entry_price, sl, tp)
                            except Exception as e:
                                logger.error(f" --- [SIGNAL ERROR]: {e} --- ")
                                return

                            self.traded_ny = True
                            logger.info(f"{current_time} --- [SELL ORDER - SCENARIO B] Price: {entry_price} | RR: {self.rr_ratio:.2f} ---")

                    # --- 2. OBSERVE MSS & 3. IDENTIFY PD ARRAY (BULLISH REVERSAL) ---
                    elif self.ny_sweep_low and last_price > self.ny_range_low and not self.traded_ny:
                        # Confirm market structure shifts (MSS) in lower timeframes
                        df = self.get_historical_prices(self.asset, 20, "minute")

                        if df is None or df.empty:
                            logger.error(f"{current_time} -- [ERROR] Bullish swing scan: DataFrame is None or empty")
                            return
                        if "high" not in df.columns:
                            logger.error(f"{current_time} -- [ERROR] Bullish swing scan: missing 'high' column")
                            return
                        highs = df["high"].values

                        for i in range(len(highs) - 2, 0, -1):
                            if highs[i] > highs[i - 1] and highs[i] > highs[i + 1]:
                                self.mss_swing_high = float(highs[i])
                                self._emit_mss(self.mss_swing_high, "bullish")
                                break

                        # If MSS occurs, Locate PD Array (FVG)
                        if self.mss_swing_high and last_price > self.mss_swing_high:
                            df = self.get_historical_prices(self.asset, 5, "minute")
                            if df is not None and not df.empty and len(df) >= 3:
                                c1 = float(df.iloc[-3]["high"])
                                c2 = float(df.iloc[-1]["low"])

                                if c2 > c1:  # Bullish FVG Found
                                    self.fvg_top = c2
                                    self.fvg_bottom = c1

                                    self.bearish_fvg_confirmed = False
                                    self.bullish_fvg_confirmed = True
                                    logger.info(f"--- MSS & FVG CONFIRMED ---")
                                    logger.info(f"Entry Zone: {self.fvg_bottom} - {self.fvg_top}")
                                    self._emit_fvg()
                                else:
                                    # If no FVG is formed, ICT traders usually wait for a secondary break
                                    logger.warning("Price broke swing low but no displacement (FVG) found. Skipping entry.")
                                    return
                            if self.bullish_fvg_confirmed and self._bias_allows("buy"):
                                entry_price = self.mss_swing_high
                                sl = self.sweep_trough - self.buffer  # SL below OB/Sweep Low
                                risk = entry_price - sl
                                tp = _calculate_take_profit(entry_price, sl, "buy", self.rr_ratio)

                                if tp is None:
                                    logger.warning(f"{current_time} --- [BULLISH TRADE SKIPPED] Invalid TP calculation --- ")
                                    return

                                verdict = build_verdict(
                                    symbol=self.asset.symbol, direction="buy", entry=entry_price, sl=sl, tp=tp, risk=risk, rr=self.rr_ratio, scenario="ny_continuation_bullish"
                                )
                                try:
                                    payload = save_verdict(verdict)
                                    publish_verdict(payload)
                                    self._emit_entry(verdict, entry_price, sl, tp)
                                except Exception as e:
                                    logger.error(f" --- [SIGNAL ERROR]: {e} --- ")
                                    return

                                self.traded_ny = True
                                logger.info(f"{current_time} --- [BUY ORDER - SCENARIO B] Price: {entry_price} | RR: {self.rr_ratio:.2f} --- ")
                                
        if current_time >= time(16, 0):
            logger.info(f" --- {current_date} - Market is closed for the day --- ")
