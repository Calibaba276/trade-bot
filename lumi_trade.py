import math
import json
import pandas as pd
from datetime import time
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
        self.risk_amount = 25
        self.stop_loss_distance = None
        self.asset = Asset(symbol=self.symbol, asset_type="forex")

    def before_market_opens(self):
        self.high = None
        self.low = None
        self.traded_today = False
        self.swept_high = False
        self.swept_low = False
        self.mss_swing_low = None
        self.mss_swing_high = None
        self.stop_loss_distance = None

    def on_trading_iteration(self):

        dt = self.get_datetime()
        current_time = dt.time()

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
                        limit_price = self.low,
                        stop_price = self.mss_swing_low + self.buffer
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
                        limit_price = self.high,
                        stop_price = self.mss_swing_high - self.buffer
                    )
                    self.submit_order(order)
                    self.traded_today = True

class TrendStrategy(Strategy):
    """
    Trend Strategy - AI-Powered Sentiment Analysis
    
    ⏰ TIME ZONE: ALL TIMES ARE IN NIGERIAN TIME (UTC+1)
    - All timestamps in logs: Nigerian Time (UTC+1), not UTC
    - When backtesting shows times: interpret as NGT
    - Conversions: 01:00 NGT = 00:00 UTC, etc.
    """
    def initialize(self):
        self.result = FetchTrends(NEWS_API_KEY, GEMINI_API_KEY)
        self.sleeptime = "5M"
        self.set_market("24/5")
        self.risk_amount = 25
    
    def on_trading_iteration(self):

        dt = self.get_datetime()

        date = dt.date()
        time = dt.time()

        payload = json.loads(self.result.get_ai_response())
        signals = payload.get("signals", [])
        self.order_sent = False

        if not signals:
            return

        for signal in signals:
            ticker = signal["ticker"]
            score = signal["sentiment_score"]
            reason = signal["reason"]

            asset = Asset(symbol=ticker, asset_type="stock")
            
            try:
                self.broker.select_symbol(asset)
            except Exception:
                self.log_message(f"Could not enable {ticker}. Skipping...")
                continue

            if score > 0.7:
                pos = self.get_position(asset)
                if pos is None:
                    quantity = calculate_quantity(self, asset)

                    if quantity <= 0:
                        self.log_message(f"Skipping {ticker}. Price is too high for $25 trade limit.")
                        continue
                    
                    order = self.create_order(asset, quantity, "buy", order_type="market")
                    self.submit_order(order)
                    self.log_message(f"{date} - {time} BUY {ticker} | Score: {score} | Reason: {reason}")
                    self.order_sent = True

            elif score <= -0.5:
                pos = self.get_position(asset)
                if pos is not None:

                    order = self.create_order(asset, pos.quantity, "sell", order_type="market")
                    self.submit_order(order)
                    self.log_message(f"{date} - {time} SELL {ticker} | Score: {score} | Reason: {signal['reason']}")
                    self.order_sent = True

        if not self.order_sent:
            self.log_message("No Orders Made... Unto the Next")
    
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

        if df is not None and not df.empty:
            yesterday = df.pandas_df.iloc[-1]
            day_before = df.pandas_df.iloc[-2]
        else:
            self.log_message("Warning: No data found for the current signal request.")
            return None 

        if yesterday['close'] > day_before['high']:
            self.log_message(f"{current_time} --- EXPECTING BULLISH TREND TODAY ---")
            return "BULLISH"
        elif yesterday['close'] > yesterday['open'] and day_before['close'] < day_before['open']:
            self.log_message(f"{current_time} --- EXPECTING BULLISH TREND TODAY --- ")
            return "BULLISH"
        
        elif yesterday['close'] < day_before['low']:
            self.log_message(f"{current_time} --- EXPECTING BEARISH TREND TODAY ---")
            return "BEARISH"
        elif yesterday['close'] < yesterday['open'] and day_before['close'] > day_before['open']:
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
                limit_price=limit_price,
                stop_price=stop_price
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
                limit_price=limit_price,
                stop_price=stop_price
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
            stop_price=self.stop_price,
            limit_price=limit_price
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
            
