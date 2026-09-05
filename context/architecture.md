# Glass Box: Architecture

## System shape

```text
Market data / MT5
  -> Python strategy runners -> Verdict + candles/events -> Supabase
                              -> Redis `signals` -> per-account worker -> MT5 order
                                                     -> executions/events -> Supabase
Supabase Auth/RLS + Realtime <-> React/Vite dashboard
Azure Key Vault -> Python services only; Telegram <- operational notifications
```

## Technology baseline

| Area | Chosen technology | Responsibility |
| --- | --- | --- |
| Dashboard | React 19, TypeScript, Vite, React Router v7 | Browser UI at public, auth, dashboard, and share routes. |
| UI/state | Tailwind CSS 3, Zustand, TanStack Query, Lightweight Charts v5 | Styling, local replay/UI state, server caching, chart rendering. |
| Backend | Python 3.10, Lumibot, MetaTrader5 | Strategy evaluation, order execution, risk monitoring. |
| Persistence | Supabase Postgres, Auth, Realtime | Auth, owned product data, event stream, audit snapshots. |
| Messaging | Upstash Redis / redis-py | Low-latency verdict fan-out. Not the source of truth. |
| Secrets | Azure Key Vault / DefaultAzureCredential | Service keys, broker credentials, Redis URL, Telegram secrets. |
| Operations | Telegram Bot API, structured logging | Important worker and execution notifications. |

This repository is **not a Next.js application**. Do not add Next.js, server actions, or `NEXT_PUBLIC_*` variables unless an approved migration changes the architecture. Browser variables use `VITE_*`; service credentials must never enter the browser bundle.

## Layer boundaries

### Frontend (`frontend/src`)

- `pages/` compose route-level screens only; routing lives in `App.tsx`.
- `components/` render reusable presentational/domain UI; chart drawing stays in chart components/utilities.
- `hooks/` own lifecycle logic for Auth, Supabase reads/realtime, and derived server data.
- `store/` holds cross-screen ephemeral UI state (for example replay position), never authoritative trading state.
- `types/` contains database/domain shapes shared within the frontend; validate/normalize external rows at the boundary.
- `lib/supaclient.ts` is the single browser Supabase client boundary. The browser may use only the anon key and RLS-protected operations.

### Trading engine (`backend`)

- `strategies/`: pure-ish market/ICT logic. It must be deterministic and testable with historical inputs.
- `runners/`: choose market, mode, and schedule/strategy parameters. No duplicated strategy logic.
- `services/verdict.py`: builds, persists, and publishes the canonical verdict.
- `services/worker.py`: resolves one account’s configuration, enforces gates, claims signals, and executes idempotently.
- `services/orchestrator.py`: supervises per-account worker/runner processes.
- `services/position_monitor.py`: owns ongoing protective controls such as halt/drawdown behavior.
- `brokers/`: MT5-specific adapter; broker quirks stay here or in a future normalization layer.
- `config/`: secrets, Supabase, logging, market policy, and operational configuration.

### Data and integrations

- Supabase migrations are the schema contract. Additive, reversible migrations precede code that depends on new fields.
- Redis accelerates delivery; persisted `signals` and execution records provide recovery/auditability.
- `shared_sessions.payload` is an immutable audit snapshot. There is deliberately no update policy.

## Non-negotiable invariants

### Security and privacy

1. Secrets, service-role keys, MT5 credentials, Redis URLs, and Telegram tokens live only in Azure Key Vault or local ignored environment configuration. Never log, return, or commit them.
2. Browser code uses the Supabase anon key only. Service-role access is backend-only and is loaded lazily where practical.
3. Every user-owned frontend table must enforce RLS with `auth.uid() = user_id` on reads and writes. Do not weaken an existing policy to “fix” a client query.
4. Public share links are intentionally readable without authentication. Snapshot contents must be minimized and treated as public; owners can delete, never mutate, a share.
5. Do not persist passwords or sensitive broker data in Zustand, URL parameters, local/session storage, telemetry, or client logs.

### Trading correctness and safety

1. Strategy decisions use closed candles only: no current-forming-candle reads, lookahead, or replay leakage.
2. A verdict’s entry/SL/TP/direction/scenario and observed indicator values are a creation-time audit record; do not retroactively rewrite them.
3. A worker must execute a signal for an account at most once. Use the database uniqueness/atomic claim of `(signal_id, account_id)`; never replace it with read-then-write logic.
4. Market/tier/risk/halt/configuration failures must fail closed: log the reason and skip/stop execution rather than defaulting to a permissive action.
5. Redis delivery may be duplicated or absent. Workers must tolerate duplicate delivery and recover safely from durable signal storage.
6. Timestamps crossing system boundaries are UTC/ISO 8601 or documented epoch milliseconds. UI may format in the user context; strategy session logic explicitly uses `Africa/Lagos` where configured.

### Reliability and observability

1. Persist meaningful lifecycle changes (`signal_received`, claim, sizing, order result, error) before/alongside user-visible status where possible.
2. Never claim a successful order, engine status, latency, P&L, or backtest metric without its source data.
3. Errors should retain safe context—IDs, symbol, state, operation—not credentials or full sensitive payloads.
4. Preserve migration compatibility: existing account rows need safe defaults/backfills and new code must tolerate pre-migration nulls during rollout.

## Change protocol

For any cross-layer feature, make the contract explicit in this order: schema/RLS and indexes → Python producer/consumer → frontend type/query/subscription → visible states → tests. Describe any deployment ordering requirement in the PR/task notes. Do not ship a UI control for a risk feature until backend enforcement exists.
