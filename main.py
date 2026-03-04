import os
from lumi_trade import TradingStrategy
from lumibot.backtesting import PolygonDataBacktesting
from dotenv import load_dotenv

from datetime import datetime

load_dotenv()

BACKTESTING_START = os.getenv("BACKTESTING_START")
BACKTESTING_END = os.getenv("BACKTESTING_END")
POLYGON_API_KEY = os.getenv("POLYGON_API_KEY")

start = datetime.strptime(BACKTESTING_START, "%Y-%m-%d")
end = datetime.strptime(BACKTESTING_END, "%Y-%m-%d")

if __name__ == "__main__":
    TradingStrategy.run_backtest(
        PolygonDataBacktesting,
        start,
        end,
        parameters={"symbol": "C:EURUSD"},
        quiet_logs=False,
        polygon_api_key=POLYGON_API_KEY
    )