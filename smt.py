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
            backtesting_start,
            backtesting_end,
            parameters = {
                "symbol_nq": "QQQ",
                "symbol_ym": "DIA",
                "risk_per_trade": 500,
                "ratio": 2,  # 2:1 risk-reward ratio
                "max_position_value": 5000,  # Maximum $5000 per position
                "trades_per_day": 3
            },
            polygon_api_key=POLYGON_API_KEY,
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

        smtm = SMTDivergence(name="SMT Divergence", broker=smt, 
        parameters = {
            "symbol_nq": "NAS100",
            "symbol_ym": "US30",
            "risk_per_trade": 500, 
            "ratio": 2,
            "max_position_value": 5000,
            "trades_per_day": 3
            }
        
        )

        trader = Trader()
        trader.add_strategy(smtm)

        trader.run_all()
