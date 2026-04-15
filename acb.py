import os
from lumi_trade import ACB
from mt5_broker import MetaTrader5
from lumibot.backtesting import PolygonDataBacktesting
from lumibot.traders import Trader

from datetime import datetime

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
    
ACCOUNT = get_azure_secret("ACCOUNT")
PASSWORD = get_azure_secret("PASSWORD")
SERVER = get_azure_secret("SERVER")
POLYGON_API_KEY = get_azure_secret("POLYGON-API-KEY")

ISBACKTESTING = True
backtesting_start = datetime(2025, 5, 1)
backtesting_end = datetime(2025, 12, 31)

if __name__ == "__main__":
    if ISBACKTESTING:
        ACB.backtest(
            PolygonDataBacktesting,
            backtesting_start,
            backtesting_end,
            parameters={"symbol": "C:GBPUSD"},
            polygon_api_key=POLYGON_API_KEY,
            quiet_logs=False,
        )
    else:
        acb = MetaTrader5({
            "login": int(ACCOUNT),
            "password": PASSWORD,
            "server": SERVER,
            "timezone": "Africa/Lagos",
            "path": "C:\\\\Program Files\\\\ACB Strategy\\\\terminal64.exe"
        })

        acbm = ACB(name="ACB Strategy", broker=acb, parameters={"symbol": "GBPUSDm"})

        trader = Trader()
        trader.add_strategy(acbm)

        trader.run_all()
