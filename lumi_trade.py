import math
import json
import pandas as pd
from datetime import time
import pytz
from lumibot.strategies.strategy import Strategy
from lumibot.entities import Asset

from fetch_trends import FetchTrends

from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient

VAULT_URL = "https://calibabasecret.vault.azure.net/"
credentials = DefaultAzureCredential()
client = SecretClient(VAULT_URL, credentials)

def get_azure_secret(name):
    """Helper to pull secrets from Azure"""
    try:
        return client.get_secret(name).value
    except Exception as e:
        print(f"Error fetching {name}: {e}")
        return None

NEWS_API_KEY = get_azure_secret("NEWS-API-KEY")
GEMINI_API_KEY = get_azure_secret("GEMINI-API-KEY")


class LiquiditySweep(Strategy):
    """
    Liquidity Sweep Strategy - Market Structure Shift (MSS) Based

    ⏰ TIME ZONE: ALL TIMES ARE IN NIGERIAN TIME (UTC+1)
    - When you see timestamps in logs: they are in NGT, not UTC
    - Asian Session: 01:00-09:00 NGT (00:00-08:00 UTC)
    - All time checks use NGT
    """
    def initialize(self):
        self.symbol = self.parameters.get("symbol")
        self.sleeptime = "1M"
        self.set_market("24/7")
        self.high = None
        self.low = None
        self.traded_today = False
        self.last_range_date = None
        self.swept_high = False
        self.swept_low = False
        self.buffer = 0.0005
        self.mss_swing_low = None
        self.mss_swing_high = None
        self.risk_amount = self.parameters.get("risk_amount", 25)
        self.stop_loss_distance = None
        self.asset = Asset(symbol=self.symbol, asset_type="forex")
        
        # Breakeven & Drawdown Protection
        self.entry_prices = {}
        self.rr_ratio = self.parameters.get("rr_ratio", 2)
        self.max_daily_drawdown_pct = self.parameters.get("max_daily_drawdown_pct", 0.02)
        self.daily_equity_start = None
        self.last_trade_date = None

    def before_market_opens(self):
        self.high = None
        self.low = None
        self.traded_today = False
        self.swept_high = False
        self.swept_low = False
        self.mss_swing_low = None
        self.mss_swing_high = None
        self.stop_loss_distance = None
        self.entry_prices = {}

    def on_trading_iteration(self):
        dt = self.get_datetime()
        current_time = dt.time()
        current_date = dt.date()

        # if _manage_risk_controls(self, current_date, current_time):
        #     return

        if current_time >= time(7, 0) and self.last_range_date != dt.date():
            try:
                df = self.get_historical_prices(self.asset, 420, "minute")
            except Exception:
                self.log_message(f" --- {current_time} Failed to fetch historical prices --- ")
                return

            df.index = pd.to_datetime(df.index)
            
            morning_data = df.between_time("00:00", "06:59")

            if not morning_data.empty:
                self.high = morning_data["high"].max()
                self.low = morning_data["low"].min()
                self.last_range_date = dt.date()
                self.log_message(f"--- {dt.date()} - {current_time} From 12:00 - 6:59am: High={self.high}, Low={self.low} ---")
            else:
                self.log_message(f"--- {dt.date()} - {current_time} Market is Closed (No Data) ---")

        if self.high and self.low and not self.traded_today:
            # Time check: 07:00-17:00 NGT (Nigerian Time, UTC+1)
            if time(7, 0) <= current_time < time(17, 0):
                last_price = self.get_last_price(self.symbol)

                # --- BEARISH MSS ---
                # Step 1: Detect sweep above the high
                if last_price > self.high:
                    self.swept_high = True
                    self.log_message(f"{current_time} -- Current Price has surpassed the Highest Point --")

                # Step 2: Price reverses below high — scan recent bars for a swing low (higher low)
                if self.swept_high and last_price < self.high and self.mss_swing_low is None:
                    df = _as_price_dataframe(self.get_historical_prices(self.asset, 20, "minute"))
                    lows = df["low"].values
                    for i in range(len(lows) - 2, 0, -1):
                        if lows[i] < lows[i - 1] and lows[i] < lows[i + 1] and lows[i] > self.low:
                            self.mss_swing_low = float(lows[i])
                            self.log_message(f"{current_time} -- Bearish MSS: Swing Low identified at {self.mss_swing_low}")
                            break

                # Step 3: Price breaks below the swing low — MSS confirmed, SELL
                if self.mss_swing_low and last_price < self.mss_swing_low:

                    # ICT rule: SL goes above the HIGH that was swept (opposite end sweep)
                    sl = self.high + self.buffer
                    # ICT rule: TP targets the opposite end of the range (session low)
                    tp = self.low
                    entry = last_price

                    risk   = sl - entry
                    reward = entry - tp

                    if risk <= 0 or reward / risk < 3.0:
                        rr_display = f"{reward/risk:.2f}" if risk > 0 else "N/A"
                        self.log_message(
                            f"{current_time} -- [BEARISH SKIPPED] R:R {rr_display} < 3.0 "
                            f"(risk={risk:.5f}, reward={reward:.5f})"
                        )
                    else:
                        quantity = calculate_quantity(self, self.asset, sl)

                        self.log_message(
                            f"{current_time} -- SELL (Bearish MSS) -- Price {entry} broke below "
                            f"swing low {self.mss_swing_low} | SL: {sl} | TP: {tp} | R:R {reward/risk:.2f}"
                        )
                        order = self.create_order(
                            self.symbol, quantity, "sell",
                            order_class="bracket",
                            secondary_limit_price=tp,
                            secondary_stop_price=sl,
                        )
                        self.submit_order(order)
                        self.traded_today = True

                # --- BULLISH MSS ---
                # Step 1: Detect sweep below the low
                elif last_price < self.low:
                    self.swept_low = True
                    self.log_message(f"{current_time} -- Current Price has surpassed the Lowest Point --")

                # Step 2: Price reverses above low — scan recent bars for a swing high (lower high)
                if self.swept_low and last_price > self.low and self.mss_swing_high is None:
                    df = _as_price_dataframe(self.get_historical_prices(self.asset, 20, "minute"))
                    highs = df["high"].values
                    for i in range(len(highs) - 2, 0, -1):
                        if highs[i] > highs[i - 1] and highs[i] > highs[i + 1] and highs[i] < self.high:
                            self.mss_swing_high = float(highs[i])
                            self.log_message(f"{current_time} -- Bullish MSS: Swing High identified at {self.mss_swing_high}")
                            break

                # Step 3: Price breaks above the swing high — MSS confirmed, BUY
                if self.mss_swing_high and last_price > self.mss_swing_high:

                    # ICT rule: SL goes below the LOW that was swept (opposite end sweep)
                    sl = self.low - self.buffer
                    # ICT rule: TP targets the opposite end of the range (session high)
                    tp = self.high
                    entry = last_price

                    risk   = entry - sl
                    reward = tp - entry

                    if risk <= 0 or reward / risk < 3.0:
                        rr_display = f"{reward/risk:.2f}" if risk > 0 else "N/A"
                        self.log_message(
                            f"{current_time} -- [BULLISH SKIPPED] R:R {rr_display} < 3.0 "
                            f"(risk={risk:.5f}, reward={reward:.5f})"
                        )
                    else:
                        quantity = calculate_quantity(self, self.asset, sl)

                        self.log_message(
                            f"{current_time} -- BUY (Bullish MSS) -- Price {entry} broke above "
                            f"swing high {self.mss_swing_high} | SL: {sl} | TP: {tp} | R:R {reward/risk:.2f}"
                        )
                        order = self.create_order(
                            self.symbol, quantity, "buy",
                            order_class="bracket",
                            secondary_limit_price=tp,
                            secondary_stop_price=sl,
                        )
                        self.submit_order(order)
                        self.traded_today = True

