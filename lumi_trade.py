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
        
        # ✅ BREAKEVEN & DRAWDOWN MANAGEMENT
        manage_breakeven_and_drawdown(self)

        # Check if drawdown halted trading
        if is_daily_drawdown_halted(self, current_date):
            if current_time.minute == 0:
                self.log_message("[DRAWDOWN] Daily drawdown cap reached. Trading halted.")
            return

        if current_time >= time(7, 0) and self.last_range_date != dt.date():
            try:
                df = self.get_historical_prices(self.asset, 420, "minute")
            except Exception:
                self.log_message(f" --- {current_time} Failed to fetch historical prices --- ")
                return

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
                    df = self.get_historical_prices(self.asset, 20, "minute")
                    lows = df["low"].values
                    for i in range(len(lows) - 2, 0, -1):
                        if lows[i] < lows[i - 1] and lows[i] < lows[i + 1] and lows[i] > self.low:
                            self.mss_swing_low = float(lows[i])
                            self.log_message(f"{current_time} -- Bearish MSS: Swing Low identified at {self.mss_swing_low}")
                            break

                # Step 3: Price breaks below the swing low — MSS confirmed, SELL
                if self.mss_swing_low and last_price < self.mss_swing_low:

                    self.stop_loss_distance = self.mss_swing_low + self.buffer
                    quantity = calculate_quantity(self, self.asset, self.stop_loss_distance)

                    self.log_message(f"{current_time} -- SELL (Bearish MSS) -- Price {last_price} broke below swing low {self.mss_swing_low}")
                    order = self.create_order(
                        self.symbol, quantity, "sell",
                        order_class = "stop_limit",
                        secondary_limit_price = self.low,
                        secondary_stop_price = self.mss_swing_low + self.buffer
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
                    df = self.get_historical_prices(self.asset, 20, "minute")
                    highs = df["high"].values
                    for i in range(len(highs) - 2, 0, -1):
                        if highs[i] > highs[i - 1] and highs[i] > highs[i + 1] and highs[i] < self.high:
                            self.mss_swing_high = float(highs[i])
                            self.log_message(f"{current_time} -- Bullish MSS: Swing High identified at {self.mss_swing_high}")
                            break

                # Step 3: Price breaks above the swing high — MSS confirmed, BUY
                if self.mss_swing_high and last_price > self.mss_swing_high:

                    self.stop_loss_distance = self.mss_swing_high - self.buffer
                    quantity = calculate_quantity(self, self.asset, self.stop_loss_distance)

                    self.log_message(f"{current_time} -- BUY (Bullish MSS) -- Price {last_price} broke above swing high {self.mss_swing_high}")
                    order = self.create_order(
                        self.symbol, quantity, "buy",
                        order_class = "bracket",
                        secondary_limit_price = self.high,
                        secondary_stop_price = self.mss_swing_high - self.buffer
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

        self.traded_today = False
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
        self.active_take_profit = None
        self.active_stop_loss = None
        self.order_side = None

    def before_market_opens(self):
        self.traded_today = False
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
        self.active_take_profit = None
        self.active_stop_loss = None
        self.order_side = None

    def on_trading_iteration(self):
        dt = self.get_datetime()
        current_time = dt.time()
        current_date = dt.date()

        # ✅ BREAKEVEN & DRAWDOWN MANAGEMENT
        manage_breakeven_and_drawdown(self)

        # Check if drawdown halted trading
        if is_daily_drawdown_halted(self, current_date):
            if current_time.minute == 0:
                self.log_message("[DRAWDOWN] Daily drawdown cap reached. Trading halted.")
            return
        
        # After 9 AM, capture the 6:00–9:00 AM session high/low as PDH/PDL
        if current_time >= time(9, 0) and self.last_range_date != current_date:
            try:
                df = self.get_historical_prices(self.asset, 200, "minute")
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

        if self.pdh and self.pdl and not self.traded_today:
            if time(9, 0) <= current_time < time(17, 0):
                last_price = self.get_last_price(self.asset)

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
                    df = self.get_historical_prices(self.asset, 20, "minute")
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
                    df = self.get_historical_prices(self.asset, 5, "minute")

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
                        self.active_take_profit = tp
                        self.active_stop_loss = sl
                        self.order_side = "sell"
                        self.traded_today = True
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
                    df = self.get_historical_prices(self.asset, 20, "minute")
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
                    df = self.get_historical_prices(self.asset, 5, "minute")

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
                        self.active_take_profit = tp
                        self.active_stop_loss = sl
                        self.order_side = "buy"
                        self.traded_today = True
                        self.log_message(f"{current_time} -- [BUY ORDER PLACED] Price: {entry_price} | SL: {sl} | TP: {tp} | Qty: {quantity}")
                    else:
                        self.log_message(f"{current_time} -- [BULLISH TRADE SKIPPED] Risk: {risk:.5f}, R:R: {rr:.2f} (min 3.0), skipping")
                        return

    def on_filled_order(self, position, order, price, quantity, multiplier):
        """Log when take profit or stop loss is hit for ICTModel orders.

        In a Lumibot bracket order the TP child is a limit order and the SL
        child is a stop order.  Both have the opposite side to the entry, so
        we use (order_type + opposite-side) to distinguish TP from SL without
        relying on order IDs.
        """
        if self.active_take_profit is None and self.active_stop_loss is None:
            return

        # getattr guards handle any Lumibot version differences in attribute names
        order_type = getattr(order, "order_type", None)
        order_side = getattr(order, "side", None)

        if order_type is None or order_side is None:
            return

        # Exit orders have the opposite side to the entry
        is_exit = (
            (self.order_side == "sell" and order_side == "buy") or
            (self.order_side == "buy" and order_side == "sell")
        )

        if not is_exit:
            return

        # Bracket TP child → limit order; SL child → stop order
        if order_type in ("limit", "stop_limit"):
            self.log_message(
                f"[TAKE PROFIT HIT] {self.symbol} closed at {price:.5f} "
                f"| TP was: {self.active_take_profit:.5f} | SL was: {self.active_stop_loss:.5f}"
            )
        elif order_type in ("stop", "stop_market"):
            self.log_message(
                f"[STOP LOSS HIT] {self.symbol} closed at {price:.5f} "
                f"| SL was: {self.active_stop_loss:.5f} | TP was: {self.active_take_profit:.5f}"
            )

        self.active_take_profit = None
        self.active_stop_loss = None
        self.order_side = None

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
        
        # ✅ BREAKEVEN & DRAWDOWN MANAGEMENT
        manage_breakeven_and_drawdown(self)

        # Check if drawdown halted trading
        if is_daily_drawdown_halted(self, current_date):
            if dt.minute == 0:
                self.log_message("[DRAWDOWN] Daily drawdown cap reached. Trading halted.")
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


def manage_breakeven_and_drawdown(self):
    """
    Iterate over all open positions and move the stop loss to breakeven
    once the position has reached rr_ratio times the initial risk.

    Breakeven level includes a small commission buffer:
      - long  → entry_price * 1.0005
      - short → entry_price * 0.9995
    """
    open_positions = self.get_positions()
    if not open_positions:
        return

    if not hasattr(self, "entry_prices") or self.entry_prices is None:
        self.entry_prices = {}

    for position in open_positions:
        symbol = position.symbol
        current_price = self.get_last_price(symbol)
        if current_price is None:
            continue

        # Seed entry price from the fill price when not yet recorded
        if symbol not in self.entry_prices:
            self.entry_prices[symbol] = position.avg_fill_price

        entry_price = self.entry_prices[symbol]

        if position.side == "long":
            pnl = current_price - entry_price
            max_risk = abs(entry_price - position.stop_price) if position.stop_price else 0
            if max_risk > 0 and pnl >= (max_risk * self.rr_ratio):
                breakeven_sl = entry_price * 1.0005
                update_stop_loss(self, position, breakeven_sl)
                self.log_message(
                    f"[BREAKEVEN] LONG {symbol}: Moved SL to breakeven {breakeven_sl:.5f}"
                )

        elif position.side == "short":
            pnl = entry_price - current_price
            max_risk = abs(position.stop_price - entry_price) if position.stop_price else 0
            if max_risk > 0 and pnl >= (max_risk * self.rr_ratio):
                breakeven_sl = entry_price * 0.9995
                update_stop_loss(self, position, breakeven_sl)
                self.log_message(
                    f"[BREAKEVEN] SHORT {symbol}: Moved SL to breakeven {breakeven_sl:.5f}"
                )


def update_stop_loss(self, position, new_stop_price):
    """Cancel the existing stop order for position and place a new one at new_stop_price."""
    symbol = position.symbol
    side = "sell" if position.side == "long" else "buy"
    try:
        for order in self.get_orders():
            if order.asset.symbol == symbol and order.status == "open":
                if order.order_type == "stop" or (
                    hasattr(order, "stop_price") and order.stop_price is not None
                ):
                    self.cancel_order(order)

        stop_order = self.create_order(
            symbol,
            position.quantity,
            side,
            order_type="stop",
            stop_price=new_stop_price,
        )
        self.submit_order(stop_order)
    except Exception as e:
        self.log_message(f"[ERROR] Failed to update SL for {symbol}: {e}")


def is_daily_drawdown_halted(self, current_date):
    """
    Return True when the portfolio has lost more than max_daily_drawdown_pct
    of its value since the start of current_date, halting further trading for that day.
    """
    if self.last_trade_date != current_date:
        self.last_trade_date = current_date
        self.daily_equity_start = self.get_portfolio_value()
        return False

    if self.daily_equity_start is None:
        self.daily_equity_start = self.get_portfolio_value()
        return False

    current_equity = self.get_portfolio_value()
    max_loss = self.daily_equity_start * self.max_daily_drawdown_pct

    if current_equity <= (self.daily_equity_start - max_loss):
        return True

    return False
