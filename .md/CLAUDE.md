# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## Critical: Time Zone

**All strategy times are Nigerian Time (NGT, UTC+1).** The broker is configured with `"timezone": "Africa/Lagos"`. Session windows in the code (e.g. `time(1, 0)` to `time(9, 0)` for Asian session) are NGT. Do not convert to UTC or EST — all internal comparisons assume NGT.

> Note: `.github/copilot-instructions.md` incorrectly labels these as EST — that file is outdated. The code and broker config use NGT throughout.

---

## Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Authenticate with Azure (required for all secrets)
az login

# Run EURUSD ICT strategy (backtest or live, determined by ISBACKTESTING vault secret)
python -m backend.runners.eurusd

# Run XAUUSD (Gold) ICT strategy (backtest or live)
python -m backend.runners.xauusd

# Run LiquiditySweep live (MT5)
python -m backend.runners.liquidity_sweep

# Run main entry point (routes based on ISBACKTESTING secret)
python -m backend.runners.main

# Multi-account orchestrator (Azure VM deployment)
python -m backend.services.orchestrator

# Single account worker (spawned by orchestrator, or run manually)
python -m backend.services.worker --account-id <uuid>

# Measure infrastructure latency (Redis, Key Vault, Supabase)
python -m backend.config.latency
```

---

## Architecture

The codebase is organized as a three-layer system with a multi-account execution tier on top.

### Layer 1 — Strategy Definition (`backend/strategies/`)

All strategies inherit from Lumibot's `Strategy` base class. They are pure trading logic:

- `liquidity_sweep.py`: Detects Asian session (01:00–07:00 NGT) high/low, waits for a price sweep, then enters on the reversal swing break. Risk: $25/trade, RR: 3.0.
- `eurusd_model.py`: 8-phase ICT institutional order flow. London session (09:00–11:00 NGT) and NY session (13:00–17:00 NGT). Uses fair value gaps and market structure shifts. Risk: $500/trade, RR: 3.0.
- `xauusd_model.py`: Gold (XAUUSD) variant of the ICT order-flow model. Same sweep → MSS → FVG → OTE structure as `eurusd_model.py`, but tuned for Gold's dollar-denominated scale: stop `buffer` and `min_fvg_size` are in USD (~$0.50) rather than pips, so noise FVGs are filtered out. Symbol: `C:XAUUSD` (backtest) / `XAUUSDm` (live).
- `common.py`: Shared `calculate_quantity()` (risk-based position sizing), `_calculate_take_profit()`, and `_manage_risk_controls()`.

**Position sizing** (always use `calculate_quantity()`):
- Forex: `risk_amount / sl_distance / 100_000`, floored to nearest 0.01 lot
- Stocks: `risk_amount / sl_distance`, floored to whole units

**EURUSDModel uses the Verdict pattern** — it doesn't submit orders directly. Instead it calls `save_verdict()` (Supabase) and `publish_verdict()` (Redis), and workers execute.

### Layer 2 — Execution (`backend/runners/`, `backend/brokers/`)

- **Backtesting**: `PolygonDataBacktesting` via Polygon.io. Symbol format: `EURUSD` (no suffix).
- **Live trading**: Custom `MetaTrader5` broker adapter in `backend/brokers/mt5_broker.py`. Symbol format: `EURUSDm` (with `m` suffix for live accounts).
- Runners pull all secrets from Azure Key Vault at startup and pass them to broker/strategy.

### Layer 3 — Infrastructure (`backend/services/`, `backend/config/`)

**Multi-account execution (VM deployment):**
- `orchestrator.py`: Reads runnable accounts from Supabase `broker_accounts`, spawns one `worker.py` subprocess per account, monitors health with exponential backoff (5–300s), restarts up to 10 times, propagates SIGINT cleanly.
- `worker.py`: Subscribes to Redis `signals` channel. On signal receipt: validates timing, fetches MT5 credentials from Azure Key Vault, connects to MT5, submits order. Runs `PositionMonitor` as a background thread.
- `position_monitor.py`: Polls MT5 every 5s. Moves SL to entry + buffer once unrealized P&L ≥ `rr_ratio × risk`. Halts new trades if daily equity loss exceeds threshold; `HaltFlag` auto-resets at UTC midnight.
- `verdict.py`: `build_verdict()` → `save_verdict()` (Supabase `signals`) → `publish_verdict()` (Redis `signals` channel).
- `frontend_emitter.py`: `emit_candle()` and `emit_trade_event()` write to Supabase `candles` and `trade_events` tables. Called by the strategy; fails silently — never interrupts trading.
- `telegram_notifier.py`: All `notify_*` functions call Telegram Bot API via `requests`. Reads `TELEGRAM-BOT-TOKEN` and `TELEGRAM-CHAT-ID` from Key Vault. Fails silently — does not block execution.
- `publisher.py`: Redis pub/sub wrapper.
- `vault.py`: `VaultClient` wrapping Azure SDK; uses `DefaultAzureCredential` (Managed Identity on VM, `az login` locally). Secrets cached in-process.

**Config:**
- `config/secrets.py`: `get_azure_secret(name)` — all credentials are fetched from `https://calibabasecret.vault.azure.net/`.
- `config/supaclient.py`: Singleton Supabase client (tables: `broker_accounts`, `signals`).
- `config/logger.py`: Rotating file handler (10 MB, 5 backups) + console. Use `logger.info/warning/error` with `[TAG]` prefixes: `[ENTRY]`, `[SWEEP]`, `[ERROR]`, etc.

---

## Secrets (Azure Key Vault)

| Secret | Used by |
|---|---|
| `POLYGON-API-KEY` | Backtesting data |
| `ACCOUNT` | MT5 login ID |
| `PASSWORD` | MT5 password |
| `SERVER` | MT5 server (e.g. `ICMarkets-Demo`) |
| `ISBACKTESTING` | Routes runner to backtest vs live |
| `BACKTESTING-START` / `BACKTESTING-END` | Backtest date range (YYYY-MM-DD) |
| `SUPABASE-URL` / `SUPABASE-KEY` | Database client |
| `REDIS-URL` | Upstash Redis connection string |
| `TELEGRAM-BOT-TOKEN` | Telegram Bot API token (from @BotFather) |
| `TELEGRAM-CHAT-ID` | Telegram user/chat numeric ID |

No `.env` file is used in production. Locally, run `az login` — `DefaultAzureCredential` picks up the CLI token automatically.

---

## Key Patterns

### New strategy

1. Add class to `backend/strategies/` inheriting `lumibot.strategies.strategy.Strategy`
2. Implement `initialize()`, `before_market_opens()`, `on_trading_iteration()`
3. Use `calculate_quantity()` from `common.py` for position sizing
4. Add a runner in `backend/runners/` following the existing backtest/live pattern

### Verdict / worker flow (EURUSDModel)

```
Strategy generates Verdict
  → save_verdict()   → Supabase signals table
  → publish_verdict() → Redis "signals" channel
  → worker.py receives via pub/sub
  → fetches MT5 creds from Key Vault
  → submits order to MT5
```

### MT5 symbol naming

Live trading uses broker-specific suffixes (e.g. `EURUSDm`). Backtest runners use the base symbol (`EURUSD`). Always parameterize the symbol and document which format is expected.
