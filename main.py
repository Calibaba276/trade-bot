import os
from lumi_trade import TradingStrategy
from lumibot.backtesting import YahooDataBacktesting
from dotenv import load_dotenv

from datetime import datetime

load_dotenv()

BACKTESTING_START = os.getenv("BACKTESTING_START")
BACKTESTING_END = os.getenv("BACKTESTING_END")

start = datetime.strptime(BACKTESTING_START, "%Y-%m-%d")
end = datetime.strptime(BACKTESTING_END, "%Y-%m-%d")

if __name__ == "__main__":
    TradingStrategy.run_backtest(
        YahooDataBacktesting,
        start,
        end,
        parameters={"symbol": "EURUSD=X"},
        quiet_logs=False
    )