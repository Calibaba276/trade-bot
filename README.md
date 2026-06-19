# trade-bot — Glass Box Trading Engine

An automated forex trading system built on the ICT (Inner Circle Trader) institutional order-flow model, paired with a real-time "Glass Box" dashboard that lets you watch every pattern detection, entry, and exit as it happens — or replay any past session candle-by-candle.

---

## What it does

| Layer | What it is |
|-------|-----------|
| **Strategy** | ICT model running on MetaTrader 5 — detects FVG, MSS, OB, BOS patterns across London and New York sessions, then builds and publishes trade signals |
| **Execution** | Per-account workers subscribe to signals via Redis and submit orders to MT5 with breakeven management and daily drawdown protection |
| **Dashboard** | React frontend connected to Supabase — streams live trade events in real time or replays historical sessions on an interactive chart with pattern overlays |
| **Telegram** | Real-time push notifications to your Telegram bot — signals, order fills/rejections, drawdown halts, and worker status, no VM access required |

---

## Repository layout

```
trade-bot/
├── backend/                  # Python trading engine
│   ├── brokers/              # MetaTrader 5 Lumibot adapter
│   ├── config/               # Azure Key Vault client, Supabase client, logger, latency probe
│   ├── runners/              # Entry points: ict.py, liquidity_sweep.py, main.py
│   ├── services/             # orchestrator, worker, position_monitor, verdict, frontend_emitter, telegram_notifier
│   └── strategies/           # EURUSDModel, LiquiditySweep, common utilities
├── frontend/                 # React TypeScript dashboard
│   ├── src/
│   │   ├── components/       # Chart, Layout, Controls, EventLog, Auth, Marketing
│   │   ├── hooks/            # useAuth, useLiveTradeEvents, useReplaySession,
│   │   │                     #   useKeyboardShortcuts, usePerformanceStats,
│   │   │                     #   useSessionSummaries, useTrades, useMarketStatus,
│   │   │                     #   useOnboarding
│   │   ├── pages/            # Landing, Dashboard, SharePage + dashboard sub-pages
│   │   │                     #   (Overview, FeedPage, ChartPage, TradesPage,
│   │   │                     #    PropFirmPage, SettingsPage)
│   │   ├── store/            # Zustand replay store
│   │   ├── types/            # TradeEvent, Candle, ReplaySession, BrokerAccount …
│   │   └── utils/            # patternRenderer (canvas overlay)
│   ├── e2e/                  # Playwright end-to-end tests
│   └── src/__tests__/        # Vitest unit tests
└── supabase/
    └── migrations/           # SQL schema applied to Supabase (three migrations)
```

---

## Prerequisites

### Backend

| Requirement | Notes |
|-------------|-------|
| Python 3.10 | See `.python-version` |
| Windows machine | MetaTrader 5 only runs on Windows |
| MetaTrader 5 terminal | Installed at `C:\Program Files\ICT\terminal64.exe` by default |
| Azure subscription | Key Vault holds all secrets — no `.env` file used |
| Azure CLI | Run `az login` locally; Managed Identity used on a VM |
| Upstash Redis | For signal pub/sub between strategy and workers |

### Frontend

| Requirement | Notes |
|-------------|-------|
| Node.js ≥ 18 | Any recent LTS works |
| Supabase project | Free tier is fine for development |

---

## Backend setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Authenticate with Azure

```bash
az login
```

`DefaultAzureCredential` picks up the CLI token automatically. On a VM, use Managed Identity instead.

### 3. Configure Azure Key Vault secrets

All secrets are stored in `https://calibabasecret.vault.azure.net/`. Create each one via the Azure Portal or CLI:

| Secret name | Value |
|-------------|-------|
| `SUPABASE-URL` | Your Supabase project URL |
| `SUPABASE-KEY` | Supabase **service role** key (never the anon key) |
| `REDIS-URL` | Upstash Redis connection string (`rediss://…`) |
| `ACCOUNT` | MT5 account login number |
| `PASSWORD` | MT5 account password |
| `SERVER` | MT5 server name (e.g. `ICMarkets-Demo`) |
| `ISBACKTESTING` | `"true"` for backtest, `"false"` for live |
| `BACKTESTING-START` | Start date for backtest, `YYYY-MM-DD` |
| `BACKTESTING-END` | End date for backtest, `YYYY-MM-DD` |
| `POLYGON-API-KEY` | Polygon.io key for backtest OHLCV data |
| `TELEGRAM-BOT-TOKEN` | Token from @BotFather (e.g. `7123456789:AAHxxxxxx…`) |
| `TELEGRAM-CHAT-ID` | Your Telegram user/chat ID (numeric) |

#### Setting up Telegram notifications

