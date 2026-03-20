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
    symbol = "AAPLm"
    selected = mt5api.symbol_select(symbol, True)
    if not selected:
        print(f"Failed to select {symbol}, error code =", mt5api.last_error())
        quit()

    # 3. Get symbol info
    symbol_info = mt5api.symbol_info(symbol)
    if symbol_info is None:
        print(f"{symbol} not found")
        quit()
    else:
        print(f"Symbol: {symbol_info.name}, {symbol_info.description}")

    # 4. Get last tick data
    last_tick = mt5api.symbol_info_tick(symbol)
    print(f"Last Price: {last_tick.ask}")