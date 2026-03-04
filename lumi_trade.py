from datetime import datetime
from lumibot.backtesting import YahooDataBacktesting
from lumibot.strategies.strategy import Strategy

class TradingStrategy(Strategy):
    def initialize(self):
        self.symbol = self.parameters.get("symbol")
        self.sleeptime = "1M"

    def on_trading_iteration(self):
        bars = self.get_historical_prices(self.symbol, 1000, "minute")
        df = bars.pandas_df

        morning_data = df.between_time("00:00", "06:59")

        if not morning_data.empty:
            high = morning_data["high"].max()
            low = morning_data["low"].min()

            print(f"From 12:00 - 6:59am: High={high}, Low={low}")
        else:
            print("No Data Provided")