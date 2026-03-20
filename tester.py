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
    sym = "AAPLm"  # replace with exact symbol from your account
    info = mt5.symbol_info(sym)
    if info is None:
       print("Wrong symbol")
    elif not info.visible:
       mt5.symbol_select(sym, True)

    tick = mt5.symbol_info_tick(sym)
    print(tick, mt5.last_error())