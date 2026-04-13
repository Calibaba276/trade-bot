# Copilot Instructions for Trade Bot

## ⚠️ CRITICAL: Nigerian Time (UTC+1) - Read First

**ALL times in backtesting results, strategy logs, and code are in Eastern Standard Time EST, NOT UTC.**

When backtesting shows timestamps or analyzing logs:
- Asian Session (07:00 PM -04:00 AM EST)
- London Session (03:00 AM - 12:00 PM EST)  
- New York Session (8:00 AM - 5:00 PM EST)

**Example backtest log:**
```
[ASIAN SESSION] High: 1.0950, Low: 1.0820
[DAILY STRUCTURE] High: 1.0980, Low: 1.0800
[BULLISH ENTRY] Entry: 1.0840 @ 09:15 NGT
```

All those times are **Eastern Standard Time not UTC.** When the strategy checks `if current_time >= time(1, 0)`, it's comparing against 01:00 EST.

---

## Quick Start

**Install dependencies:**
```bash
pip install -r requirements.txt
```

**Run backtests:**
```bash
python ict.py                          # ICT 2022 strategy (EURUSD)
python smt.py                          # SMT divergence strategy
```

**Live trading:**
```bash
python main.py                         # Runs LiquiditySweep or TrendStrategy
python liquidity_sweep.py              # LiquiditySweep live (MT5)
python trend_strategy.py               # TrendStrategy live (MT5)
```

**Quick test:**
```bash
python tester.py                       # Test MT5 broker connection
```

---

## Architecture Overview

### Three-Layer Design

**1. Strategy Definition Layer** (`lumi_trade.py`)
- All trading strategies as classes inheriting from `lumibot.strategies.strategy.Strategy`
- Five implemented strategies: `LiquiditySweep`, `TrendStrategy`, `ACB`, `SMTDivergence`, `ICTModel`
- Each strategy implements: `initialize()`, `on_trading_iteration()`, helper methods
- Shared helper: `calculate_quantity()` for position sizing based on risk

**2. Execution Layer**
- **Backtesting**: `ict.py`, `smt.py` use `PolygonDataBacktesting` (Polygon.io data)
- **Live Trading**: `main.py`, `liquidity_sweep.py`, `trend_strategy.py` use custom `MetaTrader5` broker
- **Support**: `fetch_trends.py` (NewsAPI + Gemini AI), `mt5_broker.py` (MT5 wrapper), `tester.py` (utilities)

**3. Infrastructure Layer**
- **Secrets**: Azure Key Vault (`get_azure_secret()` in every runner)
- **Data**: Polygon.io API for backtesting
- **Broker**: MetaTrader5 with custom Lumibot broker adapter

### Data Flow: Backtest Example

```
Polygon.io (historical data)
    ↓
PolygonDataBacktesting
    ↓
Strategy.backtest() execution
    ↓
on_trading_iteration() called repeatedly
    ↓
Orders created/submitted
    ↓
Results logged + statistics
```

---

## Key Conventions

### Time Zone: Eastern Standard Time (EST)

**All strategies use Eastern Standard Time throughout.** This is critical for:
- Session identification: Asian (07:00 PM -04:00 AM EST), London (03:00 AM - 12:00 PM EST), NY (8:00 AM - 5:00 PM EST)
- Time-based entry/exit rules
- Backtesting results

Example:
```python
current_time = dt.time()
if current_time >= time(1, 0) and current_time < time(9, 0):
    # This is Asian session in NGT
    self._identify_asian_session_structure()
```

### Strategy Class Template

```python
class NewStrategy(Strategy):
    def initialize(self):
        # Get params, create assets, set flags
        self.symbol = self.parameters.get("symbol")
        self.asset = Asset(symbol=self.symbol, asset_type="forex")
        self.risk_amount = self.parameters.get("risk_amount", 25)
        self.sleeptime = "5M"  # or "1M"
        self.set_market("24/7")  # or "24/5"
        
    def before_market_opens(self):
        # Reset daily state
        self.traded_today = False
        
    def on_trading_iteration(self):
        # Main loop - called every sleeptime interval
        dt = self.broker.get_datetime()
        current_time = dt.time()
        # ... analysis and trading logic
        
    def _helper_method(self):
        # Private analysis methods
        pass
```

### Risk Management Pattern

**Always use `calculate_quantity()`** for position sizing:

```python
def calculate_quantity(self, asset, stop_loss=None):
    """Calculate position size based on stop loss distance"""
    price = self.get_last_price(asset)
    
    if stop_loss is not None:
        sl_distance = abs(price - stop_loss)
        raw_quantity = self.risk_amount / sl_distance
        
        if asset.asset_type == "forex":
            # Forex: divide by 100k (standard lot = 100k units)
            quantity = raw_quantity / 100000
            final_qty = round(math.floor(quantity / 0.01) * 0.01, 2)
        else:
            # Stocks: floor the quantity
            final_qty = math.floor(raw_quantity)
    else:
        final_qty = self.risk_amount / price
    
    return final_qty if final_qty > 0 else 0
```

