from datetime import time
from lumibot.strategies.strategy import Strategy

import logging
logging.basicConfig(filename="trades.log", level=logging.INFO, format="%(asctime)s | %(message)s")

class TradingStrategy(Strategy):
    def initialize(self):
        self.symbol = self.parameters.get("symbol")
        self.sleeptime = "5M"
        self.high = None
        self.low = None
        self.traded_today = False
        self.last_range_date = None

    def on_trading_iteration(self):

        dt = self.get_datetime()
        current_time = dt.time()

        if current_time == time(0, 0):
            self.high = None
            self.low = None
            self.traded_today = False

        if current_time >= time(7, 0) and self.last_range_date != dt.date():
            bars = self.get_historical_prices(self.symbol, 420, "minute")
            df = bars.pandas_df
            morning_data = df.between_time("00:00", "06:59")

            if not morning_data.empty:
                self.high = morning_data["high"].max()
                self.low = morning_data["low"].min()
                self.last_range_date = dt.date()
                print(f"--- {dt.date()} From 12:00 - 6:59am: High={self.high}, Low={self.low} ---", flush=True)
                logging.info(f"--- {dt.date()} From 12:00 - 6:59am: High={self.high}, Low={self.low} ---")

            else:
                print(f"--- {dt.date()} Market is Closed (No Data) ---", flush=True)
                logging.info(f"--- {dt.date()} Market is Closed (No Data) ---")

        if self.high and self.low and not self.traded_today:
            if current_time > time(7, 0) and current_time < time(17, 0):
                last_price = self.get_last_price(self.symbol)

                # BUY
                if last_price > self.high:
                    print(f"{dt}-- BUY SIGNAL -- Price {last_price} passed High - {self.high}", flush = True)
                    logging.info(f"{dt}-- BUY SIGNAL -- Price {last_price} passed High - {self.high}")
                    order = self.create_order(self.symbol, 100, "buy")
                    self.submit_order(order)

                    self.traded_today = True

                # SELL
                elif last_price < self.low:
                    print(f"{dt} -- SELL SIGNAL -- Price {last_price} passed Low - {self.low}", flush = True)
                    logging.info(f"{dt} -- SELL SIGNAL -- Price {last_price} passed Low - {self.low}")
                    order = self.create_order(self.symbol, 100, "sell")
                    self.submit_order(order)

                    self.traded_today = True