class ICTModel(Strategy):
    """
    ICT Model Coded as Observed... HOPE IT WORKS!!!
    """

    def initialize(self):
        self.symbol = self.parameters.get("symbol")
        self.sleeptime = "1M"
        self.set_market("24/5")
        self.risk_amount = self.parameters.get("risk_amount")
        self.asset = Asset(symbol=self.symbol, asset_type="forex")
        self.buffer = 0.0002

        self.traded_london = False
        self.traded_ny = False
        self.last_range_date = None
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
        self.max_daily_drawdown_pct = self.parameters.get("max_daily_drawdown_pct", 0.02)
        self.daily_equity_start = None
        self.last_trade_date = None

    def before_market_opens(self):
        self.traded_london = False
        self.traded_ny = False
        self.last_range_date = None
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
                df = _as_price_dataframe(self.get_historical_prices(self.asset, 200, "minute"))
            except Exception:
                self.log_message(f" --- {current_time} Failed to fetch Historical Prices ---")
                return

            if df is not None and not df.empty:
                session_data = df.between_time("06:00", "08:59")
                if not session_data.empty:
                    self.pdh = float(session_data["high"].max())
                    self.pdl = float(session_data["low"].min())
                    self.last_range_date = current_date
                    self.log_message(f"[{self.symbol}] 6AM-9AM Levels Set - PDH: {self.pdh} PDL: {self.pdl}")
                else:
                    self.log_message(f"[{self.symbol}] No data in 6AM-9AM window")
            else:
                self.log_message(f"Error fetching minute data for {self.symbol}")

        if self.pdh and self.pdl:
            last_price = self.get_last_price(self.asset)

            if time(9, 0) <= current_time < time(17, 0) and not self.traded_london:

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

                    self.log_message(f"{current_time} - [BEARISH BIAS] -- Current Price has Surpassed the Highest Point --")

                # Step 2: Price reverses below high — scan for swing low
                if self.swept_high and last_price < self.pdh and self.mss_swing_low is None:
                    df = _as_price_dataframe(self.get_historical_prices(self.asset, 20, "minute"))
                    if df is None or df.empty:
                        self.log_message(f"{current_time} -- [ERROR] Bearish swing scan: DataFrame is None or empty")
                        return
                    if "low" not in df.columns:
                        self.log_message(f"{current_time} -- [ERROR] Bearish swing scan: missing 'low' column")
                        return
                    lows = df["low"].values
                    for i in range(len(lows) - 2, 0, -1):
                        if lows[i] < lows[i - 1] and lows[i] < lows[i + 1] and lows[i] > self.pdl:
                            self.mss_swing_low = float(lows[i])
                            self.log_message(f"{current_time} -- Bearish MSS: Swing Low identified at {self.mss_swing_low}")
                            break
                    if self.mss_swing_low is None:
                        self.log_message(f"{current_time} -- [STEP 2 NOT COMPLETE - BEARISH] Price reversed below PDH but no valid swing low found, skipping")
                        return

                # Step 3: Price breaks below the swing low — MSS Confirmed
                if self.mss_swing_low and last_price < self.mss_swing_low and not self.bearish_fvg_confirmed:
                    # Getting candles to check for a bearish FVG
                    df = _as_price_dataframe(self.get_historical_prices(self.asset, 5, "minute"))
                    if df is None or df.empty:
                        self.log_message(f"{current_time} -- [ERROR] Bearish FVG check: DataFrame is None or empty")
                        return
                    if len(df) < 3:
                        self.log_message(f"{current_time} -- [ERROR] Bearish FVG check: insufficient rows: got {len(df)}, need 3")
                        return
                    if "low" not in df.columns or "high" not in df.columns:
                        self.log_message(f"{current_time} -- [ERROR] Bearish FVG check: missing required columns (low/high)")
                        return

                    # The Low and High Candles
                    c1 = float(df.iloc[-3]["low"])
                    c2 = float(df.iloc[-1]["high"])

                    if c1 > c2:
                        self.fvg_top = c1
                        self.fvg_bottom = c2

                        self.bearish_fvg_confirmed = True
                        self.bullish_fvg_confirmed = False
                        self.log_message(f"--- MSS & FVG CONFIRMED ---")
                        self.log_message(f"Entry Zone: {self.fvg_bottom} - {self.fvg_top}")
                    else:
                        # If no FVG is formed, ICT traders usually wait for a secondary break
                        self.log_message("Price broke swing low but no displacement (FVG) found. Skipping entry.")
                        return

                # Trade Execution (BEARISH)
                if self.bearish_fvg_confirmed and self.highest_sweep_point is not None:
                    entry_price = self.fvg_bottom
                    sl = self.highest_sweep_point + self.buffer
                    tp = self.london_low if self.london_low else self.pdl

                    risk = sl - entry_price
                    reward = entry_price - tp
                    rr = reward / risk if risk > 0 else 0

                    if risk > 0 and rr >= 3.0:
                        quantity = round(self.risk_amount / (risk * 100000), 2)

                        order = self.create_order(
                            self.asset, quantity, "sell",
                            order_class="bracket",
                            secondary_limit_price=tp,
                            secondary_stop_price=sl
                        )
                        self.submit_order(order)

                        self.traded_london = True
                        self.log_message(f"{current_time} -- [SELL ORDER PLACED] Price: {entry_price} | SL: {sl} | TP: {tp} | Qty: {quantity}")
                    else:
                        self.log_message(f"{current_time} -- [BEARISH TRADE SKIPPED] Risk: {risk:.5f}, R:R: {rr:.2f} (min 3.0), skipping")
                        return

                # -- BULLISH --

                # BULLISH MSS
                # Step 1: Detect sweep below the low
                elif last_price < self.pdl:
                    self.swept_low = True

                    if self.lowest_sweep_point is None or last_price < self.lowest_sweep_point:
                        self.lowest_sweep_point = last_price

                    self.log_message(f"{current_time} - [BULLISH BIAS] -- Current Price has Surpassed the Lowest Point --")

                # Step 2: Price reverses above low — scan for swing high
                if self.swept_low and last_price > self.pdl and self.mss_swing_high is None:
                    df = _as_price_dataframe(self.get_historical_prices(self.asset, 20, "minute"))
                    if df is None or df.empty:
                        self.log_message(f"{current_time} -- [ERROR] Bullish swing scan: DataFrame is None or empty")
                        return
                    if "high" not in df.columns:
                        self.log_message(f"{current_time} -- [ERROR] Bullish swing scan: missing 'high' column")
                        return
                    highs = df["high"].values
                    for i in range(len(highs) - 2, 0, -1):
                        if highs[i] > highs[i - 1] and highs[i] > highs[i + 1] and highs[i] < self.pdh:
                            self.mss_swing_high = float(highs[i])
                            self.log_message(f"{current_time} -- Bullish MSS: Swing High identified at {self.mss_swing_high}")
                            break
                    if self.mss_swing_high is None:
                        self.log_message(f"{current_time} -- [STEP 2 NOT COMPLETE - BULLISH] Price reversed above PDL but no valid swing high found, skipping")
                        return

                # Step 3: Price breaks above the swing high — MSS Confirmed
                if self.mss_swing_high and last_price > self.mss_swing_high and not self.bullish_fvg_confirmed:
                    # Getting candles to check for a bullish FVG
                    df = _as_price_dataframe(self.get_historical_prices(self.asset, 5, "minute"))
                    if df is None or df.empty:
                        self.log_message(f"{current_time} -- [ERROR] Bullish FVG check: DataFrame is None or empty")
                        return
                    if len(df) < 3:
                        self.log_message(f"{current_time} -- [ERROR] Bullish FVG check: insufficient rows: got {len(df)}, need 3")
                        return
                    if "high" not in df.columns or "low" not in df.columns:
                        self.log_message(f"{current_time} -- [ERROR] Bullish FVG check: missing required columns (high/low)")
                        return

                    # The Low and High Candles
                    c1 = float(df.iloc[-3]["high"])
                    c2 = float(df.iloc[-1]["low"])

                    if c1 < c2:
                        self.fvg_top = c2
                        self.fvg_bottom = c1

                        self.bullish_fvg_confirmed = True
                        self.bearish_fvg_confirmed = False
                        self.log_message(f"--- MSS & FVG CONFIRMED ---")
                        self.log_message(f"Entry Zone: {self.fvg_bottom} - {self.fvg_top}")
                    else:
                        # If no FVG is formed, ICT traders usually wait for a secondary break
                        self.log_message("Price broke swing high but no displacement (FVG) found. Skipping entry.")
                        return

                # Trade Execution (BULLISH)
                elif self.bullish_fvg_confirmed and self.lowest_sweep_point is not None:
                    entry_price = self.fvg_top
                    sl = self.lowest_sweep_point - self.buffer
                    tp = self.london_high if self.london_high else self.pdh

                    risk = entry_price - sl
                    reward = tp - entry_price
                    rr = reward / risk if risk > 0 else 0

                    if risk > 0 and rr >= 3.0:
                        quantity = round(self.risk_amount / (risk * 100000), 2)

                        order = self.create_order(
                            self.asset, quantity, "buy",
                            order_class="bracket",
                            secondary_limit_price=tp,
                            secondary_stop_price=sl
                        )
                        self.submit_order(order)
                        self.traded_london = True

                        self.log_message(f"{current_time} -- [BUY ORDER PLACED] Price: {entry_price} | SL: {sl} | TP: {tp} | Qty: {quantity}")
                    else:
                        self.log_message(f"{current_time} -- [BULLISH TRADE SKIPPED] Risk: {risk:.5f}, R:R: {rr:.2f} (min 3.0), skipping")
                        return
                
            # --- NEW YORK SESSION RESET ---
            # At the start of NY session, clear the technical markers from London
            if current_time == time(8, 30):
                self.mss_swing_low = None
                self.mss_swing_high = None
                self.bearish_fvg_confirmed = False
                self.bullish_fvg_confirmed = False
                self.fvg_top = None
                self.fvg_bottom = None
                self.log_message("--- NY Session Started: Technical Markers Reset ---")

            # SCENARIO A: NEW YORK CONTINUATION
            # Track the Pre-NY range - SCENARIO A
            if time(3, 0) <= current_time <= time(8, 30):
                if self.pre_ny_low is None or last_price < self.pre_ny_low:
                    self.pre_ny_low = last_price
                if self.pre_ny_high is None or last_price > self.pre_ny_high:
                    self.pre_ny_high = last_price

            # Track the highest and lowest point between 12 to 8AM EST - SCENARIO B
            if time(5, 0) <= current_time <= time(13,0):
                if self.ny_range_high is None or last_price > self.ny_range_high:
                    self.ny_range_high = last_price
                if self.ny_range_low is None or last_price < self.ny_range_low:
                    self.ny_range_low = last_price

            # NY SESSION EXECUTION (8:30 - 11:00 AM)
            if time(8, 30) <= current_time <= time(11, 0) and not self.traded_ny:
                if self.pre_ny_low is None or self.pre_ny_high is None:
                    self.log_message("NY Continuation Zone (Range Dist, ote_62, OTE_79): NOT FOUND")
                    return
                
                # SCENARIO AI
                if self.swept_high or self.swept_low:
                    
                    # BEARISH CONTINUATION LOGIC
                    if self.swept_high:
                        if self.highest_sweep_point is None:
                            self.log_message("NY Continuation Zone (Range Dist, ote_62, OTE_79): NOT FOUND")
                            return

                        # Calculate the OTE Levels
                        range_dist = self.highest_sweep_point - self.pre_ny_low
                        if range_dist <= 0:
                            self.log_message("NY Continuation Zone (Range Dist, ote_62, OTE_79): NOT FOUND")
                            return

                        ote_62 = self.pre_ny_high - (range_dist * 0.62)
                        ote_79 = self.pre_ny_high - (range_dist * 0.79)

                        self.log_message(f"NY Continuation Zone (OTE): {round(ote_79, 5)} - {round(ote_62, 5)}")

                        # Wait for price to reach the OTE Zone
                        if ote_79 <= last_price <= ote_62:
                            self.ny_ote_hit_bearish = True
                            self.log_message(f"{current_time} -- NY Scenario A Bearish: Price entered Premium OTE Zone ({round(ote_62, 5)} - {round(ote_79, 5)}) --")
                        else:
                            self.log_message(f"{current_time} -- NY Scenario A Bearish: Price never enter Premium OTE Zone ({round(ote_62, 5)} - {round(ote_79, 5)}) --")
                            return

                        # Confirm MSS in Lower Timeframe (M1)
                        if self.ny_ote_hit_bearish and self.mss_swing_low is None:
                            df = _as_price_dataframe(self.get_historical_prices(self.asset, 20, "minute"))
                            lows = df['low'].values
                            for i in range(len(lows) - 2, 0, -1):
                                if lows[i] < lows[i-1] and lows[i] < lows[i+1]:
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

                            if risk > 0 and rr >= 3.0:
                                quantity = round(self.risk_amount / (risk * 100000), 2)

                                order = self.create_order(
                                    self.asset, quantity, "sell",
                                    order_class="bracket",
                                    secondary_limit_price=tp,
                                    secondary_stop_price=sl
                                )
                                self.submit_order(order)
                                self.traded_ny = True

                                self.log_message(f"{current_time} -- [SELL ORDER PLACED - NY CONTINUATION] Price: {entry_price} | SL: {sl} | TP: {tp} | Qty: {quantity}")
                            else:
                                self.log_message(f"{current_time} -- [BEARISH NY CONTINUATION TRADE SKIPPED] Risk: {risk:.5f}, R:R: {rr:.2f} (min 3.0), skipping")
                                return
                    elif self.swept_low:
                        if self.lowest_sweep_point is None:
                            self.log_message("NY Continuation Zone (Range Dist, ote_62, OTE_79): NOT FOUND")
                            return

                        # Calculate the OTE Levels
                        range_dist = self.pre_ny_high - self.lowest_sweep_point
                        if range_dist <= 0:
                            self.log_message("NY Continuation Zone (Range Dist, ote_62, OTE_79): NOT FOUND")
                            return

                        ote_62 = self.pre_ny_low + (range_dist * 0.62)
                        ote_79 = self.pre_ny_low + (range_dist * 0.79)

                        self.log_message(f"NY Continuation Zone (OTE): {round(ote_62, 5)} - {round(ote_79, 5)}")

                        # Wait for price to reach the OTE Zone
                        if ote_62 <= last_price <= ote_79:
                            self.ny_ote_hit_bullish = True
                            self.log_message(f"{current_time} -- NY Scenario A Bullish: Price entered Premium OTE Zone ({round(ote_62, 5)} - {round(ote_79, 5)}) --")

                        # Confirm MSS in Lower Timeframe (M1)
                        if self.ny_ote_hit_bullish and self.mss_swing_high is None:
                            df = _as_price_dataframe(self.get_historical_prices(self.asset, 20, "minute"))
                            highs = df['high'].values
                            for i in range(len(highs) - 2, 0, -1):
                                if highs[i] > highs[i-1] and highs[i] > highs[i+1]:
                                    self.mss_swing_high = float(highs[i])
                                    break
                        if self.mss_swing_high is None:
                            self.log_message(f"{current_time} -- [STEP 2 NOT COMPLETE - BULLISH NY] Price entered OTE but no valid swing high found, skipping")
                            return

                        # Entry on MSS confirmation
                        if self.mss_swing_high and last_price > self.mss_swing_high and not self.traded_ny:
                            entry_price = self.mss_swing_high
                            sl = self.lowest_sweep_point - self.buffer
                            tp = self.pre_ny_high if self.pre_ny_high else self.pdh

                            risk = entry_price - sl
                            reward = tp - entry_price
                            rr = reward / risk if risk > 0 else 0

                            if risk > 0 and rr >= 3.0:
                                quantity = round(self.risk_amount / (risk * 100000), 2)

                                order = self.create_order(
                                    self.asset, quantity, "buy",
                                    order_class="bracket",
                                    secondary_limit_price=tp,
                                    secondary_stop_price=sl
                                )
                                self.submit_order(order)
                                self.traded_ny = True

                                self.log_message(f"{current_time} -- [BUY ORDER PLACED - NY CONTINUATION] Price: {entry_price} | SL: {sl} | TP: {tp} | Qty: {quantity}")
                            else:
                                self.log_message(f"{current_time} -- [BULLISH NY CONTINUATION TRADE SKIPPED] Risk: {risk:.5f}, R:R: {rr:.2f} (min 3.0), skipping")
                                return
                # SCENARIO B: LONDON REMAINED IN A RANGE      
                else:
                    if self.ny_range_high is None or self.ny_range_low is None:
                        self.log_message("NY Scenario B Range: NOT FOUND")
                        return

                    # Wait for sweep of the 12-8 EST range high or low
                    if last_price > self.ny_range_high:
                        self.ny_sweep_high = True
                        self.sweep_peak = max(self.sweep_peak if self.sweep_peak else 0, last_price)
                    elif last_price < self.ny_range_low:
                        self.ny_sweep_low = True
                        self.sweep_trough = min(self.sweep_trough if self.sweep_trough else float('inf'), last_price)

                    # BEARISH
                    # Observe MSS and Identify FVG (BULLISH)
                    if self.ny_sweep_high and last_price < self.ny_range_high and not self.traded_ny:
                        df = _as_price_dataframe(self.get_historical_prices(self.asset, 20, "minute"))
                        if df is None or df.empty:
                            self.log_message(f"{current_time} -- [ERROR] Bearish swing scan: DataFrame is None or empty")
                            return
                        if "low" not in df.columns:
                            self.log_message(f"{current_time} -- [ERROR] Bearish swing scan: missing 'low' column")
                            return
                        lows = df["low"].values
                        for i in range(len(lows) - 2, 0, -1):
                            if lows[i] < lows[i - 1] and lows[i] < lows[i + 1]:
                                self.mss_swing_low = float(lows[i])
                                self.log_message(f"{current_time} -- Bearish MSS: Swing Low identified at {self.mss_swing_low}")
                                break
                        if self.mss_swing_low is None:
                            self.log_message(f"{current_time} -- [STEP 2 NOT COMPLETE - BEARISH] Price reversed below PDH but no valid swing low found, skipping")
                            return

                        if self.mss_swing_low and last_price < self.mss_swing_low and not self.bearish_fvg_confirmed:
                            # Getting candles to check for a bearish FVG
                            df = _as_price_dataframe(self.get_historical_prices(self.asset, 5, "minute"))
                            if df is None or df.empty:
                                self.log_message(f"{current_time} -- [ERROR] Bearish FVG check: DataFrame is None or empty")
                                return
                            if len(df) < 3:
                                self.log_message(f"{current_time} -- [ERROR] Bearish FVG check: insufficient rows: got {len(df)}, need 3")
                                return
                            if "low" not in df.columns or "high" not in df.columns:
                                self.log_message(f"{current_time} -- [ERROR] Bearish FVG check: missing required columns (low/high)")
                                return

                            # The Low and High Candles
                            c1 = float(df.iloc[-3]["low"])
                            c2 = float(df.iloc[-1]["high"])

                            if c1 > c2:
                                self.fvg_top = c1
                                self.fvg_bottom = c2

                                self.bearish_fvg_confirmed = True
                                self.bullish_fvg_confirmed = False
                                self.log_message(f"--- MSS & FVG CONFIRMED ---")
                                self.log_message(f"Entry Zone: {self.fvg_bottom} - {self.fvg_top}")
                            else:
                                # If no FVG is formed, ICT traders usually wait for a secondary break
                                self.log_message("Price broke swing low but no displacement (FVG) found. Skipping entry.")
                                return
                        if self.bearish_fvg_confirmed:
                            entry_price = self.mss_swing_low
                            sl = self.sweep_peak + self.buffer
                            tp = self.ny_range_low

                            risk = sl - entry_price
                            reward = entry_price - tp
                            rr = reward / risk if risk > 0 else 0

                            # Manage Trade: Ensure minimum R:R of 1:3
                            if risk > 0 and rr >= 3.0:
                                quantity = round(self.risk_amount / (risk * 100000), 2)
                                order = self.create_order(
                                    self.asset, quantity, "sell",
                                    order_class="bracket",
                                    secondary_limit_price=tp,
                                    secondary_stop_price=sl
                                )
                                self.submit_order(order)
                                self.traded_ny = True
                                self.log_message(f"{current_time} -- [SELL ORDER PLACED - SCENARIO B] Price: {entry_price} | RR: {rr:.2f}")
                            else:
                                self.log_message(f"{current_time} -- [BEARISH TRADE SKIPPED] Risk: {risk:.5f}, R:R: {rr:.2f} (min 3.0), skipping")
                                return

                    # --- 2. OBSERVE MSS & 3. IDENTIFY PD ARRAY (BULLISH REVERSAL) ---
                    elif self.ny_sweep_low and last_price > self.ny_range_low and not self.traded_ny:
                        # Confirm market structure shifts (MSS) in lower timeframes
                        df = _as_price_dataframe(self.get_historical_prices(self.asset, 20, "minute"))
                        if df is None or df.empty:
                            self.log_message(f"{current_time} -- [ERROR] Bullish swing scan: DataFrame is None or empty")
                            return
                        if "high" not in df.columns:
                            self.log_message(f"{current_time} -- [ERROR] Bullish swing scan: missing 'high' column")
                            return
                        highs = df['high'].values
                        for i in range(len(highs) - 2, 0, -1):
                            if highs[i] > highs[i-1] and highs[i] > highs[i+1]:
                                self.mss_swing_high = float(highs[i])
                                break

                        # If MSS occurs, Locate PD Array (FVG)
                        if self.mss_swing_high and last_price > self.mss_swing_high:
                            df = _as_price_dataframe(self.get_historical_prices(self.asset, 5, "minute"))
                            if df is not None and not df.empty and len(df) >= 3:
                                c1 = float(df.iloc[-3]["high"])
                                c2 = float(df.iloc[-1]["low"])

                                if c2 > c1: # Bullish FVG Found
                                    self.fvg_top = c2
                                    self.fvg_bottom = c1
    
                                    self.bearish_fvg_confirmed = False
                                    self.bullish_fvg_confirmed = True
                                    self.log_message(f"--- MSS & FVG CONFIRMED ---")
                                    self.log_message(f"Entry Zone: {self.fvg_bottom} - {self.fvg_top}")
                                else:
                                    # If no FVG is formed, ICT traders usually wait for a secondary break
                                    self.log_message("Price broke swing low but no displacement (FVG) found. Skipping entry.")
                                    return
                            if self.bullish_fvg_confirmed:
                                entry_price = self.mss_swing_high
                                sl = self.sweep_trough - self.buffer # SL below OB/Sweep Low
                                tp = self.ny_range_high # Target opposite side of range

                                risk = entry_price - sl
                                reward = tp - entry_price
                                rr = reward / risk if risk > 0 else 0

                                # Manage Trade: Ensure minimum R:R of 1:3
                                if risk > 0 and rr >= 3.0:
                                    quantity = round(self.risk_amount / (risk * 100000), 2)
                                    order = self.create_order(
                                        self.asset, quantity, "buy",
                                        order_class="bracket",
                                        secondary_limit_price=tp,
                                        secondary_stop_price=sl
                                    )
                                    self.submit_order(order)
                                    self.traded_ny = True
                                    self.log_message(f"{current_time} -- [BUY ORDER PLACED - SCENARIO B] Price: {entry_price} | RR: {rr:.2f}")
                                else:
                                    self.log_message(f"{current_time} -- [BULLISH TRADE SKIPPED] Risk: {risk:.5f}, R:R: {rr:.2f} (min 3.0), skipping")
                                    return
                        
