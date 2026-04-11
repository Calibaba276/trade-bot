"""
ICT 2022 Strategy Backtest Script
Inner Circle Trader 2022 Model - Backtesting with Nigerian Time (UTC+1)

This script runs a backtest of the ICT2022Strategy using Polygon Data
"""

import os
from lumi_trade import ICT2022Strategy
from lumibot.backtesting import PolygonDataBacktesting
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

POLYGON_API_KEY = get_azure_secret("POLYGON-API-KEY")

def backtest_single_pair(symbol, start_date, end_date):
    """Backtest ICT 2022 Strategy on a single currency pair"""
    
    print(f"\n{'='*80}")
    print(f"ICT 2022 STRATEGY BACKTEST - {symbol}")
    print(f"Period: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
    print(f"Time Zone: Nigerian Time (UTC+1)")
    print(f"{'='*80}\n")
    
    ICT2022Strategy.backtest(
        PolygonDataBacktesting,
        start_date,
        end_date,
        parameters={
            "symbol": symbol,
            "risk_amount": 500,
            "risk_reward_ratio": 1.2,
            "max_positions": 1
        },
        polygon_api_key=POLYGON_API_KEY,
        quiet_logs=False
    )


def backtest_multiple_pairs(start_date, end_date):
    """Backtest ICT 2022 Strategy on multiple currency pairs"""
    
    # Major currency pairs for forex
    pairs = [
        "EURUSD",  # Euro/US Dollar
        "GBPUSD",  # British Pound/US Dollar
        "USDJPY",  # US Dollar/Japanese Yen
        "AUDUSD",  # Australian Dollar/US Dollar
    ]
    
    print(f"\n{'='*80}")
    print(f"ICT 2022 STRATEGY MULTI-PAIR BACKTEST")
    print(f"Period: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
    print(f"Time Zone: Nigerian Time (UTC+1)")
    print(f"{'='*80}\n")
    
    results = {}
    
    for pair in pairs:
        print(f"\n[{pair}] Backtesting in progress...")
        
        try:
            ICT2022Strategy.backtest(
                PolygonDataBacktesting,
                start_date,
                end_date,
                parameters={
                    "symbol": pair,
                    "risk_amount": 500,
                    "risk_reward_ratio": 1.2,
                    "max_positions": 1
                },
                polygon_api_key=POLYGON_API_KEY,
                quiet_logs=True  # Suppress verbose output for multiple pairs
            )
            print(f"✓ {pair} backtest completed successfully")
            results[pair] = "COMPLETED"
        
        except Exception as e:
            print(f"✗ {pair} backtest failed: {str(e)}")
            results[pair] = f"ERROR: {str(e)}"
    
    print(f"\n{'='*80}")
    print("BACKTEST SUMMARY")
    print(f"{'='*80}")
    for pair, status in results.items():
        print(f"{pair:<10} : {status}")
    print(f"{'='*80}\n")


if __name__ == "__main__":
    import sys
    
    print("\n" + "█"*80)
    print("█ ICT 2022 STRATEGY BACKTEST RUNNER")
    print("█ Inner Circle Trader 2022 Model")
    print("█ Times displayed in Nigerian Time (UTC+1)")
    print("█ Data Source: Polygon.io")
    print("█"*80)
    
    # Backtest date range
    backtesting_start = datetime(2025, 5, 1)
    backtesting_end = datetime(2025, 12, 31)
    
    # Parse command line arguments
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()
        
        if command == "single":
            # Single pair backtest
            symbol = sys.argv[2] if len(sys.argv) > 2 else "EURUSD"
            backtest_single_pair(symbol, backtesting_start, backtesting_end)
        
        elif command == "multi":
            # Multi-pair backtest
            backtest_multiple_pairs(backtesting_start, backtesting_end)
        
        elif command == "custom":
            # Custom date range
            if len(sys.argv) < 5:
                print("Usage: python ict.py custom SYMBOL START_DATE END_DATE")
                print("Example: python ict.py custom EURUSD 2025-05-01 2025-12-31")
                sys.exit(1)
            
            symbol = sys.argv[2]
            try:
                start = datetime.strptime(sys.argv[3], "%Y-%m-%d")
                end = datetime.strptime(sys.argv[4], "%Y-%m-%d")
                backtest_single_pair(symbol, start, end)
            except ValueError:
                print("Invalid date format. Use YYYY-MM-DD")
                sys.exit(1)
        
        else:
            print("Unknown command. Usage:")
            print("  python ict.py single [SYMBOL]     - Backtest single pair (default: EURUSD)")
            print("  python ict.py multi                - Backtest multiple pairs")
            print("  python ict.py custom SYMBOL START END - Custom date range")
            sys.exit(1)
    
    else:
        # Default: single pair (EURUSD)
        print(f"\nRunning default single pair backtest (EURUSD)")
        print(f"Period: {backtesting_start.strftime('%Y-%m-%d')} to {backtesting_end.strftime('%Y-%m-%d')}")
        backtest_single_pair("EURUSD", backtesting_start, backtesting_end)
