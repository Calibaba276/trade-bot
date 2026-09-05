# Glass Box: Code Standards

## Applicability

The frontend is TypeScript + React + Vite, not Next.js. Apply modern TypeScript/React conventions below; do not introduce Next-specific routing, API routes, server components, or environment conventions without an approved architectural migration.

## TypeScript and React

- Keep `strict` TypeScript intent: no `any`, unsafe casts, or non-null assertions unless an external API boundary is validated immediately before use.
- Model domain values with unions, not arbitrary strings: `type Timeframe = "1m" | "5m" | "15m" | "1h"`.
- Prefer `interface` for object/domain contracts and `type` for unions, mapped types, and component prop composition.
- Use `unknown` at external boundaries (Supabase JSON, `metadata`, catch values); narrow with a small guard/normalizer.
- Treat database numerics and timestamps deliberately. Convert once at the data boundary; do not mix UTC milliseconds, seconds, and display strings.
- Components use named exports and PascalCase file names: `VerdictSidebar.tsx`, `StatusBadge.tsx`. Hooks are camelCase `use` files: `useLiveTradeEvents.ts`.
- One component per file except tiny private helpers. Export the primary component by name.
- Props are named `ComponentNameProps` when exported or non-trivial. Avoid `React.FC`; type the parameter directly.
- Use function components and early returns for loading/error/empty states. Keep pages thin; move reusable behavior into hooks/components.
- Use `useMemo`/`useCallback` only when they prevent a real expensive computation, dependency churn, or subscription instability—not by default.
- Effects must clean up Supabase realtime channels, intervals, chart instances, and event listeners. Effects synchronize external systems; they are not a substitute for derived state.

```tsx
interface StatusBadgeProps {
  status: AccountStatus;
  detail?: string;
}

export function StatusBadge({ status, detail }: StatusBadgeProps) {
  if (!detail) return <span>{status}</span>;
  return <span title={detail}>{status}</span>;
}
```

## Data-access conventions

- Query Supabase through named hooks or narrowly scoped helpers, never scattered inline calls in render trees.
- Scope every browser query/subscription by the authenticated user/account and clean it up on dependency changes.
- Do not use a client-side plan guard as authorization. `ProGuard` is presentation; worker-side checks and database policies enforce access.
- Keep raw database field names at the data boundary. Convert to a frontend view model if a screen needs a different shape.
- Use TanStack Query for cacheable server state and invalidate/update the relevant key after a mutation. Use Zustand for ephemeral global UI state only.
- Always render loading, empty, error, and degraded/reconnecting states for live data.

## Naming and structure

| Thing | Convention | Example |
| --- | --- | --- |
| React component / TS interface | PascalCase | `TradeReplayChart`, `TradeEvent` |
| Hook / function / variable | camelCase | `useReplaySession`, `selectedTimeframe` |
| Boolean | `is` / `has` / `can` prefix | `isLoading`, `hasHalted`, `canReplay` |
| Event handler | `handle` prefix | `handleMarketChange` |
| Callback prop | `on` prefix | `onDismiss` |
| Constant | camelCase unless true module constant | `const maxRetries = 3`; `const DEFAULT_TIMEFRAME` |
| Route page | PascalCase + `Page` when ambiguous | `FeedPage.tsx` |
| Tailwind class composition | readable grouped strings; extract repeated variants | `className="flex items-center gap-2 border ..."` |

## Styling and accessibility

- Use existing Tailwind tokens (`bg-bg-*`, `text-text-*`, `border-border-*`, `brand`, `bull`, `bear`, `amber`) rather than raw hex values.
- Use semantic state plus icon/text/shape; green/red alone is never enough for a trade or risk state.
- Preserve keyboard operation for dialogs, menus, chart controls, and replay shortcuts. Give icon-only controls an accessible label.
- Respect `prefers-reduced-motion`; animations should communicate updates, never obscure data or move layout.
- Prices, percentages, timestamps, and P&L use the established mono-number treatment and shared format helpers.

## Python interoperability

Frontend naming can be idiomatic TypeScript, but JSON contracts must exactly preserve backend/Supabase names unless a boundary mapper is introduced. Do not rename `signal_id`, `execute_at`, or `created_at` ad hoc. Contract changes require coordinated type, migration, producer, consumer, and test changes.

## Python backend

### Structure and boundaries

- Keep strategy rules in `backend/strategies/`, runner/bootstrap configuration in `backend/runners/`, broker-specific MT5 behavior in `backend/brokers/`, integration/business orchestration in `backend/services/`, and environment/infrastructure concerns in `backend/config/`.
- A runner selects a market and passes parameters; it must not copy ICT detection, position-sizing, or risk-control logic from a strategy.
- Keep deterministic calculations and market-rule decisions isolated from Azure, Supabase, Redis, Telegram, and MT5 imports where possible. This makes a function testable without external credentials or a live terminal.
- Keep service integrations lazy when import-time initialization would require cloud credentials. `verdict.py`'s service-role client pattern is the reference: pure verdict construction remains importable and testable offline.
- Use a new, ordered Supabase migration for persistent-contract changes. Update the producer, consumer, types, and focused tests in the same reviewed task.

