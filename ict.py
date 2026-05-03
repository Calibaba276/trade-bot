from lumi_trade import ICTModel
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

ISBACKTESTING = get_azure_secret("ISBACKTESTING")
BACKTESTING_START = get_azure_secret("BACKTESTING-START")
BACKTESTING_END = get_azure_secret("BACKTESTING-END")

POLYGON_API_KEY = get_azure_secret("POLYGON-API-KEY")

ACCOUNT = get_azure_secret("ACCOUNT")
PASSWORD = get_azure_secret("PASSWORD")
SERVER = get_azure_secret("SERVER")

if __name__ == "__main__":
    if 5 > 3:
        start_date = datetime.strptime(BACKTESTING_START, "%Y-%m-%d")
        end_date = datetime.strptime(BACKTESTING_END, "%Y-%m-%d")

        ICTModel.backtest(
        PolygonDataBacktesting,
        start_date,
        end_date,
        parameters={
            "symbol": "C:EURUSD",
            "risk_amount": 500,
            "max_daily_drawdown_pct": 0.02,
            "stop_buffer_pips": 2
        },
        polygon_api_key=POLYGON_API_KEY,
        quiet_logs=False
    )
    else:
        broker = MetaTrader5({
            "login": int(ACCOUNT),
            "password": PASSWORD,
            "server": SERVER,
            "timezone": "Africa/Lagos",
            "path": "C:\\\\Program Files\\\\ICT\\\\terminal64.exe"
        })

        strategy = ICTModel(broker=broker, 
            parameters={
            "symbol": "EURUSDm",
            "risk_amount": 500,
            "max_daily_drawdown_pct": 0.02,
            "stop_buffer_pips": 2
        })

        trader = Trader()
        trader.add_strategy(strategy)

        trader.run_all()