Default risk: `$500 per trade`. Configurable via `parameters={"risk_amount": 50}`.

### Data Fetching Pattern

```python
# Get historical bars
df = self.get_historical_prices(self.asset, lookback_bars, "minute")

# Always check validity
if df is None or df.empty:
    return

# Extract OHLC
closes = df["close"].values
highs = df["high"].values
lows = df["low"].values
```

### Order Creation Pattern

```python
# Market order
order = self.create_order(self.symbol, quantity, "buy", order_type="market")

# Limit + Stop
order = self.create_order(
    self.symbol, quantity, "buy",
    limit_price=entry_price,
    stop_price=stop_loss
)

# Submit and log
self.submit_order(order)
self.log_message(f"[ENTRY] BUY {self.symbol} @ {entry_price}")
```

### Logging Conventions

Use `[TAG]` prefix for clarity:

```python
self.log_message(f"[ENTRY] BUY EURUSD @ 1.0850, SL: 1.0730")
self.log_message(f"[SWEEP] Price broke above Asian high 1.0950")
self.log_message(f"[ERROR] Could not fetch data")
```

### Secrets Management

All credentials pulled from Azure Key Vault at runtime:

```python
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient

VAULT_URL = "https://calibabasecret.vault.azure.net/"
client = SecretClient(VAULT_URL, DefaultAzureCredential())

def get_azure_secret(name):
    try:
        return client.get_secret(name).value
    except Exception as e:
        print(f"Error fetching {name}: {e}")
        return None

POLYGON_API_KEY = get_azure_secret("POLYGON-API-KEY")
```

---

## Trading Strategy Patterns

### Market Structure Shift (MSS) Pattern
Used in LiquiditySweep and ICTModel:

1. Identify session range (high/low)
2. Detect liquidity sweep (price breaks range)
3. Identify swing point on reversal
4. Enter on break of swing point
5. Stop loss at opposite end of structure

### Institutional Order Flow Pattern
Used in SMTDivergence and ICTModel:

