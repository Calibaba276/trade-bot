import os
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
    def initialize(self):
        self.symbol = self.parameters.get("symbol")
        self.sleeptime = "1M"
        self.set_market("24/7")
        # self.timezone = "America/New_York"
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

    def on_trading_iteration(self):

        dt = self.get_datetime()
        current_time = dt.time()

        if current_time == time(0, 0):
            self.high = None
            self.low = None
            self.traded_today = False
            self.swept_high = False
            self.swept_low = False
            self.mss_swing_low = None
            self.mss_swing_high = None
            self.risk_amount = 25
            self.stop_loss_distance = None

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
            if current_time > time(7, 0) and current_time < time(17, 0):
                last_price = self.get_last_price(self.symbol)

                # --- BEARISH MSS ---
                # Step 1: Detect sweep above the high
                if last_price > self.high:
                    self.swept_high = True

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

                    self.stop_loss_distance = (self.mss_swing_low + self.buffer) - last_price
                    quantity = int(self.risk_amount / self.stop_loss_distance)

                    self.log_message(f"{current_time} -- SELL (Bearish MSS) -- Price {last_price} broke below swing low {self.mss_swing_low}")
                    order = self.create_order(
                        self.symbol, quantity, "sell",
                        take_profit_price = self.low,
                        stop_loss_price = self.mss_swing_low + self.buffer
                    )
                    self.submit_order(order)
                    self.traded_today = True

                # --- BULLISH MSS ---
                # Step 1: Detect sweep below the low
                elif last_price < self.low:
                    self.swept_low = True

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

                    self.stop_loss_distance = last_price - (self.mss_swing_high - self.buffer)
                    quantity = int(self.risk_amount / self.stop_loss_distance)

                    self.log_message(f"{current_time} -- BUY (Bullish MSS) -- Price {last_price} broke above swing high {self.mss_swing_high}")
                    order = self.create_order(
                        self.symbol, quantity, "buy",
                        take_profit_price = self.high,
                        stop_loss_price = self.mss_swing_high - self.buffer
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
            except Exception as e:
                self.log_message(f"Could not enable {ticker}: {e}. Skipping...")
                continue

            if score > 0.7:
                pos = self.get_position(asset)
                if pos is None:
                    quantity = self.calculate_quantity(asset)

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
                    quantity = self.calculate_quantity(asset)

                    if quantity <= 0:
                        self.log_message(f"Skipping {ticker}. Price is too high for $25 trade limit.")
                        continue

                    order = self.create_order(asset, pos.quantity, "sell", order_type="market")
                    self.submit_order(order)
                    self.log_message(f"{date} - {time} SELL {ticker} | Score: {score} | Reason: {signal['reason']}")
                    self.order_sent = True

        if not self.order_sent:
            self.log_message("No Orders Made... Unto the Next Iteration")

    def calculate_quantity(self, asset):
        
        # Simple logic: Use 5% of available cash per trade
        price = self.broker.get_last_price(asset)

        if price is None or price == 0:
            self.log_message(f"Warning: Price for {asset.symbol} is 0 or None. Cannot calculate $25 trade.")
            return 0

        raw_quantity = self.risk_amount / price

        quantity = round(raw_quantity, 2)

        if quantity < 0.01:
            self.log_message(f"Price of {asset.symbol} is too high! $25 buys less than 0.01 lots.")
            return 0
        
        return quantity
