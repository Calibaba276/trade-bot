# trade-bot — Glass Box Trading Engine

An automated forex trading system built on the ICT (Inner Circle Trader) institutional order-flow model, paired with a real-time "Glass Box" dashboard that lets you watch every pattern detection, entry, and exit as it happens — or replay any past session candle-by-candle.

## Recent additions

Last updated **29 August 2026**.

| Date | Addition |
|------|----------|
| 29 Aug 2026 | Replaced the Windows PowerShell deployment helpers with Command Prompt-native `deploy_windows.cmd` and `enter_release.cmd` scripts. |
| 29 Aug 2026 | Updated production deployment to run through CMD after CI approves the exact commit. |
| 29 Aug 2026 | Added versioned releases, isolated virtual environments, NSSM service management, health observation, release markers, logs, and automatic rollback. |
| 29 Aug 2026 | Added this from-scratch Windows VM, GitHub Actions runner, Key Vault, deployment, verification, and push guide. |
| 29 Aug 2026 | Moved the manual end-to-end signal injector from `scripts\inject_test_signal.py` to `tests\inject_test_signal.py`. |
| Earlier deployment work | Added Python compilation, Ruff, Pyright, Pytest, frontend linting, Vitest, and production frontend build checks to CI. |

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
├── scripts/                  # CMD-native Windows deployment and release-entry helpers
├── tests/                    # Backend tests and the manual pipeline signal injector
├── .github/workflows/        # CI gate and gated Windows VM deployment
└── supabase/
    └── migrations/           # Versioned SQL schema applied to Supabase
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

## Windows VM setup from scratch

The production engine must run natively on Windows because it connects to MetaTrader 5. These instructions use **Command Prompt**. Run installation and service commands from **Command Prompt as Administrator**.

### 1. Create and secure the Azure VM

1. Create a 64-bit Windows Azure VM with enough CPU/RAM for MT5, Python, and the enabled strategy processes.
2. Enable the VM's **system-assigned managed identity** under Azure Portal → VM → Identity.
3. Restrict RDP (`3389`) to your own public IP. The engine does not need a public inbound application port; it needs outbound HTTPS access to GitHub, Azure Key Vault, Supabase, Upstash Redis, Telegram, and market-data providers.
4. Install Windows updates and reboot before installing the trading stack.

The VM identity needs the **Key Vault Secrets User** role on both vaults:

- `calibabasecret`: Supabase, Redis, Telegram, runner/backtest settings, and the current single-runner MT5 secrets.
- `glass-box`: per-account MT5 password secrets referenced by the `password` field in `broker_accounts`.

Assign these roles in Azure Portal → each Key Vault → Access control (IAM). Managed identity avoids storing an Azure client secret on the VM.

### 2. Install the required software

Install Git, 64-bit Python 3.10, and Azure CLI:

```bat
winget install --exact --id Git.Git
winget install --exact --id Python.Python.3.10
winget install --exact --id Microsoft.AzureCLI
```

Close and reopen Command Prompt, then verify:

```bat
git --version
python --version
az --version
where python
```

Also install:

- **MetaTrader 5** at `C:\Program Files\ICT\terminal64.exe`. Log in to the broker account, enable algorithmic trading, and confirm the required symbols are visible. The EURUSD and XAUUSD runners currently use this exact terminal path.
- **NSSM** (the Non-Sucking Service Manager). Put `nssm.exe` in a stable location such as `C:\Tools\nssm\nssm.exe`; the GitHub variable can point directly to it, so changing the system `PATH` is optional.

### 3. Configure Azure Key Vault secrets

The existing code expects these general secrets in `calibabasecret`:

| Secret | Purpose |
|--------|---------|
| `SUPABASE-URL` | Supabase project URL |
| `SUPABASE-KEY` | Supabase service-role key |
| `SUPABASE-SERVICE-ROLE-KEY` | Preferred explicit service-role key for workers/verdicts |
| `REDIS-URL` | Upstash `rediss://` connection string |
| `ACCOUNT`, `PASSWORD`, `SERVER` | Current runner-level MT5 login settings |
| `ISBACKTESTING` | `false` for production |
| `BACKTESTING-START`, `BACKTESTING-END` | Backtest date range |
| `POLYGON-API-KEY` | Historical market-data key |
| `TELEGRAM-BOT-TOKEN`, `TELEGRAM-CHAT-ID` | Telegram notifications |

For each Supabase `broker_accounts` row, store the actual MT5 password as a secret in `glass-box`, then put only that secret's **name** in the row's `password` field. Do not put the plaintext broker password in Supabase or Git.