1. Analyze two correlated assets (e.g., QQQ vs DIA)
2. Find swing divergence (one extremes, other doesn't)
3. Signals institutional manipulation
4. Trade on expected reversal
5. Use risk:reward ratio (typically 1:1.5 or 1:2)

### Sentiment-Based Pattern
Used in TrendStrategy:

1. Fetch news via NewsAPI
2. Analyze sentiment via Gemini AI
3. Generate buy/sell signals (score thresholds)
4. Scalable across multiple tickers
5. Daily trade limits configurable

---

## Strategy Implementation Details

### Five Implemented Strategies

**1. LiquiditySweep** (`lumi_trade.py:28`)
- Watches Asian session high/low for sweeps
- Enters on reversal into swing points
- Best for forex (EURUSD, GBPUSD, etc.)
- Risk: $25/trade, configurable

**2. TrendStrategy** (`lumi_trade.py:144`)
- AI-powered sentiment analysis
- Requires NewsAPI + Gemini API keys
- Scalable multi-ticker
- Sentiment threshold: >0.7 buy, <-0.5 sell

**3. ACB** (`lumi_trade.py:204`)
- Daily reversal detection ("green" vs "red" days)
- Intraday range breakout
- Coil identification in last 60 minutes
- One trade/day, specific hours only (14:00-16:30 NGT)

**4. SMTDivergence** (`lumi_trade.py:254`)
- Two-asset divergence detection (NQ vs YM)
- Identifies institutional manipulation
- Risk per trade: $500, configurable
- Risk:Reward: 2:1, configurable
- Killzone hours only (NY 13:30-16:00, London 07:00-10:00)

**5. ICTModel** (`lumi_trade.py:304`)
- 8-phase institutional framework
- Order blocks, fair value gaps, premium/discount zones
- Asian session foundation (01:00-09:00 NGT)
- Liquidity sweep detection + reversal entries
- Risk:Reward: 1:1.5, configurable

---

## Backtest Runners: Pattern and Extension

### Single-Strategy Backtest Pattern

```python
# Example: ict.py
from lumi_trade import ICT2022Strategy
from lumibot.backtesting import PolygonDataBacktesting
from datetime import datetime

Strategy.backtest(
    PolygonDataBacktesting,
    datetime(2024, 1, 1),
    datetime(2024, 12, 31),
    parameters={
        "symbol": "EURUSD",
        "risk_amount": 25,
        "risk_reward_ratio": 1.5
    },
    polygon_api_key=POLYGON_API_KEY,
    quiet_logs=False
)
```

**To add a new backtest runner:**
1. Create `new_strategy.py` in root
2. Import strategy from `lumi_trade.py`
3. Use `PolygonDataBacktesting` framework
4. Call `Strategy.backtest()` with parameters
5. Include Azure vault integration for secrets

---

## Live Trading: MT5 Broker Integration

### MetaTrader5 Broker Adapter

Custom Lumibot broker at `mt5_broker.py` provides:
- Order execution via MT5 API
- Position tracking
- Breakeven stop management
- Daily drawdown limits
- Tick-by-tick data fetching

### Live Trading Pattern

```python
from mt5_broker import MetaTrader5
from lumibot.traders import Trader

broker = MetaTrader5({
    "login": int(ACCOUNT),
    "password": PASSWORD,
    "server": SERVER,
    "timezone": "Africa/Lagos"
})

strategy = LiquiditySweep(
    broker=broker,
    parameters={"symbol": "EURUSDm"}  # Note: 'm' suffix for MT5
)

trader = Trader()
trader.add_strategy(strategy)
trader.run_all()
```

**Important:**
- MT5 symbol format: `EURUSDm` (with suffix)
- Polygon backtest format: `EURUSD` (without suffix)
- Timezone always: `"Africa/Lagos"` for Nigerian Time

---

## Configuration & Secrets

### Required Azure Key Vault Secrets

```
POLYGON-API-KEY        # For backtesting data
ACCOUNT                # MT5 login ID
PASSWORD               # MT5 password
SERVER                 # MT5 server name
NEWS-API-KEY           # For TrendStrategy
GEMINI-API-KEY         # For TrendStrategy
ISBACKTESTING          # Boolean flag
BACKTESTING-START      # Start date (YYYY-MM-DD)
BACKTESTING-END        # End date (YYYY-MM-DD)
```

### Environment Setup

1. Install dependencies: `pip install -r requirements.txt`
2. Authenticate with Azure: `az login`
3. Ensure credentials have Key Vault access
4. (Optional) Create `.env` file with secrets (ignored by git)

---

## Testing & Validation

### Verify Installation

```bash
python tester.py  # Test MT5 connection (if available)
```

### Test a Single Backtest

```bash
python ict.py single EURUSD
```

This runs one iteration to verify:
- Data source connectivity (Polygon.io)
- Strategy initialization
- Order creation
- Logging output

### Full Backtest Suite

```bash
python ict.py multi
python smt.py
```

---

## Common Development Tasks

### Add a New Strategy

1. **Define class in `lumi_trade.py`:**
   ```python
   class MyStrategy(Strategy):
       def initialize(self): ...
       def on_trading_iteration(self): ...
   ```

2. **Create backtest runner (e.g., `my_strategy.py`):**
   ```python
   from lumi_trade import MyStrategy
   from lumibot.backtesting import PolygonDataBacktesting
   
   MyStrategy.backtest(PolygonDataBacktesting, ...)
   ```

3. **Test with:** `python my_strategy.py`

4. **Validate:** Check TRADING_KNOWLEDGE_BASE.md for patterns

### Modify Risk Management

Change default risk per trade:
```python
self.risk_amount = self.parameters.get("risk_amount", 50)  # Change from 25 to 50
```

Or pass at runtime:
```python
parameters={"risk_amount": 100}
```

### Add Time Zone Logic

Always use Nigerian Time (UTC+1):
```python
current_time = dt.time()
if current_time >= time(1, 0) and current_time < time(9, 0):
    # Asian session in Nigerian Time
```

### Debug Strategy Behavior

Enable verbose logging:
```python
self.log_message(f"[DEBUG] Variable value: {variable}")
```

Check backtest output (search for `[TAG]` in logs).

---

## References

**Strategy Implementation:** See `TRADING_KNOWLEDGE_BASE.md` for detailed patterns, technical analysis methods, and code quality standards.

**Key Framework:** Lumibot (v4.4.52+) - backtesting and live trading framework

**Data Source:** Polygon.io - professional-grade market data

**Broker:** MetaTrader5 - via custom adapter in `mt5_broker.py`

---

## File Structure Quick Reference

```
trade-bot/
├── lumi_trade.py              # All strategy classes
├── ict.py                      # ICT 2022 backtest runner
├── smt.py                      # SMT backtest runner
├── main.py                     # Main entry point
├── mt5_broker.py               # MT5 broker adapter
├── fetch_trends.py             # AI trend analysis
├── liquidity_sweep.py          # LiquiditySweep live
├── trend_strategy.py           # TrendStrategy live
├── tester.py                   # Testing utility
├── requirements.txt            # Dependencies
├── TRADING_KNOWLEDGE_BASE.md   # Detailed patterns & conventions
└── .github/
    └── copilot-instructions.md # This file
```
