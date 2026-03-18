import os
from lumi_trade import LiquiditySweep, TrendStrategy
from lumibot.backtesting import PolygonDataBacktesting
from mt5_broker import MetaTrader5
from lumibot.traders import Trader

from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient

VAULT_URL = "https://calibabasecret.vault.azure.net/"
credentials = DefaultAzureCredential()
client = SecretClient(VAULT_URL, credentials)

def get_azure_secret(name):
    """Helper to pull secrets from Azure"""
    try:
        return client.get_secret(name).value
    except Exception as e:
        print(f"Error fetching {name}: {e}")
        return None

from datetime import datetime

ISBACKTESTING = get_azure_secret("ISBACKTESTING")
BACKTESTING_START = get_azure_secret("BACKTESTING-START")
BACKTESTING_END = get_azure_secret("BACKTESTING-END")
POLYGON_API_KEY = get_azure_secret("POLYGON-API-KEY")

ACCOUNT = get_azure_secret("ACCOUNT")
PASSWORD = get_azure_secret("PASSWORD")
SERVER = get_azure_secret("SERVER")

if __name__ == "__main__":
    if 5 < 3:

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
        liquidity_sweep = MetaTrader5({
            "login": int(ACCOUNT),
            "password": PASSWORD,
            "server": SERVER,
            "path": "C:\\\\Program Files\\\\Liquidity Sweep\\\\terminal64.exe"
        })

        trend_strategy = MetaTrader5({
            "login": int(ACCOUNT),
            "password": PASSWORD,
            "server": SERVER,
            "path": "C:\\\\Program Files\\\\Trend Strategy\\\\terminal64.exe"
        })

        ld = LiquiditySweep(name="Liquidity Sweep", broker=liquidity_sweep, parameters={"symbol": "EURUSDm"})
        ts = TrendStrategy(name="Trend Strategy", broker=trend_strategy)

        trader = Trader()
        trader.add_strategy(ld)
        trader.add_strategy(ts)

        try:
            trader.run_all()
        except KeyboardInterrupt:
            trader.stop_all()