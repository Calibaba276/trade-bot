from datetime import datetime
from pathlib import Path
import sys

from lumibot.backtesting import PolygonDataBacktesting
from lumibot.traders import Trader

if __package__ is None or __package__ == "":
    project_root = Path(__file__).resolve().parents[2]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

from backend.brokers.mt5_broker import MetaTrader5
from backend.config.secrets import get_azure_secret
from backend.strategies.ict_model import ICTModel


def run():
    is_backtesting = get_azure_secret("ISBACKTESTING")
    backtesting_start = get_azure_secret("BACKTESTING-START")
    backtesting_end = get_azure_secret("BACKTESTING-END")

    polygon_api_key = get_azure_secret("POLYGON-API-KEY")

    account = get_azure_secret("ACCOUNT")
    password = get_azure_secret("PASSWORD")
    server = get_azure_secret("SERVER")

    if str(is_backtesting).lower() == "true":
        start_date = datetime.strptime(backtesting_start, "%Y-%m-%d")
        end_date = datetime.strptime(backtesting_end, "%Y-%m-%d")

        ICTModel.backtest(
            PolygonDataBacktesting,
            start_date,
            end_date,
            parameters={
                "symbol": "C:EURUSD",
                "risk_amount": 500,
                "max_daily_drawdown_pct": 0.02,
                "stop_buffer_pips": 2,
            },
            polygon_api_key=polygon_api_key,
            quiet_logs=False,
        )
    else:
        broker = MetaTrader5(
            {
                "login": int(account),
                "password": password,
                "server": server,
                "timezone": "Africa/Lagos",
                "path": "C:\\Program Files\\ICT\\terminal64.exe",
            }
        )

        strategy = ICTModel(
            broker=broker,
            parameters={
                "symbol": "EURUSDm",
                "risk_amount": 500,
                "max_daily_drawdown_pct": 0.02,
                "stop_buffer_pips": 2,
            },
        )

        trader = Trader()
        trader.add_strategy(strategy)
        trader.run_all()


if __name__ == "__main__":
    run()