class ICT2022Strategy(Strategy):
    """
    ICT (Inner Circle Trader) 2022 Model Implementation
    
    Key Concepts:
    - Market Structure Analysis (highs/lows, swings)
    - Order Blocks (institutional trading zones)
    - Fair Value Gaps (FVG) - unfilled price gaps
    - Liquidity Sweep & Reversal (MSS - Market Structure Shift)
    - Institutional Bias Framework
    - Premium & Discount Zones
    - Asian Session Focus (optimal institutional liquidity)
    
    ⏰ TIME ZONE: ALL TIMES ARE IN NIGERIAN TIME (UTC+1)
    - Asian Session: 01:00-09:00 NGT (00:00-08:00 UTC)
    - All timestamps in backtesting logs: Nigerian Time (UTC+1)
    - All time() comparisons: interpreted as NGT, not UTC
    """

    def initialize(self):
        self.symbol = self.parameters.get("symbol", "EURUSD")
        self.sleeptime = "5M"
        self.set_market("24/7")
        
        # Risk Management
        self.risk_amount = self.parameters.get("risk_amount", 25)
        self.risk_reward_ratio = self.parameters.get("risk_reward_ratio", 1.5)
        self.max_positions = self.parameters.get("max_positions", 1)
        
        # Market Structure
        self.asset = Asset(symbol=self.symbol, asset_type="forex")
        self.daily_high = None
        self.daily_low = None
        self.asian_session_high = None
        self.asian_session_low = None
        self.order_blocks = []
        self.fair_value_gaps = []
        
        # Trading State
        self.traded_today = False
        self.last_structure_update = None
        self.liquidity_swept = False
        self.current_bias = None  # "BULLISH" or "BEARISH"
        self.entry_point = None
        self.stop_loss = None
        self.take_profit = None
        
        # Swing Detection
        self.last_swing_high = None
        self.last_swing_low = None
        self.swing_high_index = None
        self.swing_low_index = None
        
        # Premium/Discount Zones
        self.premium_zone_high = None
        self.premium_zone_low = None
        self.discount_zone_high = None
        self.discount_zone_low = None

    def before_market_opens(self):
        """Reset daily markers"""
        self.daily_high = None
        self.daily_low = None
        self.traded_today = False
        self.liquidity_swept = False
        self.entry_point = None
        self.stop_loss = None
        self.take_profit = None

    def on_trading_iteration(self):
        """Main trading logic following ICT 2022 methodology"""
        dt = self.get_datetime()

        current_time = dt.time()
        current_date = dt.date()
        
        # === PHASE 1: Identify Asian Session Range (01:00 - 09:00 Nigerian Time / 00:00 - 08:00 UTC) ===
        if current_time >= time(1, 0) and current_time < time(9, 0):
            if self.last_structure_update != current_date:
                self._identify_asian_session_structure()
                self.last_structure_update = current_date
        
        # === PHASE 2: Identify Daily Market Structure ===
        if current_time >= time(9, 0) and self.daily_high is None:
            self._identify_daily_structure()
        
        # === PHASE 3: Identify Order Blocks ===
        if len(self.order_blocks) < 2:
            self._identify_order_blocks()
        
        # === PHASE 4: Identify Fair Value Gaps (FVG) ===
        if len(self.fair_value_gaps) < 3:
            self._identify_fvg()
        
        # === PHASE 5: Premium & Discount Zone Identification ===
        if self.premium_zone_high is None:
            self._identify_premium_discount_zones()
        
        # === PHASE 6: Determine Market Bias (Institutional Direction) ===
        self.current_bias = self._determine_market_bias()
        
        # === PHASE 7: Liquidity Sweep & Entry Logic ===
        if not self.traded_today:
            self._execute_liquidity_sweep_strategy()
        
        # === PHASE 8: Trade Management ===
        if self.entry_point is not None:
            self._manage_position()

    def _identify_asian_session_structure(self):
        """
        Identify Asian session range (01:00 - 09:00 Nigerian Time / 00:00 - 08:00 UTC)
        This is the institutional setup for the day
        """
        try:
            df = self.get_historical_prices(self.asset, 480, "minute")
            
            if df is None or df.empty:
                return
            
            self.asian_session_high = df["high"].max()
            self.asian_session_low = df["low"].min()
            
            self.log_message(
                f"[ASIAN SESSION 01:00-09:00 NGT] High: {self.asian_session_high}, Low: {self.asian_session_low}"
            )
        except Exception as e:
            self.log_message(f"Error identifying Asian session: {e}")

    def _identify_daily_structure(self):
        """Identify key daily structure: highs and lows"""
        try:
            df = self.get_historical_prices(self.asset, 1440, "minute")
            
            if df is None or df.empty:
                return
            
            self.daily_high = df["high"].max()
            self.daily_low = df["low"].min()
            
            self.log_message(
                f"[DAILY STRUCTURE] High: {self.daily_high}, Low: {self.daily_low}, "
                f"Range: {self.daily_high - self.daily_low}"
            )
        except Exception as e:
            self.log_message(f"Error identifying daily structure: {e}")

    def _identify_swing_points(self, lookback_bars=20):
        """Identify swing highs and swing lows"""
        try:
            df = self.get_historical_prices(self.asset, lookback_bars + 5, "minute")
            
            if df is None or df.empty or len(df) < 3:
                return
            
            highs = df["high"].values
            lows = df["low"].values
            
            for i in range(len(highs) - 2, 1, -1):
                if highs[i] > highs[i - 1] and highs[i] > highs[i + 1]:
                    self.last_swing_high = float(highs[i])
                    self.swing_high_index = i
                    break
            
            for i in range(len(lows) - 2, 1, -1):
                if lows[i] < lows[i - 1] and lows[i] < lows[i + 1]:
                    self.last_swing_low = float(lows[i])
                    self.swing_low_index = i
                    break
            
            self.log_message(
                f"[SWING POINTS] High: {self.last_swing_high}, Low: {self.last_swing_low}"
            )
        except Exception as e:
            self.log_message(f"Error identifying swing points: {e}")

    def _identify_order_blocks(self):
        """Order Blocks: areas of concentrated selling/buying by institutions"""
        try:
            df = self.get_historical_prices(self.asset, 100, "minute")
            
            if df is None or df.empty or len(df) < 10:
                return
            
            closes = df["close"].values
            highs = df["high"].values
            lows = df["low"].values
            
            for i in range(3, len(closes) - 3):
                # Bearish Order Block (after strong bearish move)
                if closes[i] < closes[i-1] and closes[i-1] < closes[i-2]:
                    if closes[i+1] > closes[i] and closes[i+2] > closes[i+1]:
                        ob = {
                            "type": "BEARISH",
                            "high": max(highs[i-2:i+1]),
                            "low": min(lows[i-2:i+1]),
                            "index": i
                        }
                        if ob not in self.order_blocks:
                            self.order_blocks.append(ob)
                
                # Bullish Order Block (after strong bullish move)
                if closes[i] > closes[i-1] and closes[i-1] > closes[i-2]:
                    if closes[i+1] < closes[i] and closes[i+2] < closes[i+1]:
                        ob = {
                            "type": "BULLISH",
                            "high": max(highs[i-2:i+1]),
                            "low": min(lows[i-2:i+1]),
                            "index": i
                        }
                        if ob not in self.order_blocks:
                            self.order_blocks.append(ob)
            
            if self.order_blocks:
                self.log_message(f"[ORDER BLOCKS] Identified {len(self.order_blocks)} blocks")
        except Exception as e:
            self.log_message(f"Error identifying order blocks: {e}")

    def _identify_fvg(self, lookback=50):
        """Fair Value Gap (FVG): Unfilled gaps in price that typically get filled later"""
        try:
            df = self.get_historical_prices(self.asset, lookback, "minute")
            
            if df is None or df.empty or len(df) < 3:
                return
            
            highs = df["high"].values
            lows = df["low"].values
            
            for i in range(2, len(highs)):
                # Bullish FVG: Price gaps up
                if lows[i] > highs[i-2]:
                    fvg = {
                        "type": "BULLISH",
                        "top": highs[i-2],
                        "bottom": lows[i],
                        "index": i
                    }
                    if fvg not in self.fair_value_gaps:
                        self.fair_value_gaps.append(fvg)
                
                # Bearish FVG: Price gaps down
                if highs[i] < lows[i-2]:
                    fvg = {
                        "type": "BEARISH",
                        "top": lows[i-2],
                        "bottom": highs[i],
                        "index": i
                    }
                    if fvg not in self.fair_value_gaps:
                        self.fair_value_gaps.append(fvg)
            
            if self.fair_value_gaps:
                self.log_message(f"[FVG] Identified {len(self.fair_value_gaps)} gaps")
        except Exception as e:
            self.log_message(f"Error identifying FVG: {e}")

    def _identify_premium_discount_zones(self):
        """
        Premium Zone: Area above the Asian session high (institutional selling)
        Discount Zone: Area below the Asian session low (institutional buying)
        """
        if self.asian_session_high and self.asian_session_low:
            range_size = self.asian_session_high - self.asian_session_low
            
            self.premium_zone_low = self.asian_session_high
            self.premium_zone_high = self.asian_session_high + (range_size * 0.2)
            
            self.discount_zone_high = self.asian_session_low
            self.discount_zone_low = self.asian_session_low - (range_size * 0.2)
            
            self.log_message(
                f"[ZONES] Premium: {self.premium_zone_low}-{self.premium_zone_high}, "
                f"Discount: {self.discount_zone_low}-{self.discount_zone_high}"
            )

    def _determine_market_bias(self):
        """
        Determine if market is BULLISH or BEARISH
        BULLISH: Higher lows and higher highs
        BEARISH: Lower highs and lower lows
        """
        try:
            self._identify_swing_points()
            
            if self.last_swing_high is None or self.last_swing_low is None:
                return None
            
            if self.swing_low_index is not None and self.swing_high_index is not None:
                if self.swing_low_index > self.swing_high_index:
                    return "BULLISH"
                else:
                    return "BEARISH"
        except Exception as e:
            self.log_message(f"Error determining bias: {e}")
        
        return None

    def _execute_liquidity_sweep_strategy(self):
        """
        ICT Liquidity Sweep Strategy (MSS - Market Structure Shift):
        1. Price sweeps the Asian session high (bullish) or low (bearish)
        2. Creates a liquidity event
        3. Institutions reverse after collecting liquidity
        4. Enter on the reversal with order block support/resistance
        """
        try:
            last_price = self.get_last_price(self.symbol)
            
            if last_price is None:
                return
            
            # BULLISH SETUP: Sweep above Asian High, then reverse into order block
            if (self.asian_session_high and last_price > self.asian_session_high 
                and not self.liquidity_swept and self.current_bias != "BEARISH"):
                
                self.liquidity_swept = True
                self.log_message(
                    f"[LIQUIDITY SWEEP-BULLISH] Price broke above Asian High {self.asian_session_high}"
                )
                
                for ob in self.order_blocks:
                    if ob["type"] == "BULLISH":
                        if last_price <= ob["high"] and last_price >= ob["low"]:
                            self._execute_bullish_entry(last_price, ob)
                            return
            
            # BEARISH SETUP: Sweep below Asian Low, then reverse into order block
            if (self.asian_session_low and last_price < self.asian_session_low 
                and not self.liquidity_swept and self.current_bias != "BULLISH"):
                
                self.liquidity_swept = True
                self.log_message(
                    f"[LIQUIDITY SWEEP-BEARISH] Price broke below Asian Low {self.asian_session_low}"
                )
                
                for ob in self.order_blocks:
                    if ob["type"] == "BEARISH":
                        if last_price <= ob["high"] and last_price >= ob["low"]:
                            self._execute_bearish_entry(last_price, ob)
                            return
        except Exception as e:
            self.log_message(f"Error in liquidity sweep strategy: {e}")

    def _execute_bullish_entry(self, current_price, order_block):
        """Execute bullish entry at order block support"""
        try:
            self.entry_point = order_block["low"]
            self.stop_loss = order_block["low"] - (order_block["high"] - order_block["low"]) * 0.5
            self.take_profit = current_price + (current_price - self.stop_loss) * self.risk_reward_ratio
            
            quantity = calculate_quantity(self, self.asset, self.stop_loss)
            
            if quantity <= 0:
                self.log_message("Insufficient funds for bullish entry")
                return
            
            order = self.create_order(
                self.symbol, quantity, "buy",
                limit_price=self.entry_point,
                stop_price=self.stop_loss
            )
            self.submit_order(order)
            
            self.log_message(
                f"[BULLISH ENTRY] Entry: {self.entry_point}, SL: {self.stop_loss}, TP: {self.take_profit}"
            )
            self.traded_today = True
        except Exception as e:
            self.log_message(f"Error executing bullish entry: {e}")

    def _execute_bearish_entry(self, current_price, order_block):
        """Execute bearish entry at order block resistance"""
        try:
            self.entry_point = order_block["high"]
            self.stop_loss = order_block["high"] + (order_block["high"] - order_block["low"]) * 0.5
            self.take_profit = current_price - (self.stop_loss - current_price) * self.risk_reward_ratio
            
            quantity = calculate_quantity(self, self.asset, self.stop_loss)
            
            if quantity <= 0:
                self.log_message("Insufficient funds for bearish entry")
                return
            
            order = self.create_order(
                self.symbol, quantity, "sell",
                limit_price=self.entry_point,
                stop_price=self.stop_loss
            )
            self.submit_order(order)
            
            self.log_message(
                f"[BEARISH ENTRY] Entry: {self.entry_point}, SL: {self.stop_loss}, TP: {self.take_profit}"
            )
            self.traded_today = True
        except Exception as e:
            self.log_message(f"Error executing bearish entry: {e}")

    def _manage_position(self):
        """Manage active positions using ICT framework"""
        try:
            positions = self.get_positions()
            
            if not positions:
                return
            
            last_price = self.get_last_price(self.symbol)
            
            for position in positions:
                if position.quantity > 0:
                    if last_price >= self.take_profit:
                        self._close_position(position)
                
                elif position.quantity < 0:
                    if last_price <= self.take_profit:
                        self._close_position(position)
        except Exception as e:
            self.log_message(f"Error managing position: {e}")

    def _close_position(self, position):
        """Close a position at market price"""
        try:
            order = self.create_order(
                position.asset,
                position.quantity,
                "sell" if position.quantity > 0 else "buy",
                order_type="market"
            )
            self.submit_order(order)
            self.log_message(f"Position closed at market price")
            self.entry_point = None
            self.traded_today = True
        except Exception as e:
            self.log_message(f"Error closing position: {e}")


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