From an authenticated administrator machine, secrets can be created with:

```bat
az login
az keyvault secret set --vault-name calibabasecret --name REDIS-URL --value "YOUR_VALUE"
az keyvault secret set --vault-name glass-box --name "mt5-YOUR_ACCOUNT-password" --value "YOUR_MT5_PASSWORD"
```

Repeat for every required secret. Avoid placing real secret values in command history on shared machines; the Azure Portal is safer for manual entry.

### 4. Prepare Supabase

Apply all migrations in `supabase\migrations` in filename order. There are currently six migrations, covering the Glass Box frontend schema, onboarding, shared sessions, forced worker respawn, account plans/enabled markets, and signal indicator columns.

Then confirm each production `broker_accounts` row has the correct:

- `user_id`, MT5 login/account number, broker server, and password **secret name**;
- runnable status and `force_spawn = false` unless a one-time respawn is intended;
- `plan` and `enabled_markets` (EURUSD and/or XAUUSD currently have runners).

### 5. Install the GitHub Actions runner

Keep the repository private: a self-hosted runner executes workflow code on your VM. In GitHub, open repository **Settings → Actions → Runners → New self-hosted runner**, choose Windows x64, and follow the generated commands. GitHub recommends installing it under `C:\actions-runner`.

During `config.cmd`, install the runner as a Windows service so it starts after a reboot. This deployment workflow installs and reconfigures another Windows service, so run the Actions runner service under a dedicated Windows account that has the required local permissions. Do not reuse your everyday administrator account.

Verify the runner appears **Idle** in GitHub and has the default labels `self-hosted`, `windows`, and `x64`, which match `.github\workflows\deploy.yml`.

### 6. Configure GitHub deployment controls

In GitHub → repository **Settings → Secrets and variables → Actions → Variables**, add:

| Variable | Value |
|----------|-------|
| `ENABLE_VM_DEPLOYMENT` | `true` when the VM is ready; omit it or use `false` while preparing |
| `GLASSBOX_ROOT` | `C:\GlassBox` |
| `GLASSBOX_SERVICE_NAME` | `GlassBoxOrchestrator` |
| `GLASSBOX_PYTHON` | Full result from `where python`, or `python.exe` if reliably on the runner service's `PATH` |
| `GLASSBOX_NSSM` | `C:\Tools\nssm\nssm.exe` |

Create or review the GitHub `production` environment if you want approval rules before deployment.

### 7. Deploy

The recommended path is automatic:

1. Push a feature branch and open a pull request into `main`.
2. Wait for the `CI` workflow to pass.
3. Merge into `main`.
4. CI runs again on `main`; after it succeeds, `deploy.yml` checks out that exact approved commit on the Windows runner and calls `scripts\deploy_windows.cmd`.

For a deliberate manual deployment from a checked-out repository on the VM:

```bat
cd C:\path\to\trade-bot
git rev-parse HEAD
scripts\deploy_windows.cmd --source "%CD%" --commit FULL_40_CHARACTER_SHA --run-id 1-1 --nssm "C:\Tools\nssm\nssm.exe"
```

The deployer creates an immutable folder under `C:\GlassBox\releases`, creates its own `.venv`, installs dependencies, compiles the backend, configures the `GlassBoxOrchestrator` NSSM service, waits for it to remain healthy, and records `current-release.txt`. If service activation fails, it restores the previous NSSM application, directory, and parameters.

### 8. Verify and operate the service

```bat
sc query GlassBoxOrchestrator
type C:\GlassBox\current-release.txt
type C:\GlassBox\logs\orchestrator-service-stderr.log
type C:\GlassBox\logs\orchestrator-service-stdout.log
```

Enter the active release and keep its virtual environment in your current Command Prompt:

```bat
call C:\GlassBox\Enter-GlassBox.cmd
```

The `call` keyword is required. Do not manually start a second orchestrator while the service is running. For an intentional interactive engine session:

```bat
net stop GlassBoxOrchestrator
call C:\GlassBox\Enter-GlassBox.cmd
python -m backend.services.orchestrator
```

When finished, stop the interactive process with `Ctrl+C`, then restore the service:

```bat
net start GlassBoxOrchestrator
```

### 9. Optional end-to-end signal test

This command writes to Supabase, publishes to Redis, and may cause a live worker to submit an MT5 order. Use it only with a demo/test account or when you intentionally want that behavior:

```bat
call C:\GlassBox\Enter-GlassBox.cmd
python tests\inject_test_signal.py
```

Check `signals`, `executions`, and `execution_events` in Supabase plus the service logs and Telegram. A rejection while the market is closed still proves that the message reached MT5.

