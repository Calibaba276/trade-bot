from datetime import time
from lumibot.strategies.strategy import Strategy

class LiquiditySweep(Strategy):
    def initialize(self):
        self.symbol = self.parameters.get("symbol")
        self.sleeptime = "1M"
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
            bars = self.get_historical_prices(self.symbol, 420, "minute")
            df = bars.pandas_df
            morning_data = df.between_time("00:00", "06:59")

            if not morning_data.empty:
                self.high = morning_data["high"].max()
                self.low = morning_data["low"].min()
                self.last_range_date = dt.date()
                print(f"--- {dt.date()} From 12:00 - 6:59am: High={self.high}, Low={self.low} ---", flush=True)
            else:
                print(f"--- {dt.date()} Market is Closed (No Data) ---", flush=True)

        if self.high and self.low and not self.traded_today:
            if current_time > time(7, 0) and current_time < time(17, 0):
                last_price = self.get_last_price(self.symbol)

                # --- BEARISH MSS ---
                # Step 1: Detect sweep above the high
                if last_price > self.high:
                    self.swept_high = True

                # Step 2: Price reverses below high — scan recent bars for a swing low (higher low)
                if self.swept_high and last_price < self.high and self.mss_swing_low is None:
                    bars = self.get_historical_prices(self.symbol, 20, "minute")
                    df = bars.pandas_df
                    lows = df["low"].values
                    for i in range(len(lows) - 2, 0, -1):
                        if lows[i] < lows[i - 1] and lows[i] < lows[i + 1] and lows[i] > self.low:
                            self.mss_swing_low = float(lows[i])
                            print(f"{dt} -- Bearish MSS: Swing Low identified at {self.mss_swing_low}", flush=True)
                            break

                # Step 3: Price breaks below the swing low — MSS confirmed, SELL
                if self.mss_swing_low and last_price < self.mss_swing_low:

                    self.stop_loss_distance = (self.mss_swing_low + self.buffer) - last_price
                    quantity = int(self.risk_amount / self.stop_loss_distance)

                    print(f"{dt} -- SELL (Bearish MSS) -- Price {last_price} broke below swing low {self.mss_swing_low}", flush=True)
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
                    bars = self.get_historical_prices(self.symbol, 20, "minute")
                    df = bars.pandas_df
                    highs = df["high"].values
                    for i in range(len(highs) - 2, 0, -1):
                        if highs[i] > highs[i - 1] and highs[i] > highs[i + 1] and highs[i] < self.high:
                            self.mss_swing_high = float(highs[i])
                            print(f"{dt} -- Bullish MSS: Swing High identified at {self.mss_swing_high}", flush=True)
                            break

                # Step 3: Price breaks above the swing high — MSS confirmed, BUY
                if self.mss_swing_high and last_price > self.mss_swing_high:

                    self.stop_loss_distance = last_price - (self.mss_swing_high - self.buffer)
                    quantity = int(self.risk_amount / self.stop_loss_distance)

                    print(f"{dt} -- BUY (Bullish MSS) -- Price {last_price} broke above swing high {self.mss_swing_high}", flush=True)
                    order = self.create_order(
                        self.symbol, quantity, "buy",
                        take_profit_price = self.high,
                        stop_loss_price = self.mss_swing_high - self.buffer
                    )
                    self.submit_order(order)
                    self.traded_today = True