### Typing, naming, and API contracts

- Target Python 3.10 syntax. Type all new function parameters and return values, including `-> None` for side-effect functions. Use built-in generic forms (`dict[str, object]`, `list[str]`) and `X | None` rather than `typing.Dict`, `typing.List`, or `Optional[X]` in new code.
- Use `dataclass` for stable, in-process domain records such as a Verdict; use `Literal` for constrained fields such as direction, scenario, status, and timeframe when the allowed set is known.
- Name modules, functions, variables, and arguments in `snake_case`; classes and protocols in `PascalCase`; module constants in `UPPER_SNAKE_CASE`; private implementation details with a leading underscore.
- Name boolean predicates/actions clearly: `is_market_enabled`, `has_halted`, `should_execute`, `can_trade`. Do not encode a boolean as an ambiguous noun.
- Use explicit keyword-only arguments (`*`) for optional inputs that affect a record or execution outcome, as `emit_trade_event()` does. This prevents positional-argument mistakes in financial data.
- Do not pass unstructured dictionaries through multiple layers when a dataclass, typed mapping, or named normalizer can define the contract. If a JSONB payload must remain flexible, type its narrow known fields and isolate the flexible remainder.
- Preserve canonical domain names across boundaries (`signal_id`, `account_id`, `execute_at`, `created_at`) and normalize broker symbols through the shared market helpers rather than ad hoc prefixes/suffix stripping.

### Time, money, and execution safety

- Use timezone-aware datetimes only. Persist/network timestamps as UTC ISO 8601 except where an existing schema explicitly requires epoch milliseconds; convert at the boundary. Session calculations must declare their configured timezone (`Africa/Lagos` in the current engine).
- Use `Decimal` for newly introduced currency/accounting calculations where precision matters. Existing price/lot interfaces may use `float` because of MT5/library APIs; validate finite values and round only at the broker boundary.
- Reject invalid prices, sizes, ratios, symbols, account configurations, and unknown plan values explicitly. For execution, tier, market, drawdown, or credential uncertainty, fail closed and log the reason.
- Strategy logic may inspect only closed historical bars. No current-forming-candle input, future-data lookahead, or replay leakage is permitted.
- Preserve database-backed atomic signal claiming and the unique `(signal_id, account_id)` execution invariant. Never replace it with a read-then-act deduplication check.
- Never swallow an execution or risk-control exception. A best-effort observability/UI emitter may catch an exception only when its docstring/comment states that it cannot interrupt trading, logs safe context, and callers retain the authoritative execution path.

### Errors, logging, and secrets

- Use `setup_logger(__name__)` (or the documented worker exception with `rotate=False`) rather than `print` or configuring handlers in individual modules.
- Log structured, searchable event prefixes such as `[VERDICT SAVED]`, `[CLAIM FAILED]`, or `[DRAWDOWN]`, with safe identifiers, market, state, and error context. Do not log passwords, access tokens, service keys, Redis URLs, full broker credentials, or private payloads.
- Raise specific `ValueError` for invalid caller input and `RuntimeError` for unavailable/invalid operational configuration. Preserve the original exception with `raise ... from exc` when translating it.
- Keep a narrow `try` block around the operation that can fail; never wrap an entire worker loop in a broad `except` that hides the failed stage. A worker configuration or safety-gate failure must result in a visible error/halt status.
- Retrieve secrets only through the configured Azure Key Vault boundary. No fallback secret literals, committed `.env` files, or environment-value logging.

### Tests and static analysis

- As we add new features ensure there are tests to make sure the code works alright as required for each features. Put backend tests in `tests/` and name them `test_<behavior>.py`; name tests as observable behavior (`test_verdict_rejects_missing_prices`) rather than implementation details.
- Use pure fixtures/fakes and deterministic timestamps. Backend CI checks must run without Azure, MT5, Redis, Telegram, or Supabase connectivity.
- Add focused tests for every new validation, risk/tier gate, symbol normalization case, strategy phase, and execution idempotency branch. For strategy changes, include no-lookahead/closed-candle cases.
- Run the relevant commands before handoff: `pytest`, `ruff check backend tests`, and `pyright` (the configured scope is `backend/strategies`, `backend/services`, and `tests`). Do not silence findings globally; fix the contract or add the narrowest justified suppression.

## Testing and quality gate

- Write Vitest tests for deterministic stores, formatters, selectors, calculations, and hook behavior.
- Add Playwright coverage for critical user journeys: auth redirects, protected routes, public shares, and key gating behavior.
- Use fixtures that look like production events; never use real credentials/account numbers.
- Before handoff run the narrowest relevant test, then `npm run lint` and `npm run build` for frontend changes when feasible. For backend logic, add/run focused pytest tests.
- Do not “fix” type/lint failures by disabling rules globally or widening core types.
