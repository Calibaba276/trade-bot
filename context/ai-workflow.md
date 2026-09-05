# Glass Box: Agent Workflow Supplement

[`AGENTS.md`](../AGENTS.md) is the mandatory master instruction set for all work. It owns universal task intake, review-gated `NEXT` authorization, progress-tracker maintenance, safety rules, ambiguity/escalation, and handoff format. Do not restate or override those rules here.

This document supplies only the feature-delivery detail agents need after following `AGENTS.md`.

## Feature scope

A feature includes the direct plumbing needed for its requested outcome—types, visible UI states, and tests—but not a new product decision, broker integration, payment provider, market, or data-retention policy. Treat README, `.md/`, `context/`, migrations, types, and executable code as potentially divergent; inspect the current implementation before relying on a document.

State facts as facts and assumptions as assumptions. Never invent live metrics, execution states, backtest outcomes, broker compatibility, or compliance claims.

## Cross-layer implementation

1. Trace the data lifecycle end to end. For a new field: migration/RLS/index → backend producer/consumer → frontend type/normalizer → query/realtime → UI states → test.
2. Keep public interfaces narrow. Validate external input at the boundary and retain useful safe error context.
3. For execution paths, preserve atomic idempotency and write observable events. Never use a client-side check as the only gate.
4. For UI work, use `ui-context.md` tokens/patterns and cover loading, empty, error, unauthorized/locked, and live-update states.
5. For Supabase changes, use a new ordered migration; do not edit a migration that may already be applied.
6. For secrets, use Azure Key Vault/backend configuration. Never create committed secret files or expose service credentials to Vite.

## Risk-focused verification

- Run targeted unit tests first; expand to lint/build/e2e in proportion to the changed surface.
- Review changed files for contract mismatches, RLS implications, cleanup of subscriptions/timers, null compatibility, and accidental secret logging.
- For database changes, inspect the SQL for indexes, RLS `USING` and `WITH CHECK`, ownership, rollback/compatibility, and public-read implications.
- For trading logic, validate closed-candle behavior, time zones, risk gates, failure paths, and duplicate signal handling. A passing happy-path test alone is insufficient.

## Prohibited shortcuts

- Do not commit credentials, logs containing credentials, database dumps, or actual user/broker data.
- Do not weaken RLS, remove plan/risk gates, make audit snapshots mutable, or turn a service-key operation into a browser operation for convenience.
- Do not mock a real-time successful execution in production UI when the operation failed or is unknown.
- Do not use lookahead data in strategies/backtests or reveal future replay events before their timestamp.
- Do not claim trading, security, or regulatory guarantees beyond implemented and verified behavior.