class TrendStrategy(Strategy):
    """
    Sentiment-based trading strategy using AI analysis.
    Uses 1:2 risk-reward ratio with proper stop loss and take profit.
    """
    def initialize(self):
        self.result = FetchTrends(NEWS_API_KEY, GEMINI_API_KEY)
        self.sleeptime = "5M"
        self.set_market("24/5")
        self.risk_amount = self.parameters.get("risk_amount", 25)
        self.rr_ratio = self.parameters.get("rr_ratio", 2)
        self.stop_loss_percent = self.parameters.get("stop_loss_percent", 0.02)
        
        # Breakeven & Drawdown Protection
        self.entry_prices = {}  # Track entry price per ticker
        self.max_daily_drawdown_pct = self.parameters.get("max_daily_drawdown_pct", 0.02)
        self.daily_equity_start = None
        self.last_trade_date = None
    
    def on_trading_iteration(self):
        dt = self.get_datetime()
        current_date = dt.date()

        if _manage_risk_controls(self, current_date, dt.time()):
            return
        
        payload = json.loads(self.result.get_ai_response())
        signals = payload.get("signals", [])
        tickers_scores = {}
        self.order_sent = False

        if not signals:
            return

        for signal in signals:
            ticker = signal["ticker"]
            score = signal["sentiment_score"]
            reason = signal["reason"]

            if ticker not in tickers_scores:
                tickers_scores[ticker] = []
                tickers_scores[ticker].append(score)
                tickers_scores[ticker].append(reason)

        for ticker, scores in tickers_scores.items():
            avg_score = sum(scores) / len(scores)
            asset = Asset(symbol=ticker, asset_type="stock")

            if avg_score > 0.7:
                pos = self.get_position(asset)
                if pos is None:
                    price = self.get_last_price(asset)
                    
                    if price is None or price == 0:
                        self.log_message(f"[ERROR] Cannot fetch price for {ticker}")
                        continue
                    
                    stop_loss_price = price * (1 - self.stop_loss_percent)
                    take_profit_price = price + (price - stop_loss_price) * self.rr_ratio
                    quantity = calculate_quantity(self, asset, stop_loss_price)

                    if quantity <= 0:
                        self.log_message(f"Skipping {ticker}. Price is too high for ${self.risk_amount} trade limit.")
                        continue
                    
                    order = self.create_order(
                        asset, quantity, "buy",
                        order_class="bracket",
                        secondary_limit_price=take_profit_price,
                        secondary_stop_price=stop_loss_price
                    )
                    self.submit_order(order)
                    self.entry_prices[ticker] = price
                    self.log_message(f"[ENTRY] BUY {ticker} @ {price:.2f} | SL: {stop_loss_price:.2f} | TP: {take_profit_price:.2f} | Score: {avg_score:.2f}")
                    self.order_sent = True

            elif avg_score <= -0.5:
                pos = self.get_position(asset)
                if pos is not None:
                    price = self.get_last_price(asset)
                    
                    if price is None or price == 0:
                        self.log_message(f"[ERROR] Cannot fetch price for {ticker}")
                        continue
                    
                    stop_loss_price = price * (1 + self.stop_loss_percent)
                    take_profit_price = price - (stop_loss_price - price) * self.rr_ratio
                    
                    order = self.create_order(
                        asset, pos.quantity, "sell",
                        order_class="stop_limit",
                        secondary_limit_price=take_profit_price,
                        secondary_stop_price=stop_loss_price
                    )
                    self.submit_order(order)
                    if ticker in self.entry_prices:
                        del self.entry_prices[ticker]
                    self.log_message(f"[EXIT] SELL {ticker} @ {price:.2f} | SL: {stop_loss_price:.2f} | TP: {take_profit_price:.2f} | Score: {avg_score:.2f}")
                    self.order_sent = True

        if not self.order_sent:
            self.log_message("No Orders Made... Unto the Next Iteration")

