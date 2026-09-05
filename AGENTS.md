# Glass Box — Agent Operating Manual

This is the authoritative entrypoint for agents working in this repository. Read it completely before inspecting, editing, running, or proposing work. More specific instructions in a subdirectory apply to that subtree; user instructions take precedence over all repository instructions.

## Product and architecture context

Glass Box is a rule-driven, explainable automated forex trading engine. It executes deterministic ICT setups through MT5 and exposes the evidence behind each decision through a real-time dashboard and replay/audit surfaces. It is not an AI signal generator and must never imply guaranteed returns.

Read these files before starting a task, selecting only the additional documents relevant to the requested work:

| File | Read when | Purpose |
| --- | --- | --- |
| [`context/project-overview.md`](context/project-overview.md) | Always | Product vision, user flows, scope, and out-of-scope boundaries. |
| [`context/architecture.md`](context/architecture.md) | Always | Stack, layer boundaries, data contracts, security, and trading invariants. |
| [`context/code-standards.md`](context/code-standards.md) | Always | React/TypeScript and Python code standards, test expectations, and naming. |
| [`context/ai-workflow.md`](context/ai-workflow.md) | Always | Scoping, ambiguity, implementation, review, and verification rules. |
| [`context/ui-context.md`](context/ui-context.md) | UI/UX work | Existing design tokens, component patterns, accessibility, and visual direction. |
| [`context/progress-tracker.md`](context/progress-tracker.md) | Always | Current milestones, verified work, architectural decisions, and blockers. |

The implementation is a **React 19 + TypeScript + Vite** frontend and a **Python 3.10** MT5 trading engine. It is not a Next.js application. Do not add Next.js, server actions, `NEXT_PUBLIC_*` variables, or an alternate routing model without an explicitly approved architecture migration.

## Mandatory operating sequence

For every requested feature or change:

1. Read this file and the required context documents, including `context/progress-tracker.md`; then inspect relevant current code, migrations, tests, and local instructions.
2. Identify the requested outcome, affected layers, authoritative data source, security/access boundary, acceptance criteria, and any existing user changes that must be preserved.
3. Break the feature into small, independently reviewable steps. Each step must state its outcome, limited scope, acceptance criteria, and verification method. Cross-layer work follows dependency order: schema/RLS/index → backend contract → frontend data boundary → UI → tests.
4. Implement **only the first step**. Do not begin later steps or opportunistic refactors.
5. Verify only the completed step in proportion to risk, then stop.
6. Report: what changed, affected files, acceptance criteria/evidence, verification, any required `progress-tracker.md` update, and exactly one proposed next step.
7. Wait for explicit user approval. Only the literal user instruction `NEXT` authorizes that one proposed next step. It does not authorize subsequent steps, another feature, broad refactoring, or scope expansion.

If a user requests revisions, make only those revisions, verify them, and pause for review again. After a feature’s final step, pause and wait for an explicit `NEXT` before beginning another feature.

## Progress tracking

- Before editing, consult `context/progress-tracker.md` as the current project record.
- After edits, update it only if the result is verified completed work, an active milestone, or a durable architectural decision.
- Include concrete evidence: a passing test, applied migration, commit, reviewed implementation, or other verifiable artifact.
- Never use the tracker for routine edits, speculative plans, UI-only stubs, or unverified claims. Do not mark a task complete merely because code was written.

## Non-negotiable safety rules

- Never commit, log, return, or expose secrets: MT5 credentials, Azure Key Vault/service-role keys, Redis URLs, Telegram tokens, or private user data.
- Browser code uses only the Supabase anon key. Service-role operations remain backend-only. Do not weaken Supabase RLS to repair a client query.
- User-owned rows remain account/user scoped. Public shared-session UUIDs are deliberately capability-public; snapshots must be safe to disclose and immutable after creation.
- Trading logic uses closed historical candles only—no lookahead, forming-candle decisions, or replay leakage.
- Execution/risk/tier/market/config failures fail closed. Preserve atomic `(signal_id, account_id)` claiming; never replace it with a read-then-act deduplication pattern.
- Never show an unverified execution, live status, latency, P&L, or backtest metric as fact.
- Preserve existing worktree changes. Do not reset, revert, delete, overwrite, or mass-reformat unrelated files.

## Quality requirements

- Use existing boundaries: `frontend/src` for React UI/data hooks/store, `backend/strategies` for deterministic strategy logic, `backend/services` for orchestration/integrations, `backend/brokers` for MT5 concerns, `backend/config` for infrastructure, and `supabase/migrations` for schema contracts.
- Make additive migrations for persistent-contract changes; do not alter migrations that may already be applied.
- Provide loading, empty, error, access-locked, and degraded/reconnecting states for asynchronous UI.
- Use existing Tailwind design tokens and accessibility patterns. Do not add a new component library or design system without approval.
- Run focused verification first. Frontend changes normally use relevant Vitest/Playwright checks, then `npm run lint` / `npm run build` when appropriate. Backend changes normally use focused pytest, then `ruff check backend tests` and `pyright` when appropriate. Report any check not run.

## Ambiguity and escalation

Resolve low-risk ambiguity from current code and repository context, and state the assumption in the handoff. Stop and ask one concise question when a decision changes execution behavior, money/risk limits, access control, public data exposure, billing, a durable schema decision, or destructive scope. Default to safe, fail-closed behavior where configuration or authorization is uncertain.
