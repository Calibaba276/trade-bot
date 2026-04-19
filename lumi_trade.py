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
