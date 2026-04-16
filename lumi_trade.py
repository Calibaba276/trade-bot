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
    
    ✅ FEATURES:
    - Breakeven protection: Moves SL to entry when reaching 1:2 RR
    - Daily drawdown cap: Halts trading if daily loss exceeds threshold
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
        self.entry_price = None
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
        self.entry_price = None

    def on_trading_iteration(self):
        dt = self.get_datetime()
        current_time = dt.time()
        current_date = dt.date()
        
        # ✅ BREAKEVEN & DRAWDOWN MANAGEMENT
        self._manage_breakeven_and_drawdown(current_date)
        
        # Check if drawdown halted trading
        if self._is_daily_drawdown_halted(current_date):
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
                        order_class = "bracket",
                        take_profit_price = self.low,
                        stop_loss_price = self.mss_swing_low + self.buffer
                    )
                    self.submit_order(order)
                    self.traded_today = True

                # --- BULLISH MSS ---
                # Step 1: Detect sweep below the low
                elif last_price < self.low:
                    self.swept_low = True
                    self.log_message(f"{current_time} -- Current Price has surpassed the Highest Point --")

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
                        take_profit_price = self.high,
                        stop_loss_price = self.mss_swing_high - self.buffer
                    )
                    self.submit_order(order)
                    self.traded_today = True
    
    def _manage_breakeven_and_drawdown(self, current_date):
        """
        Manages breakeven stops and cleanup for active positions.
        When a position reaches 1:2 RR, moves SL to entry (with commission buffer).
        """
        open_positions = self.get_positions()
        
        if not open_positions:
            return
        
        for position in open_positions:
            if position.symbol != self.symbol:
                continue
            
            current_price = self.get_last_price(self.symbol)
            if current_price is None:
                continue
            
            # Store entry price if not already stored
            if self.entry_price is None:
                self.entry_price = position.avg_fill_price
            
            # Calculate unrealized P&L and check if reached 1:2 RR
            if position.side == "long":
                pnl = current_price - self.entry_price
                max_risk = abs(self.entry_price - position.stop_price) if position.stop_price else 0
                
                if max_risk > 0 and pnl >= (max_risk * self.rr_ratio):
                    # Move SL to breakeven (with small buffer to avoid commission)
                    breakeven_sl = self.entry_price * 1.0005
                    self._update_stop_loss(position, breakeven_sl)
                    self.log_message(f"[BREAKEVEN] LONG {self.symbol}: Moved SL to breakeven {breakeven_sl:.5f}")
            
            elif position.side == "short":
                pnl = self.entry_price - current_price
                max_risk = abs(position.stop_price - self.entry_price) if position.stop_price else 0
                
                if max_risk > 0 and pnl >= (max_risk * self.rr_ratio):
                    # Move SL to breakeven (with small buffer to avoid commission)
                    breakeven_sl = self.entry_price * 0.9995
                    self._update_stop_loss(position, breakeven_sl)
                    self.log_message(f"[BREAKEVEN] SHORT {self.symbol}: Moved SL to breakeven {breakeven_sl:.5f}")
    
    def _update_stop_loss(self, position, new_stop_price):
        """Update stop loss for a position by canceling old order and submitting new one."""
        try:
            orders = self.get_orders()
            for order in orders:
                if order.asset.symbol == position.symbol and order.status == "open":
                    if order.order_type == "stop" or (hasattr(order, 'stop_price') and order.stop_price is not None):
                        self.cancel_order(order)
            
            # Submit new stop order
            stop_order = self.create_order(
                self.symbol, position.quantity, "sell" if position.side == "long" else "buy",
                order_type="stop",
                stop_price=new_stop_price
            )
            self.submit_order(stop_order)
        except Exception as e:
            self.log_message(f"[ERROR] Failed to update SL: {e}")
    
    def _is_daily_drawdown_halted(self, current_date):
        """Check if daily drawdown limit has been exceeded."""
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

