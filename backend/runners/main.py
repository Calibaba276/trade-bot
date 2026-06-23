from datetime import datetime

from lumibot.backtesting import PolygonDataBacktesting
from lumibot.traders import Trader

from backend.brokers.mt5_broker import MetaTrader5
from backend.config.logger import setup_logger
from backend.config.secrets import get_azure_secret
from backend.strategies.liquidity_sweep import LiquiditySweep

logger = setup_logger("liquidity_sweep")


def run():
    is_backtesting = get_azure_secret("ISBACKTESTING")
    backtesting_start = get_azure_secret("BACKTESTING-START")
    backtesting_end = get_azure_secret("BACKTESTING-END")
    polygon_api_key = get_azure_secret("POLYGON-API-KEY")

    account = get_azure_secret("ACCOUNT")
    password = get_azure_secret("PASSWORD")
    server = get_azure_secret("SERVER")

    if str(is_backtesting).lower() == "true":
        start = datetime.strptime(backtesting_start, "%Y-%m-%d")
        end = datetime.strptime(backtesting_end, "%Y-%m-%d")

        LiquiditySweep.run_backtest(
            PolygonDataBacktesting,
            start,
            end,
            parameters={"symbol": "C:EURUSD"},
            benchmark_asset="C:EURUSD",
            quiet_logs=False,
            polygon_api_key=polygon_api_key,
        )
    else:
        broker = MetaTrader5(
            {
                "login": int(account),
                "password": password,
                "server": server,
            }
        )

        strategy = LiquiditySweep(broker=broker, parameters={"symbol": "EURUSDm"})
        trader = Trader()
        trader.add_strategy(strategy)

        try:
            trader.run_all()
        except KeyboardInterrupt:
            trader.stop_all()


if __name__ == "__main__":
    run()