def calculate_quantity(self, asset, stop_loss=None):
    """Quantity Calculator for Stocks and Forex"""

    # Simple logic: Use 5% of available cash per trade
    price = self.get_last_price(asset)

    if price is None or price == 0:
        self.log_message(f"Warning: Price for {asset.symbol} is 0 or None. Cannot calculate $25 trade.")
        return 0

    if stop_loss is not None:
        sl_distance = abs(price - stop_loss)
        if sl_distance == 0:
            return 0

        raw_quantity = self.risk_amount / sl_distance

        if asset.asset_type == "forex":
            step = 0.01
            quantity = raw_quantity / 100000

            final_qty = round(math.floor(quantity / step) * step, 2)
        else:
            quantity = raw_quantity

            final_qty = math.floor(quantity)

    else:
        final_qty = self.risk_amount / price

    if final_qty <= 0:
        self.log_message(f"Quantity too small for {asset.symbol} with $25 Limit.")
        return 0

    return final_qty


def _as_price_dataframe(price_data):
    """Normalize historical price payloads (Bars/DataFrame) into a pandas DataFrame."""
    if price_data is None:
        return pd.DataFrame()
    if isinstance(price_data, pd.DataFrame):
        return price_data

    bars_df = getattr(price_data, "df", None)
    if isinstance(bars_df, pd.DataFrame):
        return bars_df

    try:
        return pd.DataFrame(price_data)
    except Exception:
        return pd.DataFrame()