### 10. VM recovery checklist

- Runner offline: check the GitHub Actions runner service in `services.msc` and confirm outbound GitHub access.
- Deployment disabled: confirm `ENABLE_VM_DEPLOYMENT` is exactly `true`.
- Key Vault authentication failure: confirm system-assigned identity is enabled and has `Key Vault Secrets User` on both vaults.
- `python.exe` or `nssm.exe` not found: use full executable paths in the GitHub variables.
- MT5 initialization failure: confirm terminal path, broker login/server, algorithmic trading, symbol names/suffixes, and that the service account can access the terminal installation.
- New service repeatedly stops: inspect `C:\GlassBox\logs\orchestrator-service-stderr.log`; the deployer should roll an existing service back automatically.

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

```bat
cd frontend
npm install
```

### 2. Create your environment file

```bat
copy .env.local.example .env.local
```

Edit `.env.local` and fill in:

```
VITE_SUPABASE_URL=https://<your-project-ref>.supabase.co
VITE_SUPABASE_ANON_KEY=<your-anon-key>
```

Use the **anon (publishable) key** here — never the service role key. Row-level security handles data isolation.

### 3. Apply the database migrations

Six migration files currently live under `supabase/migrations/`. Apply them in filename order, or let the Supabase CLI push all pending migrations:

```bat
rem With the Supabase CLI (recommended)
supabase db push
```

Alternatively, paste each file into the Supabase SQL editor in filename order.

| Migration file | What it creates |
|---------------|----------------|
| `20260612000000_glassbox_frontend_schema.sql` | `candles`, `trade_events`, `replay_sessions`, `signals`; adds `user_id` to `broker_accounts`; enables Realtime |
| `20260617000000_user_onboarding.sql` | `user_onboarding` — wizard step + completion flag, synced across devices |
| `20260618000000_shared_sessions.sql` | `shared_sessions` — immutable audit snapshots for public share links |
| `20260619000000_broker_accounts_force_spawn.sql` | Adds the indexed one-time `force_spawn` worker-respawn override |
| `20260620000000_account_plans_and_markets.sql` | Adds account plans and per-account enabled-market selection |
| `20260620000001_signals_indicator_columns.sql` | Adds structured indicator/context columns to signals |

### 4. Start the dev server

```bat
npm run dev
rem Open http://localhost:5173
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

### Backend checks used by CI

```bat
python -m pip install -r requirements-ci.txt
python -m compileall -q backend\strategies backend\services tests
ruff check --select=E9,F63,F7,F82 backend\strategies backend\services tests
pyright backend\strategies backend\services tests
python -m pytest -q tests
```

### Unit tests (Vitest)

```bat
cd frontend
npm test
npm run test:watch
```

Covers: Zustand store actions, `usePerformanceStats` calculations, Context Cascade parent-timeframe logic.

### End-to-end tests (Playwright)

```bat
cd frontend
npm run test:e2e
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

## Commit, push, and release this work

The current working branch is `vm-deploy`. Review and push all tracked deletions, modifications, and new files together so the PowerShell-to-CMD replacement and test-file move are recorded correctly:

```bat
git status
git add -A
git diff --cached --stat
git diff --cached
git commit -m "Document and finalize CMD Windows VM deployment"
git push -u origin vm-deploy
```

Then open a pull request from `vm-deploy` into `main`. Do not bypass a failing CI check. After review:

1. Merge the pull request into `main`.
2. Confirm `CI` passes on the resulting `main` commit.
3. Confirm **Deploy approved release to Azure VM** starts only after CI succeeds.
4. Verify `GlassBoxOrchestrator`, `current-release.txt`, logs, Telegram startup notifications, and the dashboard before considering the release complete.

If Git reports that the remote branch moved, fetch and inspect before pushing:

```bat
git fetch origin
git status
git log --oneline --decorate --graph --all -20
```

Do not use `git push --force` on `main` or the deployment branch unless you intentionally understand and approve rewriting its history.

---

## Security notes

- The frontend uses the **anon key** — RLS policies on `candles`, `trade_events`, `replay_sessions`, and `user_onboarding` ensure each user only sees their own rows.
- The backend uses the **service role key** (fetched from Azure Key Vault, never committed) to write rows with the correct `user_id` so RLS passes on read.
- `shared_sessions` rows are readable by anyone (the UUID is the unguessable capability), but only the authenticated owner can create or delete them. Snapshots are immutable once created — no update policy exists by design.
- Never commit `.env.local` or any file containing the service role key. Both are gitignored.
- All MT5 credentials, Redis URLs, and Supabase keys live exclusively in Azure Key Vault.
