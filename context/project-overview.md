# Glass Box: Project Overview

## Product vision

Glass Box is a rule-driven automated forex trading engine with an explainable, real-time dashboard. It executes deterministic ICT (Inner Circle Trader) setups through MetaTrader 5 (MT5) while exposing the evidence for each decision: market patterns, verdict inputs, execution outcome, and risk state.

The brand promise is **transparent automation**: users should be able to answer “what happened, why, and what did the engine know at that time?” for every trade. Glass Box is not an AI signal generator and must never imply guaranteed returns.

## Primary users and outcomes

| User | Job to be done | Product proof |
| --- | --- | --- |
| New automated trader | Run a disciplined strategy without manual emotional execution. | Clear onboarding, account status, plain-English explanations. |
| ICT trader | Verify that automation follows the intended setup rules. | Pattern timeline, verdict checklist, replay, audit link. |
| Prop-firm candidate | Protect an account against trading-rule breaches. | Per-account sizing, drawdown visibility, obvious halt state. |

## Core flows

### 1. Join and connect

1. Visitor lands on `/`, understands the rule-driven/transparent value proposition, and creates an account at `/sign-up`.
2. Supabase Auth establishes the session; the app routes authenticated users to `/dashboard`.
3. The user completes onboarding, creates or connects a `broker_accounts` record, configures risk, and chooses permitted markets.
4. The orchestrator starts a dedicated worker for the account. The dashboard shows its actual status; it must not claim “running” from optimistic client state.

### 2. Detect, explain, and execute

1. A market runner evaluates only closed candles during its configured session and identifies ICT conditions (for example sweep, MSS, FVG).
2. It creates a `Verdict` containing immutable-at-creation signal inputs: symbol, direction, entry, stop loss, take profit, scenario, timestamps, and indicator state.
3. The verdict is persisted in Supabase, published via Redis, and processed by the account worker.
4. The worker applies account-level market/tier/risk gates, atomically claims `(signal_id, account_id)`, submits to MT5, and persists the execution lifecycle.
5. The frontend receives account-scoped events and renders the decision trail without fabricating data or hiding a rejection/error.

### 3. Monitor, review, and share

1. In Live mode, the user sees candles, pattern events, verdicts, execution state, and risk/halt indicators as they arrive.
2. In Replay mode, the user steps through recorded candles and events by time; replay must only reveal information available at the selected timestamp.
3. The user filters trade history and opens the verdict details to inspect prices, conditions, and execution details.
4. The user can create a server-stored, immutable `shared_sessions` snapshot and share `/share/:uuid`. Anyone with the unguessable UUID can view it; only its owner may revoke it.

## Scope for the current product

- MT5-connected, account-specific execution and monitoring.
- ICT strategy runners, currently centered on EURUSD and XAUUSD; market availability is enforced per plan/account.
- Supabase-backed auth, account-scoped dashboard data, and realtime trade-event display.
- Redis signal transport plus database durability/idempotency backstops.
- Live/replay dashboard, trade history, prop-firm risk visibility, Telegram operational notifications, and public audit snapshots.

## Explicitly out of scope

- Predictive AI/ML, discretionary trade recommendations, copy trading, or a promise of profitability.
- Holding customer funds, acting as a broker, KYC/AML workflows, or investment-advisory functionality.
- Replacing MT5, supporting arbitrary brokers without a tested symbol-normalization layer, or assuming broker symbols are universal.
- Crypto’s 24/7 execution model until it has its own strategy/risk/session design.
- A generic portfolio-management system or social-trading network.
- Treating a public audit link as private data: it is intentionally capability-public and must contain only data safe to disclose.

## Product acceptance bar

Any user-facing feature is complete only when it preserves explainability, shows loading/empty/error states, respects plan and account boundaries, and has a test appropriate to its risk. Any execution-affecting change also needs an explicit fail-closed behavior and an auditable event/log trail.