1. Message **@BotFather** on Telegram → `/newbot` → copy the token into `TELEGRAM-BOT-TOKEN`
2. Start a conversation with your new bot, then open `https://api.telegram.org/bot<TOKEN>/getUpdates` and grab the `"id"` field from the `"chat"` object → put it in `TELEGRAM-CHAT-ID`
3. Add both secrets to the vault via CLI:
   ```bash
   az keyvault secret set --vault-name calibabasecret --name TELEGRAM-BOT-TOKEN --value "<token>"
   az keyvault secret set --vault-name calibabasecret --name TELEGRAM-CHAT-ID --value "<chat_id>"
   ```
4. Restart the worker — you will receive a 🟢 **WORKER ONLINE** message confirming it works

You will then receive messages for:
- 🟢 / 🔴 Signal generated (pair, direction, entry/SL/TP, scenario)
- ✅ Order placed at broker (lots, fill price, latency)
- ⚠️ Order rejected (error code and reason)
- 🚨 Drawdown halt triggered (balance, loss %, limit %)
- 🟢 / 🔴 Worker online / offline

### 4. Supabase: set `user_id` on broker accounts

The frontend dashboard uses row-level security filtered by `user_id`. After signing up in the dashboard, find your user UUID in Supabase Auth → Users, then update the account row:

```sql
update public.broker_accounts
set user_id = '<your-auth-user-uuid>'
where account_number = '<your-mt5-login>';
```

---

## Running the backend

> **All times are Nigerian Time (NGT = UTC+1).** Session windows in the code (London 09:00–11:00, NY 13:00–17:00) are NGT. The broker is configured with `Africa/Lagos`.

```bash
# ICT strategy — backtest or live, determined by ISBACKTESTING vault secret
python -m backend.runners.eurusd

# Multi-account orchestrator (reads all active accounts from Supabase, spawns workers)
python -m backend.services.orchestrator

# Single account worker (spawned automatically by orchestrator, or run manually)
python -m backend.services.worker --account-id <broker_accounts.id>

# Measure infrastructure latency (Redis, Key Vault, Supabase)
python -m backend.config.latency
```

### How signals flow

```
EURUSDModel.on_trading_iteration()
  └── detects FVG / MSS / OB pattern
      ├── emits trade_event to Supabase  ← frontend reads this
      ├── emits candle OHLCV to Supabase ← frontend reads this
      └── build_verdict()
          ├── save_verdict()  → Supabase `signals` table
          ├── notify_signal() → Telegram 🟢/🔴 SIGNAL message
          └── publish_verdict() → Redis "signals" channel
                └── worker.py receives signal
                    ├── submits order to MetaTrader 5
                    ├── notify_order_filled()  → Telegram ✅ ORDER PLACED
                    └── notify_order_rejected() → Telegram ⚠️ ORDER REJECTED

position_monitor.py (background thread)
  └── daily drawdown breached
      └── notify_drawdown_halt() → Telegram 🚨 DRAWDOWN HALT
```

---

## Frontend setup

### 1. Install dependencies

```bash
cd frontend
npm install
```

### 2. Create your environment file

```bash
cp .env.local.example .env.local
```

Edit `.env.local` and fill in:

```
VITE_SUPABASE_URL=https://<your-project-ref>.supabase.co
VITE_SUPABASE_ANON_KEY=<your-anon-key>
```

Use the **anon (publishable) key** here — never the service role key. Row-level security handles data isolation.

### 3. Apply the database migrations

Three migration files live under `supabase/migrations/`. Run them all at once with the Supabase CLI:

```bash
# With the Supabase CLI (recommended)
supabase db push

# Or paste each SQL file directly in the Supabase SQL editor
```

| Migration file | What it creates |
|---------------|----------------|
| `20260612000000_glassbox_frontend_schema.sql` | `candles`, `trade_events`, `replay_sessions`, `signals`; adds `user_id` to `broker_accounts`; enables Realtime |
| `20260617000000_user_onboarding.sql` | `user_onboarding` — wizard step + completion flag, synced across devices |
| `20260618000000_shared_sessions.sql` | `shared_sessions` — immutable audit snapshots for public share links |

### 4. Start the dev server

```bash
npm run dev
# → http://localhost:5173
```

Sign up at `/signup`, then log in. The onboarding wizard runs on first login. The dashboard loads immediately — candles and events appear once the ICT strategy starts emitting data.

---

## Dashboard features

