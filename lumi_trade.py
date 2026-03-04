from datetime import time
from lumibot.strategies.strategy import Strategy

class TradingStrategy(Strategy):
    def initialize(self):
        self.symbol = self.parameters.get("symbol")
        self.sleeptime = "1M"
        self.high = None
        self.low = None

    def on_trading_iteration(self):

        dt = self.get_datetime()
        current_time = dt.time()

        if current_time == time(7, 0):
            bars = self.get_historical_prices(self.symbol, 420, "minute")
            df = bars.pandas_df
            morning_data = df.between_time("00:00", "06:59")

            if not morning_data.empty:
                self.high = morning_data["high"].max()
                self.low = morning_data["low"].min()
                print(f"--- {dt.date()} From 12:00 - 6:59am: High={self.high}, Low={self.low} ---", flush=True)
            else:
                print(f"--- {dt.date()} Market is Closed (No Data) ---", flush=True)