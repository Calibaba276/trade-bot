import os
from lumi_trade import SMTDivergence
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
        SMTDivergence.backtest(
            PolygonDataBacktesting,
            polygon_api_key=POLYGON_API_KEY,
            backtesting_start,
            backtesting_end,
            parameters = {"symbol_nq": "NQ", "symbol_ym": "YM"},
            quiet_logs=False
        )
    else:
        smt = MetaTrader5({
            "login": int(ACCOUNT),
            "password": PASSWORD,
            "server": SERVER,
            "timezone": "Africa/Lagos",
            "path": "C:\\\\Program Files\\\\SMT Divergence\\\\terminal64.exe"
        })

        smtm = SMTDivergence(name="SMT Divergence", broker=smt, parameters = {"symbol_nq": "NQ", "symbol_ym": "YM", "risk_per_trade": 500, "ratio": 2})

        trader = Trader()
        trader.add_strategy(smtm)

        trader.run_all()