| Feature | How to use |
|---------|-----------|
| **Live mode** | Click `● LIVE` in the topbar (or press `L`) — chart follows real-time events from Supabase Realtime |
| **Replay mode** *(Pro)* | Press `L` to switch — scrub with the slider or keyboard, step candle-by-candle through any past session |
| **Chart overlays** | FVG boxes (amber), OB zones (blue), MSS lines (teal), BOS lines (purple), entry ▼ / exit ▲ pins |
| **Context Cascade** | Strip below chart header shows latest pattern on each parent timeframe (1m → 5m → 15m → 1h) |
| **Markets panel** | Click any pair to switch; click `‹` to collapse |
| **Event log** | Granular pattern detections + entries/exits with timestamps; collapses with `›` |
| **Trade history** | Sortable table with scenario, entry price, SL, TP, P&L, and status |
| **Prop Firm panel** *(Pro)* | Daily drawdown tracker, consecutive-loss counter, profit-target progress, halt status |
| **Performance dashboard** | Monthly P&L, win rate, average R, consecutive wins/losses |
| **Share audit link** | Export any session as a tamper-proof public link — recipients see the exact snapshot at `/share/:uuid`, no login required |

### Keyboard shortcuts

| Key | Action |
|-----|--------|
| `Space` | Play / Pause (replay mode) |
| `←` / `→` | Step one candle back / forward |
| `Home` / `End` | Jump to start / end of date range |
| `L` | Toggle Live / Replay |
| `1` | Switch to 1m timeframe |
| `5` | Switch to 5m timeframe |
| `F` | Switch to 15m timeframe |
| `H` | Switch to 1h timeframe |

Hover the `?` button in the topbar to see this list at any time.

---

## Database schema

| Table | RLS | Description |
|-------|-----|-------------|
| `broker_accounts` | `auth.uid() = user_id` | MT5 account credentials per user |
| `candles` | `auth.uid() = user_id` | OHLCV market data per pair/timeframe |
| `trade_events` | `auth.uid() = user_id` | Pattern detections, entries, exits; published to Supabase Realtime |
| `signals` | service role write / worker read | Verdicts built by the strategy and consumed by workers |
| `replay_sessions` | `auth.uid() = user_id` | Persists scrub position and playback speed |
| `user_onboarding` | `auth.uid() = user_id` | Wizard step index and completion flag, synced across devices |
| `shared_sessions` | public read / owner insert+delete | Immutable audit snapshots — anyone can read by UUID; only the owner can create or revoke |

---

## Testing

### Unit tests (Vitest)

```bash
cd frontend
npm test          # run once
npm run test:watch  # watch mode
```

Covers: Zustand store actions, `usePerformanceStats` calculations, Context Cascade parent-timeframe logic.

### End-to-end tests (Playwright)

```bash
cd frontend
npm run test:e2e  # starts dev server automatically, runs Chromium
```

Covers: login page UI, signup form, unauthenticated redirect.

---

## Tech stack

### Backend

| Library | Purpose |
|---------|---------|
| [Lumibot](https://lumibot.lumiwealth.com/) | Strategy framework and backtesting engine |
| [MetaTrader5](https://www.mql5.com/en/articles/10827) | Live broker connectivity |
| [supabase-py](https://github.com/supabase/supabase-py) | Database and auth client |
| [redis-py](https://github.com/redis/redis-py) | Signal pub/sub via Upstash |
| [azure-keyvault-secrets](https://pypi.org/project/azure-keyvault-secrets/) | Secret management |
| [pandas](https://pandas.pydata.org/) | OHLCV data manipulation |
| [requests](https://docs.python-requests.org/) | Telegram Bot API calls |

### Frontend

| Library | Purpose |
|---------|---------|
| [React 19](https://react.dev/) | UI framework |
| [Vite 8](https://vitejs.dev/) | Build tool |
| [TypeScript](https://www.typescriptlang.org/) | Type safety |
| [Tailwind CSS 3](https://tailwindcss.com/) | Utility styling |
| [Zustand](https://github.com/pmndrs/zustand) | Global state (replay store) |
| [TanStack Query](https://tanstack.com/query) | Server state and caching |
| [Lightweight Charts v5](https://tradingview.github.io/lightweight-charts/) | TradingView candlestick chart |
| [@supabase/supabase-js](https://github.com/supabase/supabase-js) | Realtime subscriptions + RLS auth |
| [React Router v7](https://reactrouter.com/) | Client-side routing |
| [Vitest](https://vitest.dev/) | Unit tests |
| [Playwright](https://playwright.dev/) | End-to-end tests |

---

## Security notes

- The frontend uses the **anon key** — RLS policies on `candles`, `trade_events`, `replay_sessions`, and `user_onboarding` ensure each user only sees their own rows.
- The backend uses the **service role key** (fetched from Azure Key Vault, never committed) to write rows with the correct `user_id` so RLS passes on read.
- `shared_sessions` rows are readable by anyone (the UUID is the unguessable capability), but only the authenticated owner can create or delete them. Snapshots are immutable once created — no update policy exists by design.
- Never commit `.env.local` or any file containing the service role key. Both are gitignored.
- All MT5 credentials, Redis URLs, and Supabase keys live exclusively in Azure Key Vault.
