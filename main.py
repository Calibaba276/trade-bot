import os
from lumi_trade import LiquiditySweep
from lumibot.backtesting import PolygonDataBacktesting
from lumibot.brokers import Alpaca
from lumibot.traders import Trader

from dotenv import load_dotenv

from datetime import datetime

load_dotenv()

ISBACKTESTING = os.getenv("ISBACKTESTING", "false").lower() == "true"
BACKTESTING_START = os.getenv("BACKTESTING_START")
BACKTESTING_END = os.getenv("BACKTESTING_END")
POLYGON_API_KEY = os.getenv("POLYGON_API_KEY")
ALPACA_API_KEY = os.getenv("ALPACA_API_KEY")
ALPACA_API_SECRET = os.getenv("ALPACA_API_SECRET")

if __name__ == "__main__":
    if ISBACKTESTING:

        start = datetime.strptime(BACKTESTING_START, "%Y-%m-%d")
        end = datetime.strptime(BACKTESTING_END, "%Y-%m-%d")

        LiquiditySweep.run_backtest(
            PolygonDataBacktesting,
            start,
            end,
            parameters={"symbol": "C:EURUSD"},
            benchmark_asset="C:EURUSD",
            quiet_logs=False,
            polygon_api_key=POLYGON_API_KEY
        )
    else:
        broker = Alpaca({
            "API_KEY": ALPACA_API_KEY,
            "API_SECRET": ALPACA_API_SECRET,
            "PAPER": True
        })

        strategy = LiquiditySweep(broker=broker, parameters={"symbol": "EURUSD"})
        trader = Trader()
        trader.add_strategy(strategy)
        trader.run_all()