import math
import json
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

        dt = self.broker.get_datetime()
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
    def initialize(self):
        self.symbol = self.parameters.get("symbol")
        self.sleeptime = "1M"
        self.asset = Asset(symbol=self.symbol, asset_type="forex")
        self.risk_amount = 25
        self.start = time(14, 0)
        self.end = time(16, 30)
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
    
    def initialize(self):
        self.sleeptime = "1m"
        self.bullish_smt = False
        self.bearish_smt = False
        self.mss_level = None
        self.stop_price = None
        self.target_asset = None
        
        # Validate required parameters
        required_params = ["symbol_nq", "symbol_ym", "risk_per_trade", "ratio"]
        for param in required_params:
            if self.parameters.get(param) is None:
                raise ValueError(f"Missing required parameter: {param}")
        
        # Set defaults if needed
        if self.parameters.get("ratio") <= 0:
            raise ValueError("Ratio must be greater than 0")
        if self.parameters.get("risk_per_trade") <= 0:
            raise ValueError("Risk per trade must be greater than 0")

    def on_trading_iteration(self):
        nq_asset = Asset(self.parameters.get("symbol_nq"), "stock")
        ym_asset = Asset(self.parameters.get("symbol_ym"), "stock")

        # Fetch historical data with error handling
        try:
            nq_data = self.get_historical_prices(nq_asset, 5, "15m")
            ym_data = self.get_historical_prices(ym_asset, 5, "15m")
        except Exception as e:
            self.log_message(f"Error fetching historical prices: {e}")
            return
        
        # Validate data exists
        if nq_data is None or ym_data is None:
            self.log_message("Unable to fetch historical data for NQ or YM")
            return
        
        nq = nq_data.df
        ym = ym_data.df

        if len(nq) < 5 or len(ym) < 5: return

        # LOW FOR NASDAQ
        nq_low_curr = nq["low"].iloc[-1]
        nq_low_prev = nq["low"].iloc[-2]

        # LOW FOR DOW JONES
        ym_low_curr = ym["low"].iloc[-1]
        ym_low_prev = ym["low"].iloc[-2]

        # HIGH FOR NASDAQ
        nq_high_curr = nq["high"].iloc[-1]
        nq_high_prev = nq["high"].iloc[-2]

        # HIGH FOR DOW JONES
        ym_high_curr = ym["high"].iloc[-1]
        ym_high_prev = ym["high"].iloc[-2]

        # BULLISH SMT
        if (nq_low_curr < nq_low_prev) and (ym_low_curr > ym_low_prev):
            self.target_asset = ym_asset
            self.bullish_smt = True
            self.stop_price = ym['low'].iloc[-1]
            self.mss_level = ym['high'].iloc[-1]
            self.log_message("Bullish SMT Sequence Detected")
            
        elif (ym_low_curr < ym_low_prev) and (nq_low_curr > nq_low_prev):
            self.target_asset = nq_asset
            self.bullish_smt = True
            self.stop_price = nq['low'].iloc[-1]
            self.mss_level = nq['high'].iloc[-1]
            self.log_message("Bullish SMT Sequence Detected")

        # BEARISH SMT
        elif (nq_high_curr > nq_high_prev) and (ym_high_curr < ym_high_prev):
            self.target_asset = ym_asset
            self.bearish_smt = True
            self.stop_price = ym['high'].iloc[-1]
            self.mss_level = ym['low'].iloc[-1]
            self.log_message("Bearish SMT Sequence Detected")
            
        elif (ym_high_curr > ym_high_prev) and (nq_high_curr < nq_high_prev):
            self.target_asset = nq_asset
            self.bearish_smt = True
            self.stop_price = nq['high'].iloc[-1]
            self.mss_level = nq['low'].iloc[-1]
            self.log_message("Bearish SMT Sequence Detected")

        if self.target_asset is not None and self.mss_level is not None:
            last_price = self.get_last_price(self.target_asset)
            
            if self.bullish_smt:
                if last_price > self.mss_level:
                    
                    risk_distance = last_price - self.stop_price

                    if risk_distance <= 0:
                        self.log_message("Invalid risk distance for bullish trade, skipping")
                        return

                    limit_price = last_price + (risk_distance * self.parameters.get("ratio"))
                    quantity = self.parameters.get("risk_per_trade") / risk_distance
                    quantity = int(quantity)

                    if quantity <= 0:
                        self.log_message("Quantity too small, skipping trade")
                        return

                    order = self.create_order(
                        self.target_asset, 
                        quantity, 
                        "buy",
                        type="market",
                        limit_price=limit_price,
                        stop_price=self.stop_price
                    )
                    self.submit_order(order)
                    self.log_message(f"BUY - MSS Confirmed: 1m - {last_price} > {self.mss_level}")

                    # Reset after trade
                    self.stop_price = None
                    self.mss_level = None
                    self.target_asset = None
                    self.bullish_smt = False

            elif self.bearish_smt:
                if last_price < self.mss_level:

                    risk_distance = self.stop_price - last_price

                    if risk_distance <= 0:
                        self.log_message("Invalid risk distance for bearish trade, skipping")
                        return

                    limit_price = last_price - (risk_distance * self.parameters.get("ratio"))
                    quantity = self.parameters.get("risk_per_trade") / risk_distance
                    quantity = int(quantity)

                    if quantity <= 0:
                        self.log_message("Quantity too small, skipping trade")
                        return

                    self.log_message(f"SELL - MSS Confirmed: 1m - {last_price} < {self.mss_level}")
                    order = self.create_order(
                        self.target_asset, 
                        quantity,
                        "sell",
                        type="market",
                        stop_price=self.stop_price,
                        limit_price=limit_price
                    )
                    self.submit_order(order)

                    # Reset after trade
                    self.stop_price = None
                    self.mss_level = None
                    self.target_asset = None
                    self.bearish_smt = False

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
