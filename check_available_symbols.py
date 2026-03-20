import MetaTrader5 as mt5
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

# Initialize MT5
if not mt5.initialize():
    print(f"MT5 Initialize Failed: {mt5.last_error()}")
    exit()

# Login
authorized = mt5.login(
    login=int(ACCOUNT),
    password=PASSWORD,
    server=SERVER
)

if not authorized:
    error = mt5.last_error()
    mt5.shutdown()
    print(f"MT5 Login failed: {error}")
    exit()

print(f"Successfully logged into {SERVER} as {ACCOUNT}\n")

symbols_to_enable = [
    "AAPLm",   # Apple (NOTE: it's AAPL with 2 P's, not APPL)
    "NVDAm",   # NVIDIA
    "TSLAm",   # Tesla
    "MSFTm",   # Microsoft
    "AMZNm",   # Amazon
    "GOOGLm",  # Google
    "FBm",     # Meta/Facebook
    "AMDm",    # AMD
    # Add more symbols as needed
]

print("Checking and enabling symbols...")
print("=" * 70)

for symbol_name in symbols_to_enable:
    # Check if symbol exists
    info = mt5.symbol_info(symbol_name)
    
    if info is None:
        print(f"✗ {symbol_name:15} - DOES NOT EXIST on this broker")
        continue
    
    # Check if symbol is visible in Market Watch
    if not info.visible:
        print(f"⚠ {symbol_name:15} - Found but NOT visible. Enabling...")
        
        # Enable the symbol
        if mt5.symbol_select(symbol_name, True):
            # Verify it's now visible
            info = mt5.symbol_info(symbol_name)
            if info.visible:
                print(f"✓ {symbol_name:15} - Successfully enabled! Now visible in Market Watch")
            else:
                print(f"✗ {symbol_name:15} - Failed to verify visibility")
        else:
            print(f"✗ {symbol_name:15} - Failed to enable: {mt5.last_error()}")
    else:
        print(f"✓ {symbol_name:15} - Already visible in Market Watch")

print("\n" + "=" * 70)
print("\nVerifying final status...")
print("-" * 70)

for symbol_name in symbols_to_enable:
    info = mt5.symbol_info(symbol_name)
    if info and info.visible:
        tick = mt5.symbol_info_tick(symbol_name)
        if tick:
            print(f"✓ {symbol_name:15} | Bid: {tick.bid:10.2f} | Ask: {tick.ask:10.2f} | {info.description}")
        else:
            print(f"⚠ {symbol_name:15} | Visible but no tick data available")
    elif info:
        print(f"✗ {symbol_name:15} | Exists but NOT visible")
    else:
        print(f"✗ {symbol_name:15} | Does NOT exist on this broker")

print("\n✓ Done! Check your MT5 terminal - symbols should now be visible in Market Watch.")
mt5.shutdown()
