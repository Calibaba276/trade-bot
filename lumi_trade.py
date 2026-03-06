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

    def on_trading_iteration(self):

        dt = self.get_datetime()
        current_time = dt.time()

        if current_time == time(0, 0):
            self.high = None
            self.low = None
            self.traded_today = False
            self.swept_high = False
            self.swept_low = False

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

                # SELL
                #DETECT INITIAL SWEEP
                if last_price > self.high:
                    self.swept_high = True
                
                # PRICES REVERSES BACK ABOVE LOW
                elif last_price < self.high and self.swept_high:
                    print(f"{dt}-- SELL SIGNAL -- Price {last_price} reversed below High - {self.high}", flush = True)
                    order = self.create_order(
                        self.symbol, 10000, "sell",
                        take_profit_price = self.low,
                        stop_loss_price = self.high + self.buffer
                    )
                    self.submit_order(order)

                    self.traded_today = True

                # BUY
                #DETECT INITIAL SWEEP
                elif last_price < self.low:
                    self.swept_low = True

                elif last_price > self.low and self.swept_low:
                    print(f"{dt} -- BUY SIGNAL -- Price {last_price} passed Low - {self.low}", flush = True)
                    order = self.create_order(
                        self.symbol, 10000, "buy",
                        take_profit_price = self.high,
                        stop_loss_price = self.low - self.buffer
                    )
                    self.submit_order(order)

                    self.traded_today = True