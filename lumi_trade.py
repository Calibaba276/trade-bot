import math
import json
import pandas as pd
from datetime import time, timedelta
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
NIGERIAN_TZ = pytz.timezone("Africa/Lagos")


def _to_nigerian_time(dt):
    if dt.tzinfo is None:
        return NIGERIAN_TZ.localize(dt)
    return dt.astimezone(NIGERIAN_TZ)


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
    ICT 2022 Model (institutional workflow):
    1. Determine daily bias.
    2. Mark liquidity levels (previous day, Asian, and London range).
    3. Wait for a liquidity sweep in London/NY kill zones.
    4. Confirm Market Structure Shift (MSS).
    5. Identify PD array (FVG/Order Block) in premium/discount context.
    6. Enter on retracement to PD array with strict risk control.

    ⏰ TIME ZONE: ALL TIMES ARE IN NIGERIAN TIME (UTC+1).
    """

    def initialize(self):
        self.symbol = self.parameters.get("symbol", "EURUSD")
        self.sleeptime = self.parameters.get("sleeptime", "1M")
        self.set_market("24/7")

        self.asset = Asset(symbol=self.symbol, asset_type="forex")

        self.risk_amount = float(self.parameters.get("risk_amount", 25))
        self.risk_reward_ratio = float(self.parameters.get("risk_reward_ratio", 3.0))
        self.min_risk_reward = float(self.parameters.get("min_risk_reward", 3.0))
        self.max_positions = int(self.parameters.get("max_positions", 1))

        self.history_bars = int(self.parameters.get("history_bars", 2200))
        self.sweep_lookback_bars = int(self.parameters.get("sweep_lookback_bars", 120))
        self.mss_lookback_bars = int(self.parameters.get("mss_lookback_bars", 120))
        self.fvg_lookback_bars = int(self.parameters.get("fvg_lookback_bars", 180))
        self.signal_valid_minutes = int(self.parameters.get("signal_valid_minutes", 90))

        self.last_state_date = None
        self.previous_day_date = None
        self.previous_day_high = None
        self.previous_day_low = None
        self.previous_day_open = None
        self.previous_day_close = None

        self.asian_session_high = None
        self.asian_session_low = None
        self.london_range_high = None
        self.london_range_low = None

        self.daily_bias = None
        self.traded_today = False

        self.liquidity_event = None
        self.mss_event = None
        self.entry_zone = None
        self.active_trade = None

    def _reset_daily_state(self):
        self.asian_session_high = None
        self.asian_session_low = None
        self.london_range_high = None
        self.london_range_low = None
        self.daily_bias = None
        self.traded_today = False
        self.liquidity_event = None
        self.mss_event = None
        self.entry_zone = None
        self.active_trade = None

    def before_market_opens(self):
        self._reset_daily_state()

    def on_trading_iteration(self):
        dt = _to_nigerian_time(self.get_datetime())
        current_time = dt.time()
        current_date = dt.date()

        if self.last_state_date != current_date:
            self.last_state_date = current_date
            self._reset_daily_state()

        minute_df = self._get_minute_data(self.history_bars)
        if minute_df is None:
            return

        self._update_reference_levels(minute_df, current_date, current_time)
        self._manage_position()

        if self.traded_today:
            return

        if len(self._asset_positions()) >= self.max_positions:
            return

        if not self._is_killzone(current_time):
            return

        self.daily_bias = self._determine_daily_bias(minute_df, current_date)
        if self.daily_bias is None:
            return

        if self.liquidity_event is None:
            self.liquidity_event = self._detect_liquidity_sweep(minute_df, dt)
            if self.liquidity_event is None:
                return
            self.log_message(
                f"[LIQUIDITY SWEEP] {self.liquidity_event['swept_name']} swept -> "
                f"{self.liquidity_event['trade_direction']}"
            )

        if self.mss_event is None:
            self.mss_event = self._confirm_market_structure_shift(minute_df, self.liquidity_event)
            if self.mss_event is None:
                return
            self.log_message(
                f"[MSS] {self.mss_event['direction']} confirmed at pivot {self.mss_event['pivot_price']}"
            )

        if self.entry_zone is None:
            self.entry_zone = self._select_entry_zone(minute_df, self.mss_event)
            if self.entry_zone is None:
                return
            self.log_message(
                f"[PD ARRAY] {self.entry_zone['type']} "
                f"{self.entry_zone['low']:.5f}-{self.entry_zone['high']:.5f}"
            )

        if self._setup_invalidated(minute_df):
            self.log_message("[ICT RESET] Setup invalidated before entry.")
            self._clear_setup()
            return

        self._execute_entry_if_ready(minute_df, dt)

    def _get_minute_data(self, lookback_bars):
        bars = self.get_historical_prices(self.asset, lookback_bars, "minute")
        if bars is None:
            return None

        df = bars.pandas_df if hasattr(bars, "pandas_df") else bars
        if df is None or df.empty:
            return None

        if not isinstance(df.index, pd.DatetimeIndex):
            if "datetime" not in df.columns:
                return None
            df = df.copy()
            df["datetime"] = pd.to_datetime(df["datetime"])
            df = df.set_index("datetime")

        if df.index.tz is None:
            df.index = df.index.tz_localize(NIGERIAN_TZ)
        else:
            df = df.tz_convert(NIGERIAN_TZ)

        required_columns = ["open", "high", "low", "close"]
        if not set(required_columns).issubset(df.columns):
            return None

        df = df.sort_index()
        return df[required_columns].dropna()

    def _update_reference_levels(self, minute_df, current_date, current_time):
        previous_days = minute_df[minute_df.index.date < current_date]
        if not previous_days.empty:
            last_prev_date = previous_days.index[-1].date()
            if self.previous_day_date != last_prev_date:
                previous_day_data = minute_df[minute_df.index.date == last_prev_date]
                self.previous_day_date = last_prev_date
                self.previous_day_high = float(previous_day_data["high"].max())
                self.previous_day_low = float(previous_day_data["low"].min())
                self.previous_day_open = float(previous_day_data["open"].iloc[0])
                self.previous_day_close = float(previous_day_data["close"].iloc[-1])
                self.log_message(
                    f"[PREVIOUS DAY] High: {self.previous_day_high}, Low: {self.previous_day_low}"
                )

        today_data = minute_df[minute_df.index.date == current_date]
        if today_data.empty:
            return

        if self.asian_session_high is None and current_time >= time(9, 0):
            asian_data = today_data.between_time("01:00", "08:59")
            if not asian_data.empty:
                self.asian_session_high = float(asian_data["high"].max())
                self.asian_session_low = float(asian_data["low"].min())
                self.log_message(
                    f"[ASIAN SESSION 01:00-09:00 NGT] High: {self.asian_session_high}, "
                    f"Low: {self.asian_session_low}"
                )

        if self.london_range_high is None and current_time >= time(13, 30):
            london_data = today_data.between_time("08:00", "13:29")
            if not london_data.empty:
                self.london_range_high = float(london_data["high"].max())
                self.london_range_low = float(london_data["low"].min())
                self.log_message(
                    f"[LONDON RANGE 08:00-13:30 NGT] High: {self.london_range_high}, "
                    f"Low: {self.london_range_low}"
                )

    def _determine_daily_bias(self, minute_df, current_date):
        if self.previous_day_high is None or self.previous_day_low is None:
            return None

        today_data = minute_df[minute_df.index.date == current_date]
        if today_data.empty:
            return None

        today_high = float(today_data["high"].max())
        today_low = float(today_data["low"].min())
        current_close = float(today_data["close"].iloc[-1])

        if today_low < self.previous_day_low and current_close > self.previous_day_low:
            return "BULLISH"

        if today_high > self.previous_day_high and current_close < self.previous_day_high:
            return "BEARISH"

        if self.asian_session_high is not None and self.asian_session_low is not None:
            asian_midpoint = (self.asian_session_high + self.asian_session_low) / 2
            if current_close > asian_midpoint:
                return "BULLISH"
            if current_close < asian_midpoint:
                return "BEARISH"

        if self.previous_day_close is None or self.previous_day_open is None:
            return None

        if self.previous_day_close > self.previous_day_open:
            return "BULLISH"
        if self.previous_day_close < self.previous_day_open:
            return "BEARISH"

        return None

    def _is_killzone(self, current_time):
        london_killzone = time(8, 0) <= current_time < time(11, 0)
        new_york_killzone = time(13, 30) <= current_time < time(16, 0)
        return london_killzone or new_york_killzone

    def _active_liquidity_levels(self, current_time):
        levels = []

        if self.asian_session_high is not None and self.asian_session_low is not None:
            levels.append({"name": "ASIAN_HIGH", "price": self.asian_session_high, "sweep_side": "HIGH"})
            levels.append({"name": "ASIAN_LOW", "price": self.asian_session_low, "sweep_side": "LOW"})

        if self.previous_day_high is not None and self.previous_day_low is not None:
            levels.append({"name": "PDH", "price": self.previous_day_high, "sweep_side": "HIGH"})
            levels.append({"name": "PDL", "price": self.previous_day_low, "sweep_side": "LOW"})

        if current_time >= time(13, 30) and self.london_range_high is not None and self.london_range_low is not None:
            levels.append({"name": "LONDON_HIGH", "price": self.london_range_high, "sweep_side": "HIGH"})
            levels.append({"name": "LONDON_LOW", "price": self.london_range_low, "sweep_side": "LOW"})

        return levels

    def _compute_atr(self, minute_df, length=14):
        if len(minute_df) < length + 2:
            return 0.0

        high_low = minute_df["high"] - minute_df["low"]
        high_close = (minute_df["high"] - minute_df["close"].shift(1)).abs()
        low_close = (minute_df["low"] - minute_df["close"].shift(1)).abs()
        true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        atr = true_range.rolling(length).mean().iloc[-1]
        return float(atr) if pd.notna(atr) else 0.0

    def _sweep_buffer(self, minute_df):
        atr = self._compute_atr(minute_df, 14)
        return max(atr * 0.05, 0.00003)

    def _has_displacement(self, minute_df, direction):
        recent = minute_df.tail(30)
        if len(recent) < 10:
            return False

        body_sizes = (recent["close"] - recent["open"]).abs()
        baseline = float(body_sizes.iloc[:-5].tail(20).mean())
        if baseline <= 0:
            return False

        if direction == "BULLISH":
            impulse = recent.tail(5)["close"] - recent.tail(5)["open"]
            return bool((impulse > baseline * 1.5).any())

        impulse = recent.tail(5)["open"] - recent.tail(5)["close"]
        return bool((impulse > baseline * 1.5).any())

    def _detect_liquidity_sweep(self, minute_df, current_dt):
        lookback = minute_df.tail(self.sweep_lookback_bars)
        if len(lookback) < 10:
            return None

        buffer = self._sweep_buffer(lookback)
        last_close = float(lookback["close"].iloc[-1])
        levels = self._active_liquidity_levels(current_dt.time())
        if not levels:
            return None

        valid_after = lookback.index[-1] - timedelta(minutes=self.signal_valid_minutes)
        candidates = []

        for level in levels:
            price = float(level["price"])
            if level["sweep_side"] == "HIGH":
                swept_rows = lookback[lookback["high"] > price + buffer]
                swept_rows = swept_rows[swept_rows.index >= valid_after]
                if swept_rows.empty:
                    continue
                if self.daily_bias != "BEARISH" or last_close >= price:
                    continue
                if not self._has_displacement(lookback, "BEARISH"):
                    continue
                candidates.append(
                    {
                        "trade_direction": "BEARISH",
                        "swept_name": level["name"],
                        "swept_level": price,
                        "sweep_price": float(swept_rows["high"].iloc[-1]),
                        "sweep_time": swept_rows.index[-1],
                    }
                )
            else:
                swept_rows = lookback[lookback["low"] < price - buffer]
                swept_rows = swept_rows[swept_rows.index >= valid_after]
                if swept_rows.empty:
                    continue
                if self.daily_bias != "BULLISH" or last_close <= price:
                    continue
                if not self._has_displacement(lookback, "BULLISH"):
                    continue
                candidates.append(
                    {
                        "trade_direction": "BULLISH",
                        "swept_name": level["name"],
                        "swept_level": price,
                        "sweep_price": float(swept_rows["low"].iloc[-1]),
                        "sweep_time": swept_rows.index[-1],
                    }
                )

        if not candidates:
            return None

        candidates.sort(key=lambda item: item["sweep_time"])
        return candidates[-1]

    def _find_fractal_swing(self, minute_df, swing_type):
        if len(minute_df) < 7:
            return None, None

        highs = minute_df["high"].values
        lows = minute_df["low"].values
        idx = minute_df.index

        for i in range(len(minute_df) - 3, 1, -1):
            if swing_type == "HIGH":
                if (
                    highs[i] > highs[i - 1]
                    and highs[i] > highs[i - 2]
                    and highs[i] > highs[i + 1]
                    and highs[i] > highs[i + 2]
                ):
                    return float(highs[i]), idx[i]
            else:
                if (
                    lows[i] < lows[i - 1]
                    and lows[i] < lows[i - 2]
                    and lows[i] < lows[i + 1]
                    and lows[i] < lows[i + 2]
                ):
                    return float(lows[i]), idx[i]

        return None, None

    def _confirm_market_structure_shift(self, minute_df, liquidity_event):
        sweep_time = liquidity_event["sweep_time"]
        trade_direction = liquidity_event["trade_direction"]

        pre_sweep = minute_df[minute_df.index <= sweep_time].tail(self.mss_lookback_bars)
        post_sweep = minute_df[minute_df.index > sweep_time].tail(self.mss_lookback_bars)
        if len(pre_sweep) < 7 or len(post_sweep) < 3:
            return None

        if trade_direction == "BULLISH":
            pivot_price, pivot_time = self._find_fractal_swing(pre_sweep, "HIGH")
            if pivot_price is None:
                return None
            confirmation = post_sweep[post_sweep["close"] > pivot_price]
            if confirmation.empty:
                return None
            confirm_time = confirmation.index[0]
            if not self._has_displacement(post_sweep.loc[:confirm_time], "BULLISH"):
                return None
            return {
                "direction": "BULLISH",
                "pivot_price": float(pivot_price),
                "pivot_time": pivot_time,
                "confirmation_time": confirm_time,
            }

        pivot_price, pivot_time = self._find_fractal_swing(pre_sweep, "LOW")
        if pivot_price is None:
            return None
        confirmation = post_sweep[post_sweep["close"] < pivot_price]
        if confirmation.empty:
            return None
        confirm_time = confirmation.index[0]
        if not self._has_displacement(post_sweep.loc[:confirm_time], "BEARISH"):
            return None
        return {
            "direction": "BEARISH",
            "pivot_price": float(pivot_price),
            "pivot_time": pivot_time,
            "confirmation_time": confirm_time,
        }

    def _dealing_range(self):
        highs = [
            value
            for value in [self.previous_day_high, self.asian_session_high, self.london_range_high]
            if value is not None
        ]
        lows = [
            value
            for value in [self.previous_day_low, self.asian_session_low, self.london_range_low]
            if value is not None
        ]

        if not highs or not lows:
            return None, None, None

        range_high = max(highs)
        range_low = min(lows)
        if range_high <= range_low:
            return None, None, None

        return range_low, range_high, (range_low + range_high) / 2

    def _find_fvgs(self, minute_df, direction, start_time):
        data = minute_df[minute_df.index >= start_time].tail(self.fvg_lookback_bars)
        if len(data) < 3:
            return []

        highs = data["high"].values
        lows = data["low"].values
        zones = []

        for i in range(2, len(data)):
            if direction == "BULLISH":
                if lows[i] > highs[i - 2]:
                    zones.append(
                        {
                            "type": "FVG",
                            "direction": "BULLISH",
                            "low": float(highs[i - 2]),
                            "high": float(lows[i]),
                            "created_at": data.index[i],
                        }
                    )
            else:
                if highs[i] < lows[i - 2]:
                    zones.append(
                        {
                            "type": "FVG",
                            "direction": "BEARISH",
                            "low": float(highs[i]),
                            "high": float(lows[i - 2]),
                            "created_at": data.index[i],
                        }
                    )

        return zones

    def _find_order_block(self, minute_df, mss_event):
        direction = mss_event["direction"]
        confirm_time = mss_event["confirmation_time"]
        data = minute_df[minute_df.index <= confirm_time].tail(20)
        if data.empty:
            return None

        if direction == "BULLISH":
            bearish_candles = data[data["close"] < data["open"]]
            if bearish_candles.empty:
                return None
            candle = bearish_candles.iloc[-1]
            created_at = bearish_candles.index[-1]
        else:
            bullish_candles = data[data["close"] > data["open"]]
            if bullish_candles.empty:
                return None
            candle = bullish_candles.iloc[-1]
            created_at = bullish_candles.index[-1]

        return {
            "type": "ORDER_BLOCK",
            "direction": direction,
            "low": float(candle["low"]),
            "high": float(candle["high"]),
            "created_at": created_at,
        }

    def _zone_in_pd_context(self, zone, direction, midpoint):
        if midpoint is None:
            return True

        zone_mid = (zone["low"] + zone["high"]) / 2
        if direction == "BULLISH":
            return zone_mid <= midpoint
        return zone_mid >= midpoint

    def _select_entry_zone(self, minute_df, mss_event):
        _, _, midpoint = self._dealing_range()
        direction = mss_event["direction"]

        fvgs = self._find_fvgs(minute_df, direction, mss_event["confirmation_time"])
        valid_fvgs = [zone for zone in fvgs if self._zone_in_pd_context(zone, direction, midpoint)]
        if valid_fvgs:
            return valid_fvgs[-1]

        order_block = self._find_order_block(minute_df, mss_event)
        if order_block is not None and self._zone_in_pd_context(order_block, direction, midpoint):
            return order_block

        return None

    def _setup_invalidated(self, minute_df):
        if self.liquidity_event is None:
            return False

        last_close = float(minute_df["close"].iloc[-1])
        buffer = self._sweep_buffer(minute_df.tail(30))
        sweep_price = float(self.liquidity_event["sweep_price"])
        direction = self.liquidity_event["trade_direction"]

        if direction == "BULLISH":
            return last_close < sweep_price - buffer
        return last_close > sweep_price + buffer

    def _nearest_liquidity_target(self, entry_price, direction):
        highs = [
            value
            for value in [self.asian_session_high, self.previous_day_high, self.london_range_high]
            if value is not None and value > entry_price
        ]
        lows = [
            value
            for value in [self.asian_session_low, self.previous_day_low, self.london_range_low]
            if value is not None and value < entry_price
        ]

        if direction == "BULLISH":
            return min(highs) if highs else None
        return max(lows) if lows else None

    def _build_trade_plan(self, minute_df, entry_price):
        direction = self.mss_event["direction"]
        sweep_price = float(self.liquidity_event["sweep_price"])
        buffer = self._sweep_buffer(minute_df.tail(40))

        if direction == "BULLISH":
            stop_loss = sweep_price - buffer
        else:
            stop_loss = sweep_price + buffer

        risk = abs(entry_price - stop_loss)
        if risk <= 0:
            return None

        rr_multiple = max(self.risk_reward_ratio, self.min_risk_reward)
        liquidity_target = self._nearest_liquidity_target(entry_price, direction)

        if direction == "BULLISH":
            minimum_target = entry_price + (risk * rr_multiple)
            take_profit = max(minimum_target, liquidity_target) if liquidity_target is not None else minimum_target
        else:
            minimum_target = entry_price - (risk * rr_multiple)
            take_profit = min(minimum_target, liquidity_target) if liquidity_target is not None else minimum_target

        reward = abs(take_profit - entry_price)
        if reward <= 0:
            return None

        achieved_rr = reward / risk
        if achieved_rr < self.min_risk_reward:
            return None

        return {
            "direction": direction,
            "entry_price": float(entry_price),
            "stop_loss": float(stop_loss),
            "take_profit": float(take_profit),
            "risk_reward": float(achieved_rr),
        }

    def _zone_touched(self, minute_df, zone, current_price):
        buffer = self._sweep_buffer(minute_df.tail(30))
        return (zone["low"] - buffer) <= current_price <= (zone["high"] + buffer)

    def _execute_entry_if_ready(self, minute_df, dt):
        if self.entry_zone is None or self.active_trade is not None:
            return

        last_price = self.get_last_price(self.asset)
        if last_price is None:
            return

        current_price = float(last_price)
        if not self._zone_touched(minute_df, self.entry_zone, current_price):
            return

        trade_plan = self._build_trade_plan(minute_df, current_price)
        if trade_plan is None:
            return

        quantity = calculate_quantity(self, self.asset, trade_plan["stop_loss"])
        if quantity <= 0:
            self.log_message("[ICT ENTRY] Quantity <= 0; skipping trade.")
            return

        side = "buy" if trade_plan["direction"] == "BULLISH" else "sell"
        order = self.create_order(self.asset, quantity, side, order_type="market")
        self.submit_order(order)

        trade_plan["side"] = side
        trade_plan["quantity"] = quantity
        trade_plan["entry_time"] = dt
        self.active_trade = trade_plan
        self.traded_today = True

        self.log_message(
            f"[ICT ENTRY] {trade_plan['direction']} {self.symbol} @ {trade_plan['entry_price']:.5f} "
            f"| SL: {trade_plan['stop_loss']:.5f} | TP: {trade_plan['take_profit']:.5f} "
            f"| RR: {trade_plan['risk_reward']:.2f} | Zone: {self.entry_zone['type']}"
        )

        self._clear_setup()

    def _asset_positions(self):
        positions = self.get_positions()
        if not positions:
            return []

        matched = []
        for position in positions:
            position_asset = getattr(position, "asset", None)
            symbol = getattr(position_asset, "symbol", None)
            if symbol == self.asset.symbol and position.quantity != 0:
                matched.append(position)
        return matched

    def _manage_position(self):
        if self.active_trade is None:
            return

        positions = self._asset_positions()
        if not positions:
            self.active_trade = None
            return

        last_price = self.get_last_price(self.asset)
        if last_price is None:
            return

        current_price = float(last_price)
        side = self.active_trade["side"]
        stop_loss = self.active_trade["stop_loss"]
        take_profit = self.active_trade["take_profit"]

        if side == "buy":
            if current_price <= stop_loss:
                for position in positions:
                    self._close_position(position, current_price, "STOP LOSS")
            elif current_price >= take_profit:
                for position in positions:
                    self._close_position(position, current_price, "TAKE PROFIT")
        else:
            if current_price >= stop_loss:
                for position in positions:
                    self._close_position(position, current_price, "STOP LOSS")
            elif current_price <= take_profit:
                for position in positions:
                    self._close_position(position, current_price, "TAKE PROFIT")

    def _close_position(self, position, price, reason):
        exit_side = "sell" if position.quantity > 0 else "buy"
        order = self.create_order(position.asset, abs(position.quantity), exit_side, order_type="market")
        self.submit_order(order)
        self.log_message(f"[ICT EXIT] {reason} @ {price:.5f}")
        self.active_trade = None

    def _clear_setup(self):
        self.liquidity_event = None
        self.mss_event = None
        self.entry_zone = None


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
