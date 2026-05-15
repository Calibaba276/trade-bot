from datetime import time
import logging

import pandas as pd
from lumibot.entities import Asset
from lumibot.strategies.strategy import Strategy

from .common import calculate_quantity, _calculate_take_profit
from ..config.logger import setup_logger

logger = setup_logger(__name__)


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
        self.rr_ratio = self.parameters.get("rr_ratio", 3.0)
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

        if current_time >= time(7, 0) and self.last_range_date != dt.date():
            try:
                df = self.get_historical_prices(self.symbol, 420, "minute")
            except Exception:
                logger.warning(f" --- {current_time} Failed to fetch Historical Prices")
                return

            morning_data = df.between_time("00:00", "06:59")

            if not morning_data.empty:
                morning_high = morning_data["high"].max()
                morning_low = morning_data["low"].min()
                if pd.isna(morning_high) or pd.isna(morning_low):
                    logger.warning(f"--- {current_date} - {current_time} Morning data has invalid high/low ---")
                    return

                self.high = float(morning_high)
                self.low = float(morning_low)
                self.last_range_date = dt.date()
                logger.info(f"--- {current_date} - {current_time} From 12:00 - 6:59am: High={self.high}, Low={self.low} ---")
            else:
                logger.warning(f"--- {current_date} Market is Closed (No Data) ---")
                return

        if self.high is not None and self.low is not None and not self.traded_today:
            if time(7, 0) <= current_time < time(17, 0):
                last_price = self.get_last_price(self.symbol)
                if last_price is None:
                    return

                # --- BEARISH MSS ---
                # Step 1: Detect sweep above the high
                if last_price > self.high:
                    self.swept_high = True
                    logger.info(f"{current_time} -- Current Price has surpassed the Highest Point --")

                    # Step 2: Price reverses below high — scan recent bars for a swing low (higher low)
                    if self.swept_high and last_price < self.high and self.mss_swing_low is None:
                        bars = self.get_historical_prices(self.asset, 20, "minute")
                        df = bars.pandas_df

                        lows = df["low"].values
                        for i in range(len(lows) - 2, 0, -1):
                            curr_low = lows[i]
                            prev_low = lows[i - 1]
                            next_low = lows[i + 1]
                            if pd.isna(curr_low) or pd.isna(prev_low) or pd.isna(next_low):
                                continue

                            if curr_low < prev_low and curr_low < next_low and curr_low > self.low:
                                self.mss_swing_low = float(curr_low)
                                logger.info(f"{current_time} -- Bearish MSS: Swing Low identified at {self.mss_swing_low}")
                                break

                    # Step 3: Price breaks below the swing low — MSS confirmed, SELL
                    if self.mss_swing_low is not None and last_price < self.mss_swing_low:
                        sl = self.high + self.buffer
                        tp = _calculate_take_profit(last_price, sl, "sell", self.rr_ratio)
                        if tp is None:
                            return

                        quantity = calculate_quantity(self, self.asset, sl)

                        order = self.create_order(
                            self.asset,
                            quantity,
                            "sell",
                            take_profit_price=tp,
                            stop_loss_price=sl,
                        )
                        self.submit_order(order)

                        logger.info(f"{dt}-- SELL SIGNAL -- Price {last_price} reversed below High - {self.high}")
                        self.traded_today = True

                # --- BULLISH MSS ---
                # Step 1: Detect sweep below the low
                elif last_price < self.low:
                    self.swept_low = True
                    logger.info(f"{current_time} -- Current Price has surpassed the Lowest Point --")

                # Step 2: Price reverses above low — scan recent bars for a swing high (lower high)
                if self.swept_low and last_price > self.low and self.mss_swing_high is None:
                    bars = self.get_historical_prices(self.asset, 20, "minute")
                    df = bars.pandas_df

                    highs = df["high"].values
                    for i in range(len(highs) - 2, 0, -1):
                        curr_high = highs[i]
                        prev_high = highs[i - 1]
                        next_high = highs[i + 1]
                        if pd.isna(curr_high) or pd.isna(prev_high) or pd.isna(next_high):
                            continue

                        if curr_high > prev_high and curr_high > next_high and curr_high < self.high:
                            self.mss_swing_high = float(curr_high)
                            logger.info(f"{current_time} -- Bullish MSS: Swing High identified at {self.mss_swing_high}")
                            break

                    # Step 3: Price breaks above the swing high — MSS confirmed, BUY
                    if self.mss_swing_high is not None and last_price > self.mss_swing_high:
                        sl = self.low - self.buffer
                        tp = _calculate_take_profit(last_price, sl, "buy", self.rr_ratio)
                        if tp is None:
                            return

                        quantity = calculate_quantity(self, self.asset, sl)

                        order = self.create_order(
                            self.asset,
                            quantity,
                            "buy",
                            take_profit_price=tp,
                            stop_loss_price=sl,
                        )
                        self.submit_order(order)

                        logger.info(f"{dt}-- BUY SIGNAL -- Price {last_price} reversed above Low - {self.low}")
                        self.traded_today = True

