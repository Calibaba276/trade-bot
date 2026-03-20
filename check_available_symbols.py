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

# Get all symbols
symbols = mt5.symbols_get()

if symbols is None:
    print("No symbols found")
    mt5.shutdown()
    exit()

print(f"Total symbols available: {len(symbols)}\n")

# Check specific symbols you're interested in
test_symbols = ["APPLm", "NVDAm", "UBERm", "TSLA", "TSLAm", "AAPL", "NVDA"]

print("Checking specific symbols:")
print("-" * 60)
for symbol_name in test_symbols:
    info = mt5.symbol_info(symbol_name)
    if info:
        print(f"✓ {symbol_name:10} - Available | Path: {info.path} | Description: {info.description}")
    else:
        print(f"✗ {symbol_name:10} - NOT FOUND")

print("\n" + "=" * 60)
print("Searching for stock-related symbols (showing first 50):")
print("=" * 60)

# Filter and show stock symbols
stock_count = 0
for symbol in symbols:
    path_lower = symbol.path.lower()
    if "stock" in path_lower or "equity" in path_lower or "share" in path_lower:
        print(f"{symbol.name:15} | {symbol.description:40} | {symbol.path}")
        stock_count += 1
        if stock_count >= 50:
            break

if stock_count == 0:
    print("\nNo stock symbols found. Showing all symbols (first 100):")
    print("-" * 60)
    for i, symbol in enumerate(symbols[:100]):
        print(f"{symbol.name:15} | {symbol.description:40} | {symbol.path}")

mt5.shutdown()