class TrendStrategy(Strategy):
    """
    Sentiment-based trading strategy using AI analysis.
    Uses 1:2 risk-reward ratio with proper stop loss and take profit.
    
    ✅ FEATURES:
    - Breakeven protection: Moves SL to entry when reaching 1:2 RR
    - Daily drawdown cap: Halts trading if daily loss exceeds threshold
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
        self._manage_breakeven_and_drawdown()
        
        # Check if drawdown halted trading
        if self._is_daily_drawdown_halted(current_date):
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
                    quantity = self.calculate_quantity(asset, stop_loss_price)

                    if quantity <= 0:
                        self.log_message(f"Skipping {ticker}. Price is too high for ${self.risk_amount} trade limit.")
                        continue
                    
                    order = self.create_order(
                        asset, quantity, "buy",
                        order_class="bracket",
                        take_profit_price=take_profit_price,
                        stop_loss_price=stop_loss_price
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
                        order_class="bracket",
                        take_profit_price=take_profit_price,
                        stop_loss_price=stop_loss_price
                    )
                    self.submit_order(order)
                    if ticker in self.entry_prices:
                        del self.entry_prices[ticker]
                    self.log_message(f"[EXIT] SELL {ticker} @ {price:.2f} | SL: {stop_loss_price:.2f} | TP: {take_profit_price:.2f} | Score: {avg_score:.2f}")
                    self.order_sent = True

        if not self.order_sent:
            self.log_message("No Orders Made... Unto the Next Iteration")
    
    def _manage_breakeven_and_drawdown(self):
        """
        Manages breakeven stops for active positions across all tickers.
        When a position reaches 1:2 RR, moves SL to entry (with commission buffer).
        """
        open_positions = self.get_positions()
        
        if not open_positions:
            return
        
        for position in open_positions:
            ticker = position.symbol
            if ticker not in self.entry_prices:
                self.entry_prices[ticker] = position.avg_fill_price
            
            entry_price = self.entry_prices[ticker]
            current_price = self.get_last_price(ticker)
            
            if current_price is None:
                continue
            
            # Calculate unrealized P&L and check if reached 1:2 RR
            if position.side == "long":
                pnl = current_price - entry_price
                max_risk = abs(entry_price - position.stop_price) if position.stop_price else 0
                
                if max_risk > 0 and pnl >= (max_risk * self.rr_ratio):
                    # Move SL to breakeven (with small buffer to avoid commission)
                    breakeven_sl = entry_price * 1.0005
                    self._update_stop_loss_for_ticker(ticker, position.quantity, breakeven_sl, "sell")
                    self.log_message(f"[BREAKEVEN] LONG {ticker}: Moved SL to breakeven {breakeven_sl:.4f}")
            
            elif position.side == "short":
                pnl = entry_price - current_price
                max_risk = abs(position.stop_price - entry_price) if position.stop_price else 0
                
                if max_risk > 0 and pnl >= (max_risk * self.rr_ratio):
                    # Move SL to breakeven (with small buffer to avoid commission)
                    breakeven_sl = entry_price * 0.9995
                    self._update_stop_loss_for_ticker(ticker, position.quantity, breakeven_sl, "buy")
                    self.log_message(f"[BREAKEVEN] SHORT {ticker}: Moved SL to breakeven {breakeven_sl:.4f}")
    
    def _update_stop_loss_for_ticker(self, ticker, quantity, new_stop_price, side):
        """Update stop loss for a position by canceling old order and submitting new one."""
        try:
            orders = self.get_orders()
            for order in orders:
                if order.asset.symbol == ticker and order.status == "open":
                    if order.order_type == "stop" or (hasattr(order, 'stop_price') and order.stop_price is not None):
                        self.cancel_order(order)
            
            # Submit new stop order
            stop_order = self.create_order(
                Asset(symbol=ticker, asset_type="stock"), quantity, side,
                order_type="stop",
                stop_price=new_stop_price
            )
            self.submit_order(stop_order)
        except Exception as e:
            self.log_message(f"[ERROR] Failed to update SL for {ticker}: {e}")
    
    def _is_daily_drawdown_halted(self, current_date):
        """Check if daily drawdown limit has been exceeded."""
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

class ACB(Strategy):
    """
    Asian Close Break (ACB) Strategy
    
    ⏰ TIME ZONE: ALL TIMES ARE IN NIGERIAN TIME (UTC+1)
    - start = time(14, 0) means 14:00 NGT (13:00 UTC)
    - end = time(16, 30) means 16:30 NGT (15:30 UTC)
    - All timestamps in backtesting: Nigerian Time (UTC+1)
    """
    def initialize(self):
        self.symbol = self.parameters.get("symbol")
        self.sleeptime = "1M"
        self.asset = Asset(symbol=self.symbol, asset_type="forex")
        self.risk_amount = 25
        self.start = time(14, 0)  # 14:00 NGT (13:00 UTC)
        self.end = time(16, 30)   # 16:30 NGT (15:30 UTC)
        self.traded_today = False
        self.last_trade_date = None

    def get_signal_day(self, current_time):
        """Is it Green or Red Light Day"""
        try:
            df = self.get_historical_prices(self.asset, 2, "day")
        except Exception as e:
            self.log_message(f"Error: {e}")
            return None

        if df is None or df.pandas_df.empty or len(df.pandas_df) < 2:
            self.log_message("Warning: No data found for the current signal request.")
            return None

        yesterday = df.pandas_df.iloc[-1]
        day_before = df.pandas_df.iloc[-2]

        try:
            yesterday_close = float(yesterday.get("close"))
            yesterday_open = float(yesterday.get("open"))
            day_before_high = float(day_before.get("high"))
            day_before_low = float(day_before.get("low"))
            day_before_close = float(day_before.get("close"))
            day_before_open = float(day_before.get("open"))
        except (TypeError, ValueError):
            self.log_message(f"{current_time} --- Missing daily OHLC data. Skipping signal calculation ---")
            return None

        values_to_check = [
            yesterday_close, yesterday_open, day_before_high,
            day_before_low, day_before_close, day_before_open
        ]
        if any(pd.isna(value) for value in values_to_check):
            self.log_message(f"{current_time} --- Missing daily OHLC data. Skipping signal calculation ---")
            return None

        if yesterday_close > day_before_high:
            self.log_message(f"{current_time} --- EXPECTING BULLISH TREND TODAY ---")
            return "BULLISH"
        elif yesterday_close > yesterday_open and day_before_close < day_before_open:
            self.log_message(f"{current_time} --- EXPECTING BULLISH TREND TODAY --- ")
            return "BULLISH"
        
        elif yesterday_close < day_before_low:
            self.log_message(f"{current_time} --- EXPECTING BEARISH TREND TODAY ---")
            return "BEARISH"
        elif yesterday_close < yesterday_open and day_before_close > day_before_open:
            self.log_message(f"{current_time} -- EXPECTING BEARISH TREND TODAY --")
            return "BEARISH"
        
        return "NO SIGNAL"
    
    def get_coil_range(self):
        """Return the High and Low of the last 60 minutes."""

        df = self.get_historical_prices(self.asset, 60, "minute")
        
        if df is None or df.pandas_df.empty:
            return None, None
            
        return df.pandas_df['high'].max(), df.pandas_df['low'].min()
    
    def on_trading_iteration(self):
        dt = self.get_datetime()
        current_time = dt.time()
        current_date = dt.date()

        # Reset daily flag
        if self.last_trade_date != current_date:
            self.traded_today = False
            self.last_trade_date = current_date

        if not (self.start <= current_time <= self.end):
            self.log_message("Not Within Trading Period...")
            return
        
        if self.traded_today:
            self.log_message("Already traded today. Skipping...")
            return
        
        signal = self.get_signal_day(current_time)
        if signal is None or signal == "NO SIGNAL":
            return
        
        last_price = self.get_last_price(self.asset)
        high, low = self.get_coil_range()

        if high is None or low is None:
            self.log_message("Could not fetch coil range. Skipping iteration.")
            return
            
        stop_loss_distance = abs(high - low)

        if signal == "BULLISH" and last_price > high:
            limit_price = low
            stop_price = last_price + (stop_loss_distance * 2)

            quantity = calculate_quantity(self, self.asset, stop_price)

            self.log_message(f"{current_time} --- BUY at {quantity} for {self.asset.symbol} ---")
            order = self.create_order(
                self.symbol, quantity, "buy",
                order_class = "bracket",
                take_profit_price = limit_price,
                stop_loss_price = stop_price
            )
            self.submit_order(order)
            self.traded_today = True
        
        elif signal == "BEARISH" and last_price < low:
            limit_price = high
            stop_price = last_price - (stop_loss_distance * 2)

            quantity = calculate_quantity(self, self.asset, stop_price)

            self.log_message(f"{current_time} --- SELL at {quantity} for {self.asset.symbol} ---")
            order = self.create_order(
                self.symbol, quantity, "sell",
                order_class = "bracket",
                take_profit_price = limit_price,
                stop_loss_price = stop_price
            )
            self.submit_order(order)
            self.traded_today = True

class SMTDivergence(Strategy):
    """
    Smart Money Technique (SMT) Divergence Strategy
    
    Detects divergences between two highly correlated assets (e.g., NQ vs YM, ES vs NQ).
    When one asset makes a new swing high/low but the other fails to follow:
    - This indicates institutional manipulation and potential reversal
    - Bullish SMT: Both moving lower, but one makes lower low while other makes higher low
    - Bearish SMT: Both moving higher, but one makes higher high while other makes lower high
    
    ⏰ TIME ZONE: ALL TIMES ARE IN NIGERIAN TIME (UTC+1)
    - NY Session: 13:30-16:00 NGT (12:30-15:00 UTC)
    - London Session: 07:00-10:00 NGT (06:00-09:00 UTC)
    - All timestamps in logs/backtesting: Nigerian Time (UTC+1)
    """

    def is_killzone(self):
        current_time = self.get_datetime().time()
        ny_start = time(13, 30)    # 13:30 NGT (12:30 UTC)
        ny_end = time(16, 0)       # 16:00 NGT (15:00 UTC)
        london_start = time(7, 0)  # 07:00 NGT (06:00 UTC)
        london_end = time(10, 0)   # 10:00 NGT (09:00 UTC)
        return (ny_start <= current_time <= ny_end) or (london_start <= current_time <= london_end)

    def initialize(self):
        self.sleeptime = "1m"
        self.side = None
        self.entry_price = None
        self.stop_price = None
        self.target_asset = None
        self.max_daily_drawdown_pct = self.parameters.get("max_daily_drawdown_pct", 0.02)
        self.trades_count = 0
        self.last_trade_date = None
        self.swing_lookback = self.parameters.get("swing_lookback", 5)
        
        # Validate required parameters
        required_params = ["symbol_nq", "symbol_ym", "risk_per_trade", "ratio"]
        for param in required_params:
            if self.parameters.get(param) is None:
                raise ValueError(f"Missing required parameter: {param}")
        
        # Validate parameter values
        if self.parameters.get("ratio") <= 0:
            raise ValueError("Ratio must be greater than 0")
        if self.parameters.get("risk_per_trade") <= 0:
            raise ValueError("Risk per trade must be greater than 0")
        if self.max_daily_drawdown_pct <= 0:
            raise ValueError("max_daily_drawdown_pct must be greater than 0")

    def on_trading_iteration(self):
        open_positions = self.get_positions()
        if hasattr(self.broker, "cleanup_breakeven_tracking"):
            self.broker.cleanup_breakeven_tracking(self, open_positions)
        if hasattr(self.broker, "manage_breakeven_positions"):
            self.broker.manage_breakeven_positions(self, open_positions, self.get_last_price)

        if not self.is_killzone():
            return

        current_date = self.get_datetime().date()
        if self.last_trade_date != current_date:
            self.last_trade_date = current_date
            self.trades_count = 0
            if hasattr(self.broker, "reset_daily_drawdown"):
                self.broker.reset_daily_drawdown(self, current_date, self.get_portfolio_value())
            self.log_message(f"New trading day started: {current_date}")

        if self.trades_count >= self.parameters.get("trades_per_day", 3):
            if self.get_datetime().minute == 0:
                self.log_message("Daily trade limit reached... Till Tomorrow")
            return

        if hasattr(self.broker, "is_daily_drawdown_halted"):
            halted, realized_pnl, max_daily_loss = self.broker.is_daily_drawdown_halted(
                self, current_date, self.get_portfolio_value(), self.max_daily_drawdown_pct
            )
        else:
            halted, realized_pnl, max_daily_loss = False, 0.0, 0.0

        if halted:
            if self.get_datetime().minute == 0:
                self.log_message(
                    f"Daily drawdown cap reached. Realized P&L: {realized_pnl:.2f} / "
                    f"Loss limit: -{max_daily_loss:.2f}. Trading halted until next session."
                )
            return

        nq_asset = Asset(self.parameters.get("symbol_nq"), "stock")
        ym_asset = Asset(self.parameters.get("symbol_ym"), "stock")

        # Fetch 15-minute data for swing detection
        try:
            nq_data = self.get_historical_prices(nq_asset, 20, "15m")
            ym_data = self.get_historical_prices(ym_asset, 20, "15m")
        except Exception as e:
            self.log_message(f"Error fetching historical prices: {e}")
            return
        
        if nq_data is None or ym_data is None:
            self.log_message("Unable to fetch historical data for NQ or YM")
            return
        
        nq_df = nq_data if isinstance(nq_data, pd.DataFrame) else nq_data.df
        ym_df = ym_data if isinstance(ym_data, pd.DataFrame) else ym_data.df

        if len(nq_df) < self.swing_lookback + 2 or len(ym_df) < self.swing_lookback + 2:
            return

        # Detect swings in recent bars
        nq_swings = self._find_recent_swings(nq_df, self.swing_lookback)
        ym_swings = self._find_recent_swings(ym_df, self.swing_lookback)

        if nq_swings is None or ym_swings is None:
            return

        nq_swing_high, nq_swing_low = nq_swings
        ym_swing_high, ym_swing_low = ym_swings

        # Detect SMT divergence
        signal = self._detect_smt_divergence(nq_swing_high, ym_swing_high, nq_swing_low, ym_swing_low)

        if signal is None:
            return

        self.side, self.target_asset = signal
        current_price = self.get_last_price(self.target_asset)

        if current_price is None:
            return

        # Execute trade on divergence confirmation
        self._execute_trade_on_divergence(nq_df, ym_df, current_price, nq_asset, ym_asset)


    def _find_recent_swings(self, df, lookback):
        """
        Find the most recent swing high and swing low in the dataframe.
        Returns (swing_high_price, swing_low_price) or None if insufficient data.
        """
        if len(df) < lookback + 2:
            return None

        recent = df.tail(lookback + 2)
        
        swing_highs = []
        swing_lows = []

        # Identify swing points (local extremes with at least 1 candle on each side)
        for i in range(1, len(recent) - 1):
            high = recent['high'].iloc[i]
            low = recent['low'].iloc[i]
            prev_high = recent['high'].iloc[i - 1]
            next_high = recent['high'].iloc[i + 1]
            prev_low = recent['low'].iloc[i - 1]
            next_low = recent['low'].iloc[i + 1]

            if high > prev_high and high > next_high:
                swing_highs.append(high)

            if low < prev_low and low < next_low:
                swing_lows.append(low)

        if not swing_highs or not swing_lows:
            return None

        return (max(swing_highs), min(swing_lows))

    def _detect_smt_divergence(self, nq_high, ym_high, nq_low, ym_low):
        """
        Detect SMT divergence between NQ and YM swings.
        
        Returns:
            (side, target_asset) tuple where side is "buy" or "sell"
            None if no divergence detected
        """
        # Bearish SMT: One makes new high, other doesn't (expect reversal down)
        if nq_high > ym_high:
            self.log_message(f"Bearish SMT Detected: NQ HH={nq_high:.2f} > YM HH={ym_high:.2f}")
            return ("sell", Asset(self.parameters.get("symbol_nq"), "stock"))
        
        if ym_high > nq_high:
            self.log_message(f"Bearish SMT Detected: YM HH={ym_high:.2f} > NQ HH={nq_high:.2f}")
            return ("sell", Asset(self.parameters.get("symbol_ym"), "stock"))

        # Bullish SMT: One makes new low, other doesn't (expect reversal up)
        if nq_low < ym_low:
            self.log_message(f"Bullish SMT Detected: NQ LL={nq_low:.2f} < YM LL={ym_low:.2f}")
            return ("buy", Asset(self.parameters.get("symbol_nq"), "stock"))
        
        if ym_low < nq_low:
            self.log_message(f"Bullish SMT Detected: YM LL={ym_low:.2f} < NQ LL={nq_low:.2f}")
            return ("buy", Asset(self.parameters.get("symbol_ym"), "stock"))

        return None

    def _execute_trade_on_divergence(self, nq_df, ym_df, current_price, nq_asset, ym_asset):
        """Execute trade when SMT divergence is detected."""
        
        # Check for existing position
        existing_position = self.get_position(self.target_asset)
        if existing_position is not None:
            self.log_message(f"Position already exists for {self.target_asset.symbol}, skipping entry")
            return

        # Get target asset data to find recent swing for stop loss
        target_is_nq = self.target_asset.symbol == self.parameters.get("symbol_nq")
        target_df = nq_df if target_is_nq else ym_df

        if self.side == "buy":
            # Stop loss below recent swing low
            self.stop_price = target_df['low'].tail(5).min()
        else:
            # Stop loss above recent swing high
            self.stop_price = target_df['high'].tail(5).max()

        risk_dist = abs(current_price - self.stop_price)

        if risk_dist <= 0:
            self.log_message(f"Risk distance invalid ({risk_dist}), skipping trade")
            return

        quantity = int(self.parameters.get("risk_per_trade") / risk_dist)

        if quantity <= 0:
            self.log_message(f"Quantity too small ({quantity}), skipping trade")
            return

        # Calculate take profit using R:R ratio
        ratio = self.parameters.get("ratio", 2)
        if self.side == "buy":
            limit_price = current_price + (risk_dist * ratio)
        else:
            limit_price = current_price - (risk_dist * ratio)

        order = self.create_order(
            self.target_asset, quantity, self.side, type="market",
            order_class = "bracket",
            take_profit_price = self.stop_price,
            stop_loss_price = limit_price
        )

        self.submit_order(order)
        self.log_message(
            f"SMT Trade Executed: {self.side.upper()} {self.target_asset.symbol} "
            f"@ {current_price:.2f} | SL: {self.stop_price:.2f} | TP: {limit_price:.2f} | Qty: {quantity}"
        )

        if hasattr(self.broker, "register_entry_for_breakeven"):
            self.broker.register_entry_for_breakeven(
                self, self.target_asset, self.side, current_price, risk_dist
            )

        self.trades_count += 1
        self.log_message(f"Trade #{self.trades_count} submitted")

        # Reset after trade
        self.side = None
        self.entry_price = None
        self.stop_price = None
        self.target_asset = None

    def on_filled_order(self, position, order, price, quantity, multiplier):
        if hasattr(self.broker, "handle_filled_order_risk"):
            self.broker.handle_filled_order_risk(
                self,
                position,
                order,
                price,
                quantity,
                multiplier,
                self.get_positions(),
                self.get_datetime().date(),
                self.get_portfolio_value(),
                self.max_daily_drawdown_pct,
            )

class ICTModel(Strategy):
    def initialize(self):
        self.symbol = self.parameters.get("symbol")
        self.sleeptime = "1M"
        self.asset = Asset(symbol=self.symbol, asset_type="forex")
        self.risk_amount = self.parameters.get("risk_amount", 25)
        self.max_daily_drawdown_pct = self.parameters.get("max_daily_drawdown_pct", 0.02)
        self.stop_buffer_pips = self.parameters.get("stop_buffer_pips", 2)
        self.est_tz = pytz.timezone("America/New_York")
        self.slots = {
            "london_open": (time(2, 0), time(5, 0)),
            "ny_am": (time(9, 30), time(11, 0)),
            "ny_pm": (time(13, 30), time(16, 0)),
        }
        self.trades_per_day = 3
        self.current_est_date = None
        self.daily_trade_count = 0
        self.slot_used = {slot: False for slot in self.slots}
        self.active_slot = None
        self.daily_equity_start = None
        self.drawdown_halted = False
        self.previous_session_high = None
        self.previous_session_low = None
        self.session_levels_for_est_date = None
        self.swept_high = False
        self.swept_low = False
        self.reversal_confirmed = None
        self.pre_sweep_swing_low = None
        self.pre_sweep_swing_high = None
        self.active_fvg = None
        self.sweep_extreme = None
        self.pending_setup_slot = None
        self.has_open_position = False
        self.pending_entry_order = None
        self.pending_entry_slot = None
        self.entry_order_slots = {}
        self.filled_entry_order_ids = set()

    def _extract_price_df(self, bars):
        if bars is None:
            return None
        if isinstance(bars, pd.DataFrame):
            df = bars
        elif hasattr(bars, "pandas_df"):
            df = bars.pandas_df
        else:
            return None
        if df is None or df.empty:
            return None
        return df.sort_index()

    def _to_est_datetime(self, dt):
        if dt.tzinfo is None:
            dt = pytz.UTC.localize(dt)
        return dt.astimezone(self.est_tz)

    def _active_slot_for_time(self, est_time):
        for slot_name, (start, end) in self.slots.items():
            if start <= est_time < end:
                return slot_name
        return None

    def _pip_value(self):
        return 0.01 if "JPY" in self.symbol.upper() else 0.0001

    def _reset_daily_state(self, est_date):
        self.current_est_date = est_date
        self.daily_trade_count = 0
        self.slot_used = {slot: False for slot in self.slots}
        self.drawdown_halted = False
        self.daily_equity_start = self.get_portfolio_value()
        self.previous_session_high = None
        self.previous_session_low = None
        self.session_levels_for_est_date = None
        self.entry_order_slots = {}
        self.filled_entry_order_ids = set()
        self.pending_entry_order = None
        self.pending_entry_slot = None
        self._reset_setup_state()
        if hasattr(self.broker, "reset_daily_drawdown"):
            self.broker.reset_daily_drawdown(self, est_date, self.daily_equity_start)

    def _reset_setup_state(self):
        self.swept_high = False
        self.swept_low = False
        self.reversal_confirmed = None
        self.pre_sweep_swing_low = None
        self.pre_sweep_swing_high = None
        self.active_fvg = None
        self.sweep_extreme = None
        self.pending_setup_slot = None

    def _has_open_position(self):
        position = self.get_position(self.asset)
        return position is not None and getattr(position, "quantity", 0) != 0

    def _cancel_pending_entry(self, reason):
        if self.pending_entry_order is None:
            return
        if hasattr(self.broker, "cancel_order"):
            self.broker.cancel_order(self.pending_entry_order)
        self.log_message(f"[ORDER CANCELED] Pending entry canceled: {reason}")
        self.pending_entry_order = None
        self.pending_entry_slot = None
        self._reset_setup_state()

    def _mark_entry_filled(self, filled_slot, order_id=None):
        if filled_slot is None:
            return
        if order_id is not None:
            if order_id in self.filled_entry_order_ids:
                return
            self.filled_entry_order_ids.add(order_id)
            self.entry_order_slots.pop(order_id, None)
        if not self.slot_used.get(filled_slot, False):
            self.slot_used[filled_slot] = True
            self.daily_trade_count += 1
            self.log_message(
                f"[ENTRY FILLED] Slot: {filled_slot} | Daily Trades: {self.daily_trade_count}/3"
            )

    def _is_drawdown_halted(self, est_date):
        equity_now = self.get_portfolio_value()
        if self.daily_equity_start is None:
            self.daily_equity_start = equity_now

        if hasattr(self.broker, "is_daily_drawdown_halted"):
            halted, _, _ = self.broker.is_daily_drawdown_halted(
                self, est_date, self.daily_equity_start, self.max_daily_drawdown_pct
            )
            return halted

        max_loss = self.daily_equity_start * self.max_daily_drawdown_pct
        return equity_now <= (self.daily_equity_start - max_loss)

    def _update_previous_session_levels(self, est_date):
        if (
            self.session_levels_for_est_date == est_date
            and self.previous_session_high is not None
            and self.previous_session_low is not None
        ):
            return True

        minute_df = self._extract_price_df(self.get_historical_prices(self.asset, 1800, "minute"))
        if minute_df is None:
            return False

        est_index = minute_df.index
        if getattr(est_index, "tz", None) is None:
            est_index = est_index.tz_localize("UTC")
        est_index = est_index.tz_convert(self.est_tz)
        est_dates = pd.Series(est_index.date, index=minute_df.index)
        previous_dates = sorted({d for d in est_dates.unique() if d < est_date})
        if not previous_dates:
            return False

        previous_session_date = previous_dates[-1]
        previous_session_df = minute_df[est_dates == previous_session_date]
        if previous_session_df.empty:
            return False

        self.previous_session_high = float(previous_session_df["high"].max())
        self.previous_session_low = float(previous_session_df["low"].min())
        self.session_levels_for_est_date = est_date
        self._reset_setup_state()

        self.log_message(
            f"[SESSION LEVELS] Prev session high={self.previous_session_high}, "
            f"low={self.previous_session_low}"
        )
        return True

    def _find_latest_swing_low(self, df):
        lows = df["low"].values
        for i in range(len(lows) - 2, 0, -1):
            if lows[i] < lows[i - 1] and lows[i] < lows[i + 1]:
                return float(lows[i])
        return None

    def _find_latest_swing_high(self, df):
        highs = df["high"].values
        for i in range(len(highs) - 2, 0, -1):
            if highs[i] > highs[i - 1] and highs[i] > highs[i + 1]:
                return float(highs[i])
        return None

    def _is_displacement_break(self, closed_df):
        if len(closed_df) < 21:
            return False

        break_candle = closed_df.iloc[-1]
        prior_candles = closed_df.iloc[-21:-1]

        average_range = (prior_candles["high"] - prior_candles["low"]).mean()
        candle_range = break_candle["high"] - break_candle["low"]
        candle_body = abs(break_candle["close"] - break_candle["open"])

        if candle_range <= 0 or average_range <= 0:
            return False

        body_ratio = candle_body / candle_range
        return body_ratio >= 0.60 and candle_range >= (1.5 * average_range)

    def _fvg_from_last_three(self, closed_df, direction):
        if len(closed_df) < 3:
            return None

        first = closed_df.iloc[-3]
        third = closed_df.iloc[-1]

        if direction == "bullish":
            if float(first["high"]) < float(third["low"]):
                lower = float(first["high"])
                upper = float(third["low"])
                return lower, upper
        elif direction == "bearish":
            if float(first["low"]) > float(third["high"]):
                lower = float(third["high"])
                upper = float(first["low"])
                return lower, upper
        return None

    def on_trading_iteration(self):
        dt = self.get_datetime()
        est_dt = self._to_est_datetime(dt)
        est_date = est_dt.date()
        est_time = est_dt.time()

        if self.current_est_date != est_date:
            self._cancel_pending_entry("EST day reset")
            self._reset_daily_state(est_date)

        self.has_open_position = self._has_open_position()

        if self.daily_trade_count >= self.trades_per_day:
            return

        self.drawdown_halted = self._is_drawdown_halted(est_date)
        if self.drawdown_halted:
            self._cancel_pending_entry("daily drawdown halt")
            return

        active_slot = self._active_slot_for_time(est_time)
        if self.pending_entry_order is not None and active_slot != self.pending_entry_slot:
            self._cancel_pending_entry("killzone ended")
            return

        if active_slot is None or self.slot_used.get(active_slot, False):
            self.active_slot = None
            if not self.has_open_position:
                self._reset_setup_state()
            return

        if self.active_slot != active_slot and not self.has_open_position:
            self.active_slot = active_slot
            self._reset_setup_state()

        if not self._update_previous_session_levels(est_date):
            return

        minute_df = self._extract_price_df(self.get_historical_prices(self.asset, 60, "minute"))
        if minute_df is None or len(minute_df) < 25:
            return

        closed_df = minute_df.iloc[:-1]
        if closed_df.empty:
            return

        if self.has_open_position:
            if self.pending_entry_order is not None and self.pending_entry_slot is not None:
                self._mark_entry_filled(
                    self.pending_entry_slot,
                    getattr(self.pending_entry_order, "identifier", None),
                )
            self.pending_entry_order = None
            self.pending_entry_slot = None
            self._reset_setup_state()
            return

        last_price = self.get_last_price(self.asset)
        if last_price is None:
            return

        if not self.swept_high and not self.swept_low:
            current_candle_high = float(minute_df.iloc[-1]["high"])
            current_candle_low = float(minute_df.iloc[-1]["low"])
            if last_price > self.previous_session_high:
                self.swept_high = True
                self.pre_sweep_swing_low = self._find_latest_swing_low(closed_df)
                self.sweep_extreme = max(current_candle_high, float(self.previous_session_high))
                self.pending_setup_slot = active_slot
                self.log_message(
                    f"[SWEEP] Price swept previous session high "
                    f"({self.previous_session_high}) at {last_price}"
                )
            elif last_price < self.previous_session_low:
                self.swept_low = True
                self.pre_sweep_swing_high = self._find_latest_swing_high(closed_df)
                self.sweep_extreme = min(current_candle_low, float(self.previous_session_low))
                self.pending_setup_slot = active_slot
                self.log_message(
                    f"[SWEEP] Price swept previous session low "
                    f"({self.previous_session_low}) at {last_price}"
                )
            return

        if self.pending_setup_slot != active_slot:
            self._reset_setup_state()
            return

        current_candle_high = float(minute_df.iloc[-1]["high"])
        current_candle_low = float(minute_df.iloc[-1]["low"])
        if self.swept_high:
            self.sweep_extreme = max(float(self.sweep_extreme), current_candle_high)
        elif self.swept_low:
            self.sweep_extreme = min(float(self.sweep_extreme), current_candle_low)

        if self.swept_high and self.reversal_confirmed is None:
            if (
                last_price < self.previous_session_high
                and self.pre_sweep_swing_low is not None
                and len(closed_df) >= 2
            ):
                previous_close = float(closed_df.iloc[-2]["close"])
                break_close = float(closed_df.iloc[-1]["close"])
                if (
                    previous_close >= self.pre_sweep_swing_low
                    and break_close < self.pre_sweep_swing_low
                    and self._is_displacement_break(closed_df)
                ):
                    bearish_fvg = self._fvg_from_last_three(closed_df, "bearish")
                    if bearish_fvg is not None:
                        self.reversal_confirmed = "bearish"
                        self.active_fvg = {
                            "direction": "bearish",
                            "lower": bearish_fvg[0],
                            "upper": bearish_fvg[1],
                        }
                        self.log_message(
                            f"[REVERSAL CONFIRMED] Bearish displaced MSS after high sweep. "
                            f"Break close {break_close} below pre-sweep swing low "
                            f"{self.pre_sweep_swing_low}. FVG: {bearish_fvg[0]}-{bearish_fvg[1]}"
                        )

        elif self.swept_low and self.reversal_confirmed is None:
            if (
                last_price > self.previous_session_low
                and self.pre_sweep_swing_high is not None
                and len(closed_df) >= 2
            ):
                previous_close = float(closed_df.iloc[-2]["close"])
                break_close = float(closed_df.iloc[-1]["close"])
                if (
                    previous_close <= self.pre_sweep_swing_high
                    and break_close > self.pre_sweep_swing_high
                    and self._is_displacement_break(closed_df)
                ):
                    bullish_fvg = self._fvg_from_last_three(closed_df, "bullish")
                    if bullish_fvg is not None:
                        self.reversal_confirmed = "bullish"
                        self.active_fvg = {
                            "direction": "bullish",
                            "lower": bullish_fvg[0],
                            "upper": bullish_fvg[1],
                        }
                        self.log_message(
                            f"[REVERSAL CONFIRMED] Bullish displaced MSS after low sweep. "
                            f"Break close {break_close} above pre-sweep swing high "
                            f"{self.pre_sweep_swing_high}. FVG: {bullish_fvg[0]}-{bullish_fvg[1]}"
                        )

        if self.reversal_confirmed is None or self.active_fvg is None:
            return

        if self.pending_entry_order is not None:
            return

        fvg_midpoint = (self.active_fvg["lower"] + self.active_fvg["upper"]) / 2
        entry_side = "buy" if self.reversal_confirmed == "bullish" else "sell"

        stop_buffer = self.stop_buffer_pips * self._pip_value()
        if entry_side == "buy":
            stop_price = float(self.sweep_extreme) - stop_buffer
            opposing_liquidity_tp = float(self.previous_session_high)
            fallback_tp = fvg_midpoint + (2 * (fvg_midpoint - stop_price))
            take_profit = opposing_liquidity_tp if opposing_liquidity_tp > fvg_midpoint else fallback_tp
        else:
            stop_price = float(self.sweep_extreme) + stop_buffer
            opposing_liquidity_tp = float(self.previous_session_low)
            fallback_tp = fvg_midpoint - (2 * (stop_price - fvg_midpoint))
            take_profit = opposing_liquidity_tp if opposing_liquidity_tp < fvg_midpoint else fallback_tp

        if abs(fvg_midpoint - stop_price) <= 0:
            self._reset_setup_state()
            return

        quantity = calculate_quantity(self, self.asset, stop_price)
        if quantity <= 0:
            self._reset_setup_state()
            return

        order = self.create_order(
            self.asset,
            quantity,
            entry_side,
            order_class = "bracket",
            take_profit_price = take_profit,
            stop_loss_price = stop_price,
            limit_price=fvg_midpoint
        )

        self.submit_order(order)

        if getattr(order, "status", None) == "error":
            self._reset_setup_state()
            return

        if getattr(order, "identifier", None):
            self.entry_order_slots[order.identifier] = active_slot
            self.pending_entry_order = order
            self.pending_entry_slot = active_slot
            self.log_message(
                f"[ENTRY ORDER] {entry_side.upper()} {self.symbol} limit @ CE {fvg_midpoint} | "
                f"SL: {stop_price} | TP: {take_profit} | Slot: {active_slot} | "
                f"Daily Trades: {self.daily_trade_count}/3"
            )

    def on_filled_order(self, position, order, price, quantity, multiplier):
        order_id = getattr(order, "identifier", None)
        if order_id is None:
            return
        if order_id not in self.entry_order_slots:
            return

        filled_slot = self.entry_order_slots.get(order_id)
        self._mark_entry_filled(filled_slot, order_id)

        if self.pending_entry_order is not None and getattr(self.pending_entry_order, "identifier", None) == order_id:
            self.pending_entry_order = None
            self.pending_entry_slot = None
        self._reset_setup_state()

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
