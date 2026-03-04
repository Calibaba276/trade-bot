from datetime import time
from lumibot.strategies.strategy import Strategy

class TradingStrategy(Strategy):
    def initialize(self):
        self.symbol = self.parameters.get("symbol")
        self.sleeptime = "1M"
        self.high = None
        self.low = None

    def on_trading_iteration(self):

        current_time = self.get_datetime().time()

        if current_time == time(7, 0):
            bars = self.get_historical_prices(self.symbol, 500, "minute")
            df = bars.pandas_df

            morning_data = df.between_time("00:00", "06:59")

            if not morning_data.empty:
                self.high = morning_data["high"].max()
                self.low = morning_data["low"].min()
            else:
                print(f"--- {self.get_datetime().date()} Market is Closed (No Data) ---")

            print(f"From 12:00 - 6:59am: High={self.high}, Low={self.low}")