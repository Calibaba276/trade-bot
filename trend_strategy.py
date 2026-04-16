from lumi_trade import TrendStrategy
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
    
ACCOUNT = get_azure_secret("ACCOUNT")
PASSWORD = get_azure_secret("PASSWORD")
SERVER = get_azure_secret("SERVER")

if __name__ == "__main__":
    trend_strategy = MetaTrader5({
            "login": int(ACCOUNT),
            "password": PASSWORD,
            "server": SERVER,
            "timezone": "Africa/Lagos",
            "path": "C:\\\\Program Files\\\\Trend Strategy\\\\terminal64.exe"
        })

    
    ts = TrendStrategy(
        name="Trend Strategy", 
        broker=trend_strategy,
        parameters={
            "risk_amount": 500,
            "rr_ratio": 2,
            "stop_loss_percent": 0.02,
            "max_daily_drawdown_pct": 0.02
        }
    )

    trader = Trader()
    trader.add_strategy(ts)

    trader.run_all()