def _is_daily_drawdown_halted(strategy, current_date):
    """Use broker drawdown guard when available, otherwise apply strategy-local fallback."""
    broker_drawdown_guard = getattr(strategy.broker, "is_daily_drawdown_halted", None)
    if callable(broker_drawdown_guard):
        return broker_drawdown_guard(strategy, current_date)

    if strategy.last_trade_date != current_date:
        strategy.last_trade_date = current_date
        strategy.daily_equity_start = strategy.get_portfolio_value()
        return False

    if strategy.daily_equity_start is None:
        strategy.daily_equity_start = strategy.get_portfolio_value()
        return False

    current_equity = strategy.get_portfolio_value()
    max_loss = strategy.daily_equity_start * strategy.max_daily_drawdown_pct
    return current_equity <= (strategy.daily_equity_start - max_loss)


def _manage_risk_controls(strategy, current_date, current_time):
    """Apply broker-specific breakeven logic when available and enforce daily drawdown cap."""
    broker_breakeven_manager = getattr(strategy.broker, "manage_breakeven_and_drawdown", None)
    if callable(broker_breakeven_manager):
        broker_breakeven_manager(strategy)

    if _is_daily_drawdown_halted(strategy, current_date):
        if current_time.minute == 0:
            strategy.log_message("[DRAWDOWN] Daily drawdown cap reached. Trading halted.")
        return True
    return False
