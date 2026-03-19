import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime
import time

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

def connect_mt5(config):
    if not mt5.initialize():
        raise RuntimeError(" !!! Error >>> MT5 initialize() failed")
    
    authorized = mt5.login(
        login=config.get('login'),
        password=config.get('password'),
        server=config.get('server')
        )

    if not authorized:
        error = mt5.last_error()
        mt5.shutdown() # Close connection if login fails
        raise RuntimeError(f"MT5 Login failed for account {config['login']}: {error}")
        
    print(f"Successfully logged into {config['server']} as {config['login']}")

def shutdown_mt5():
    mt5.shutdown()
    print("MT5 disconnected")

def get_daily_data(symbol="EURUSDm", n=10):
    rates = rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_D1, 0, 10)
    df = pd.DataFrame(rates)
    # df['time'] = pd.to_datetime(df['time'], unit='s')
    return df

def detect_engulfing(df):
    if len(df) < 2:
        return "neutral"
    prev = df.iloc[-2]
    curr = df.iloc[-1]

    if prev['close'] < prev['open'] and curr['close'] > curr['open']:
        if curr['close'] > prev['open'] and curr['open'] < prev['close']:
            return "bullish"
    if prev['close'] > prev['open'] and curr['close'] < curr['open']:
        if curr['open'] > prev['close'] and curr['close'] < prev['open']:
            return "bearish"
    return "neutral"

def place_trade(symbol, signal, df, lot=0.1):
    # signal = "bullish" # !!! using this line just to test the function and MT5 connection
    if signal not in ["bullish", "bearish"]:
        print("No trade signal (neutral) — skipping trade.")
        return

    tick = mt5.symbol_info_tick(symbol)
    price = tick.ask if signal == "bullish" else tick.bid
    order_type = mt5.ORDER_TYPE_BUY if signal == "bullish" else mt5.ORDER_TYPE_SELL

    curr = df.iloc[-1]
    sl_price = curr['low'] if signal == "bullish" else curr['high']
    sl_dist = abs(price - sl_price)
    tp_dist = 2 * sl_dist
    sl = round(price - sl_dist, 5) if signal == "bullish" else round(price + sl_dist, 5)
    tp = round(price + tp_dist, 5) if signal == "bullish" else round(price - tp_dist, 5)

    if not mt5.symbol_select(symbol, True):
        print(f"!!! >>> Failed to select symbol: {symbol}")
        return

    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": lot,
        "type": order_type,
        "price": price,
        "sl": sl,
        "tp": tp,
        "deviation": 10,
        "magic": 234000,
        "comment": f"{signal} engulfing SL/TP",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }

    result = mt5.order_send(request)

    if result.retcode != mt5.TRADE_RETCODE_DONE:
        print(f"Order failed: {result.retcode}")
    else:
        print(f"{signal.capitalize()} trade placed successfully at {price}")
        print(f"SL: {sl} | TP: {tp}")

def run_strategy():
    weekday = datetime.now().weekday()
    # if weekday >= 5:
    #     print("Weekend — skipping execution.")
    #     return

    symbol = "EURUSDm"
    connect_mt5()
    df = get_daily_data(symbol, n=5)
    print(df.tail(2))

    signal = detect_engulfing(df)
    print(f"\\\ Signal: {signal}")

    place_trade(symbol, signal, df)
    shutdown_mt5()

if __name__ == "__main__":
    symbol = "EURUSDm"
    connect_mt5({
            "login": int(ACCOUNT),
            "password": PASSWORD,
            "server": SERVER
        })
    print(get_daily_data(symbol, 10))