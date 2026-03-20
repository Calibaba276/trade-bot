import MetaTrader5 as mt5api
from mt5_broker import MetaTrader5
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient

from lumibot.entities import Asset

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

mt5 = MetaTrader5(
    {
        "login": int(ACCOUNT),
        "password": PASSWORD,
        "server": SERVER
    }
)

if __name__ == "__main__":
    symbol = "UBERm"

    # print(mt5.select_symbol(Asset(symbol, asset_type="stock")))
    # print(mt5.get_historical_prices(Asset(symbol, asset_type="stock"), 100, "minute"))

    print(mt5api.symbol_info("AAPLm"))

    last_tick = mt5api.symbol_info_tick(symbol)
    print(f"Last Price: {last_tick.ask}")