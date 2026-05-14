from datetime import time

from lumibot.entities import Asset
from lumibot.strategies.strategy import Strategy

from .common import _manage_risk_controls
from backend.services.verdict import build_verdict, save_verdict
from backend.services.publisher import publish_verdict

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

        if _manage_risk_controls(self, current_date, current_time):
            return

        # After 9 AM, capture the 6:00–9:00 AM session high/low as PDH/PDL
        if current_time >= time(9, 0) and self.last_range_date != current_date:
            try:
                df = self.get_historical_prices(self.asset, 200, "minute")
            except Exception:
                logger.warning(f" --- {current_time} Failed to fetch Historical Prices ---")
                return

            morning_data = df.between_time("06:00", "08:59")

            if not morning_data.empty:
                self.pdh = float(morning_data["high"].max())
                self.pdl = float(morning_data["low"].min())
                self.last_range_date = current_date
                logger.info(f"--- {current_date} - {current_time} From 6:00 - 8:59am: High={self.pdh}, Low={self.pdl} ---")
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

                # BEARISH MSS
                # Step 1: Detect sweep above the high
                if last_price > self.pdh:
                    self.swept_high = True

                    if self.highest_sweep_point is None or last_price > self.highest_sweep_point:
                        self.highest_sweep_point = last_price

                    logger.info(f" --- {current_time} - [BEARISH BIAS] -- Current Price has Surpassed the Highest Point ---")

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
                    else:
                        # If no FVG is formed, ICT traders usually wait for a secondary break
                        logger.warning("Price broke swing low but no displacement (FVG) found. Skipping entry.")
                        return

                # Trade Execution (BEARISH)
                if self.bearish_fvg_confirmed and self.highest_sweep_point is not None:
                    entry_price = self.fvg_bottom
                    sl = self.highest_sweep_point + self.buffer
                    tp = self.london_low if self.london_low else self.pdl

                    risk = sl - entry_price
                    reward = entry_price - tp
                    rr = reward / risk if risk > 0 else 0

                    if risk > 0 and rr >= self.rr_ratio:
                        quantity = round(self.risk_amount / (risk * 100000), 2)

                        verdict = build_verdict(
                            symbol=self.asset.symbol, direction="sell", entry=entry_price, sl=sl, tp=tp, risk=risk, rr=rr, scenario="london_bearish"
                        )
                        try:
                            save_verdict(verdict)
                            publish_verdict(verdict)
                        except Exception as e:
                            logger.error(f" --- [SIGNAL ERROR]: {e} --- ")
                            return

                        self.traded_london = True
                        logger.info(f" --- {current_time} [SELL ORDER] Price: {entry_price} | SL: {sl} | TP: {tp} | Qty: {quantity} ---")
                    else:
                        logger.warning(
                            f" --- {current_time} [BEARISH TRADE SKIPPED] Risk: {risk:.5f}, "
                            f"R:R: {rr:.2f} (min {self.rr_ratio:.2f}), skipping ---"
                        )
                        return

                # -- BULLISH --

                # BULLISH MSS
                # Step 1: Detect sweep below the low
                elif last_price < self.pdl:
                    self.swept_low = True

                    if self.lowest_sweep_point is None or last_price < self.lowest_sweep_point:
                        self.lowest_sweep_point = last_price

                    logger.info(f" --- {current_time} [BULLISH BIAS] Current Price has Surpassed the Lowest Point ---")

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
                    else:
                        # If no FVG is formed, ICT traders usually wait for a secondary break
                        logger.warning(f" --- {current_time} [FVG NOT FOUND] Price broke swing high but no displacement (FVG) found. Skipping entry. ---")
                        return

                # Trade Execution (BULLISH)
                elif self.bullish_fvg_confirmed and self.lowest_sweep_point is not None:
                    entry_price = self.fvg_top
                    sl = self.lowest_sweep_point - self.buffer
                    tp = self.london_high if self.london_high else self.pdh

                    risk = entry_price - sl
                    reward = tp - entry_price
                    rr = reward / risk if risk > 0 else 0

                    if risk > 0 and rr >= self.rr_ratio:
                        quantity = round(self.risk_amount / (risk * 100000), 2)


                        verdict = build_verdict(
                            symbol=self.asset.symbol, direction="buy", entry=entry_price, sl=sl, tp=tp, risk=risk, rr=rr, scenario="london_bullish"
                        )
                        try:
                            save_verdict(verdict)
                            publish_verdict(verdict)
                        except Exception as e:
                            logger.error(f" --- [SIGNAL ERROR]: {e} --- ")
                            return

                        self.traded_london = True

                        logger.info(f" --- {current_time} [BUY ORDER] Price: {entry_price} | SL: {sl} | TP: {tp} | Qty: {quantity} ---")
                    else:
                        logger.warning(
                            f" --- {current_time} [BULLISH TRADE SKIPPED] Risk: {risk:.5f}, "
                            f"R:R: {rr:.2f} (min {self.rr_ratio:.2f}), skipping ---"
                        )
                        return

            # Keep tracking London sweep state until NY open so Scenario A/B uses complete data.
            if time(11, 0) <= current_time < time(13, 30):
                if self.london_low is None or last_price < self.london_low:
                    self.london_low = last_price
                    logger.info(f" --- LONDON LOW: {self.london_low} [LONDON REMAINED IN RANGE] --- ")
                if self.london_high is None or last_price > self.london_high:
                    self.london_high = last_price
                    logger.info(f" --- LONDON HIGH: {self.london_high} [LONDON REMAINED IN RANGE] --- ")

                if last_price > self.pdh:
                    self.swept_high = True
                    if self.highest_sweep_point is None or last_price > self.highest_sweep_point:
                        self.highest_sweep_point = last_price
                        logger.info(f" --- HIGHEST SWEEP POINT: {self.highest_sweep_point} [LIQUIDITY SWEPT DURING LONDON] ")

                if last_price < self.pdl:
                    self.swept_low = True
                    if self.lowest_sweep_point is None or last_price < self.lowest_sweep_point:
                        self.lowest_sweep_point = last_price
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
                                    break

                        # Entry on MSS confirmation
                        if self.mss_swing_low and last_price < self.mss_swing_low:
                            entry_price = self.mss_swing_low
                            sl = self.highest_sweep_point + self.buffer
                            tp = self.pre_ny_low if self.pre_ny_low else self.pdl

                            risk = sl - entry_price
                            reward = entry_price - tp
                            rr = reward / risk if risk > 0 else 0

                            if risk > 0 and rr >= self.rr_ratio:
                                quantity = round(self.risk_amount / (risk * 100000), 2)

                                verdict = build_verdict(
                                    symbol=self.asset.symbol, direction="sell", entry=entry_price, sl=sl, tp=tp, risk=risk, rr=rr, scenario="ny_continuation_bearish"
                                )
                                try:
                                    save_verdict(verdict)
                                    publish_verdict(verdict)
                                except Exception as e:
                                    logger.error(f" --- [SIGNAL ERROR]: {e} --- ")
                                    return

                                self.traded_ny = True

                                logger.info(f"{current_time} --- [SELL ORDER - NY CONTINUATION] Price: {entry_price} | SL: {sl} | TP: {tp} | Qty: {quantity} --- ")
                            else:
                                logger.warning(
                                    f"{current_time} --- [BEARISH NY CONTINUATION TRADE SKIPPED] "
                                    f"Risk: {risk:.5f}, R:R: {rr:.2f} (min {self.rr_ratio:.2f}), skipping --- "
                                )
                                return
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
                                    break

                        if self.mss_swing_high is None:
                            logger.warning(f"{current_time} -- [STEP 2 NOT COMPLETE - BULLISH NY] Price entered OTE but no valid swing high found, skipping")
                            return

                        # Entry on MSS confirmation
                        if self.mss_swing_high and last_price > self.mss_swing_high and not self.traded_ny:
                            entry_price = self.mss_swing_high
                            sl = self.lowest_sweep_point - self.buffer
                            tp = self.pre_ny_high if self.pre_ny_high else self.pdh

                            risk = entry_price - sl
                            reward = tp - entry_price
                            rr = reward / risk if risk > 0 else 0

                            if risk > 0 and rr >= self.rr_ratio:
                                quantity = round(self.risk_amount / (risk * 100000), 2)

                                order = self.create_order(
                                    self.asset,
                                    quantity,
                                    "buy",
                                    take_profit_price=tp,
                                    stop_loss_price=sl,
                                )
                                self.submit_order(order)

                                verdict = build_verdict(
                                    symbol=self.asset.symbol, direction="buy", entry=entry_price, sl=sl, tp=tp, risk=risk, rr=rr, scenario="ny_continuation_bullish"
                                )
                                try:
                                    save_verdict(verdict)
                                    publish_verdict(verdict)
                                except Exception as e:
                                    logger.error(f" --- [SIGNAL ERROR]: {e} --- ")
                                    return
                                
                                self.traded_ny = True

                                logger.info(f"{current_time} --- [BUY ORDER - NY CONTINUATION] Price: {entry_price} | SL: {sl} | TP: {tp} | Qty: {quantity} ---")
                            else:
                                logger.warning(
                                    f"{current_time} --- [BULLISH NY CONTINUATION TRADE SKIPPED] "
                                    f"Risk: {risk:.5f}, R:R: {rr:.2f} (min {self.rr_ratio:.2f}), skipping ---"
                                )
                                return
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

                    # Wait for sweep of the absolute 06:00-14:00 range high or low
                    if last_price > self.ny_range_high:
                        self.ny_sweep_high = True
                        self.sweep_peak = max(self.sweep_peak if self.sweep_peak else 0, last_price)
                    elif last_price < self.ny_range_low:
                        self.ny_sweep_low = True
                        self.sweep_trough = min(self.sweep_trough if self.sweep_trough else float("inf"), last_price)

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
                            else:
                                # If no FVG is formed, ICT traders usually wait for a secondary break
                                logger.warning("Price broke swing low but no displacement (FVG) found. Skipping entry.")
                                return

                        if self.bearish_fvg_confirmed:
                            entry_price = self.mss_swing_low
                            sl = self.sweep_peak + self.buffer
                            tp = self.ny_range_low

                            risk = sl - entry_price
                            reward = entry_price - tp
                            rr = reward / risk if risk > 0 else 0

                            # Manage Trade: Ensure minimum R:R of 1:3
                            if risk > 0 and rr >= self.rr_ratio:
                                verdict = build_verdict(
                                    symbol=self.asset.symbol, direction="sell", entry=entry_price, sl=sl, tp=tp, risk=risk, rr=rr, scenario="ny_continuation_bearish"
                                )
                                try:
                                    save_verdict(verdict)
                                    publish_verdict(verdict)
                                except Exception as e:
                                    logger.error(f" --- [SIGNAL ERROR]: {e} --- ")
                                    return

                                self.traded_ny = True
                                logger.info(f"{current_time} -- [SELL ORDER - SCENARIO B] Price: {entry_price} | RR: {rr:.2f}")
                            else:
                                logger.warning(
                                    f"{current_time} -- [BEARISH TRADE SKIPPED] Risk: {risk:.5f}, "
                                    f"R:R: {rr:.2f} (min {self.rr_ratio:.2f}), skipping"
                                )
                                return

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
                                else:
                                    # If no FVG is formed, ICT traders usually wait for a secondary break
                                    logger.warning("Price broke swing low but no displacement (FVG) found. Skipping entry.")
                                    return
                            if self.bullish_fvg_confirmed:
                                entry_price = self.mss_swing_high
                                sl = self.sweep_trough - self.buffer  # SL below OB/Sweep Low
                                tp = self.ny_range_high  # Target opposite side of range

                                risk = entry_price - sl
                                reward = tp - entry_price
                                rr = reward / risk if risk > 0 else 0

                                # Manage Trade: Ensure minimum R:R of 1:3
                                if risk > 0 and rr >= self.rr_ratio:
                                    verdict = build_verdict(
                                    symbol=self.asset.symbol, direction="buy", entry=entry_price, sl=sl, tp=tp, risk=risk, rr=rr, scenario="ny_continuation_bullish"
                                    )
                                    try:
                                        save_verdict(verdict)
                                        publish_verdict(verdict)
                                    except Exception as e:
                                        logger.error(f" --- [SIGNAL ERROR]: {e} --- ")
                                        return

                                    self.traded_ny = True

                                    logger.info(f"{current_time} --- [BUY ORDER - SCENARIO B] Price: {entry_price} | RR: {rr:.2f} --- ")
                                else:
                                    logger.warning(
                                        f"{current_time} --- [BULLISH TRADE SKIPPED] Risk: {risk:.5f}, "
                                        f"R:R: {rr:.2f} (min {self.rr_ratio:.2f}), skipping --- "
                                    )
                                    return
        if current_time >= time(16, 0):
            logger.info(f" --- {current_date} - Market is closed for the day --- ")
