# Glass Box: Progress Tracker

> Update this file only for verified completed work, active milestones, or durable architectural decisions. Link to the relevant PR, migration, test, or commit where available. Do not mark UI-only work complete when enforcement/data plumbing is pending.

## Status legend

- `[ ]` Not started
- `[~]` In progress
- `[x]` Verified complete
- `[!]` Blocked / needs decision

## Current focus

| Field | Value |
| --- | --- |
| Phase | Six-week coding roadmap rebaseline |
| Objective | Deliver the implementation backlog in `.md/SIX_WEEK_BUILD_PLAN.md`, in its original week order. |
| Owner | Coding agent + project owner for external/manual dependencies |
| Started | 2026-09-05 |
| Status | `[~]` |
| Source | `.md/SIX_WEEK_BUILD_PLAN.md` (updated 2026-06-21); statuses below preserve only verified plan evidence. |

## Coding roadmap — ordered by the six-week plan

> This is the coding backlog only. Marketing, legal, provider outreach, Paystack account setup, and other `[YOU]` manual tasks remain in the source plan and are intentionally not tracked as agent implementation work here. Do not infer completion from the age of the plan; verify the code, migration, and tests before changing a task status.

### Week 1 — Foundation, trial CTA, and safety

- [ ] EURUSD strategy rewrite: eliminate lookahead bias; prove all decisions use closed candles.
- [ ] Add `user_profiles` with trial fields, signup trigger, RLS, and effective-tier behavior.
- [ ] Denormalize effective plan/trial state into `broker_accounts`, including `trial_expired` behavior.
- [ ] Add the three missing database indexes from the plan.
- [ ] Audit RLS across all relevant tables.
- [ ] Audit MT5 credential handling; confirm no plaintext secrets reach logs.
- [ ] Backtest XAUUSD bias thresholds (strict/balanced/active) and commit real comparison metrics; this gates the bias-mode UI.
- [ ] Landing page: align pricing to $15/$49 with trial badge and replace primary CTA with the 30-day free-trial offer.
- [ ] Landing page: remove dead footer links, repair the live-demo action, and add ICT-term tooltips.
- [ ] Wire the RiskTab “Save Defaults” action to persisted account configuration.

### Week 2 — XAUUSD, auth, onboarding, and access controls

- [ ] Build and validate the XAUUSD strategy runner.
- [x] Orchestrator supervises strategy runners with staggered WAT launch times; batch-file launch path removed. Evidence: source plan records completion on 2026-06-25; re-verify before modifying.
- [ ] Replace the superseded `broker_accounts.symbol` approach with account `enabled_markets`; remove the legacy column only after dependent frontend work is verified.
- [ ] Add market selection to the account-creation flow and persist `enabled_markets`.
- [ ] Add account `bias_mode` (strict default, Pro-only) and pass it through the XAUUSD runner/strategy.
- [ ] Add trial-abuse prevention: one account during trial and verified-email gating.
- [ ] Add the beta-registration cap (50 users).
- [ ] Complete auth UX: token alignment, forgot-password action, password-length hint, and correct post-signup redirect.
- [ ] Rename “Chart Debugger” to “Replay Mode” and standardize sidebar icons.
- [ ] Build the first-login onboarding checklist with trial context.

### Week 3 — indices, enforcement, and account experience

- [ ] Add NAS100, US30, and SPX500 runners through `MARKET_RUNNER_CATALOGUE` after the EURUSD strategy change is verified.
- [ ] Replace the accounts-table symbol column with enabled-market chips.
- [ ] Enforce tiers in `worker.py`: active trial can access Pro markets; `trial_expired` halts execution; failures fail closed.
- [ ] Add dashboard market tabs reflecting effective tier and a Pro-locked overlay for post-trial Starter users.
- [ ] Add an all-pages engine-halt banner and the delayed halt-notification email path.
- [ ] Persist PropFirmPanel configuration and remove unsupported hardcoded uptime data.
- [ ] Open VerdictSidebar from Overview signal rows.
- [ ] Add the Pro trade-selectivity selector using real gated backtest numbers, plus no-trade-day explanation in Live Feed/cold-start states.
- [ ] Build the post-onboarding cold-start experience.

### Week 4 — live data, audit links, and explainability

- [ ] Replace/pair verdict polling with a Supabase Realtime verdict feed.
- [ ] Add the PropFirmPanel profit-target tracker and Trades-page date-range filter.
- [ ] Add dashboard ICT “Explain this” tooltips.
- [ ] Add the immutable `audit_links` persistence contract and generation API endpoint.
- [ ] Build the public `/audit/[uuid]` page with a trial acquisition CTA.
- [ ] Render realtime chart overlays in Live mode.
- [ ] Add the session-countdown timer utility.

### Week 5 — billing, trial lifecycle, and replay

- [ ] Add the trial countdown banner with the planned day-range states.
- [ ] Add the Day 30 plan-selection screen (Pro, Starter, Pause).
- [ ] Add hourly trial-expiry processing that applies `trial_expired`.
- [ ] Add the five-message trial email drip campaign.
- [ ] Add atomic `activate_subscription` RPC and Paystack webhook handling with HMAC-SHA512 validation.
- [ ] Store Paystack keys in Azure Key Vault; never in frontend configuration.
- [ ] Complete the Settings billing tab and Starter-to-Pro upgrade nudge.
- [ ] Add Replay Mode slider access for Pro and trial users.
- [ ] Add structured FVG data to verdicts and chart overlays (stretch).
- [ ] Add landing-page social-proof placeholder section.

### Week 6 — engineering QA and launch readiness

- [ ] Final landing-page polish: prominent trial CTA and pricing/trial treatment.
- [ ] Execute and record the full trial-to-paid primary QA journey.
- [ ] Execute trial-email drip QA and the full Pro journey, including bias mode/no-trade-day behavior.
- [ ] Run regression coverage on existing features and record performance-check results.
- [ ] Add session-summary cards (stretch).

## Completed work

| Date | Item | Evidence | Notes |
| --- | --- | --- | --- |
|  |  |  |  |

## Architectural decisions

| Date | Decision | Rationale | Consequences / follow-up |
| --- | --- | --- | --- |
|  |  |  |  |

## Open decisions and blockers

| ID | Decision / blocker | Impact | Owner | Needed by | Status |
| --- | --- | --- | --- | --- |
|  |  |  |  |  | `[!]` |

## Verification log

| Date | Change area | Verification performed | Result | Follow-up |
| --- | --- | --- | --- | --- |
|  |  |  |  |  |
