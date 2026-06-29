# Glass Box — Master TODO

All tasks from planning. Grouped by owner and delivery week.

Legend: `[ ]` = not started · `[~]` = in progress · `[x]` = done · `[!]` = blocked

---

## YOUR TASKS (Human-Side)

Things only you can do. No code required.

| # | Task | Priority | When |
|---|------|----------|------|
| H-1 | DM 5 ICT signal providers on Telegram. Script: *"I'm building a transparency layer for MT5 execution — would you look at a demo? I think it could make your channel look more professional."* Goal: one "yes" = first real demand signal. | P0 | Week 1 |
| H-2 | Set up a Paystack account and verify your business identity (required before billing integration can go live). | P0 | Week 1 |
| H-3 | Legal/compliance check: consult a Nigerian fintech/SaaS lawyer on whether auto-executing third-party signals requires a SEC licence. Fallback already decided — "personal automation" framing if unfavourable. Cap public registration at 50 users until resolved. | P1 | Before public launch |
| H-4 | Decide lifetime deal logistics: WHERE to sell ($99 Starter / $199 Pro lifetime, cap 50–100 users) — Gumroad or Lemon Squeezy. Manually provision lifetime tier in Supabase until billing ships. | P2 | After Week 5 billing |
| H-5 | Write pricing page copy: one headline + one value prop per tier in ≤10 words each. Validate framing with first 5 users before finalising. Draft: Starter = "auto-execute ICT signals on your MT5 account" / Pro = "full ICT transparency for your prop firm challenge." | P3 | Week 6 |
| H-6 | Establish at least one active signal provider partnership (the B2B2C flywheel doesn't start without this). | P1 | Week 4 |

---

## ENGINEERING BUILD QUEUE

All code tasks, ordered by delivery week.

---

### WEEK 1 — Core Rewrite + Schema Foundation

- [ ] **E-1-1** Rewrite `ict_model.py` EURUSD logic to fix the repainting/lookahead bug. Audit all calls to future candle data. Output must be strictly point-in-time.
- [ ] **E-1-2** Create `user_profiles` Supabase table with columns: `id` (FK → auth.users), `plan_tier` (text, default `'starter'`), `created_at`. Add index on `plan_tier`.
- [ ] **E-1-3** Denormalize `plan_tier` into `broker_accounts` table so `worker.py` can read tier without a JOIN. Add DB migration.
- [ ] **E-1-4** Add three missing DB indexes: `broker_accounts(user_id)`, `signals(account_id, created_at DESC)`, `signals(symbol, created_at DESC)`.
- [x] **E-1-5** Landing page — fix pricing to $15 Starter / $49 Pro (currently shows $49/$99). File: `Landing.tsx` pricing section.
- [x] **E-1-6** Landing page — add two visible CTA tracks: "Auto-execute signals" (Starter) → `/signup?plan=starter` and "Prop firm challenge" (Pro) → `/signup?plan=pro`.
- [ ] **E-1-7** Landing page — rename "Watch Live Demo" button. It currently scrolls to the features section, not a demo. Either link to a real demo video or rename to "See How It Works."
- [ ] **E-1-8** Landing page — remove footer dead links (About, Blog, Careers) until those pages exist.
- [ ] **E-1-9** Landing page — change CTA to "Start 30-Day Free Trial — No Credit Card Required." (Note: trial infrastructure ships Week 5 — in Week 1, the button links to /sign-up with a banner explaining trial is coming soon for early access users.)
- [x] **E-1-10** Fix `RiskTab` "Save Defaults" button: either wire it to persist to Supabase or add a "Coming soon" label.

---

### WEEK 2 — Onboarding + XAUUSD

- [x] **E-2-1** Build onboarding checklist for first-time users: Step 1 → Connect MT5 account, Step 2 → Set risk config, Step 3 → Wait for next London session. Show on dashboard until all steps complete.
- [ ] **E-2-2** Add XAUUSD strategy runner. Run a second `ict_model.py` instance for XAUUSD (same London/NY session windows as EURUSD). XAUUSD is available on both Starter and Pro.
- [ ] **E-2-3** Make `broker_accounts.symbol` store a comma-separated list (`"EURUSD,XAUUSD,GBPUSD"`). Worker reads the list and skips signals for symbols not in it. Backward compatible with existing single-value records.
- [ ] **E-2-4** Auth pages — replace hardcoded hex colours (`#141921`, `#0f1419`) with design tokens (`bg-bg-surface`, `bg-bg-base`).
- [x] **E-2-5** Auth pages — add "Forgot password" link to Login page.
- [x] **E-2-6** Auth pages — add password length hint on SignUp page.
- [x] **E-2-7** Auth pages — fix post-signup redirect: after email confirmation, send user to `/dashboard`, not `/sign-in`.
- [x] **E-2-8** Rename "Chart Debugger" in sidebar nav to "Replay Mode" to match marketing copy.
- [x] **E-2-9** Standardise sidebar nav icons: pick either emoji OR Unicode icons, not both mixed.
- [ ] **E-2-10** Backtest bias-strength thresholds on XAUUSD (strict 0.70/0.30, balanced 0.60/0.40, active 0.50). Record profit factor, win rate, max drawdown, expectancy, net P&L per mode. **GATE:** these real numbers populate the Pro selectivity UI — feature does not ship without them. (Week 1 dependency, listed here with the Gold work.)
- [ ] **E-2-11** Replace the hardcoded 50% midpoint in `xauusd_model.py` `_compute_daily_bias()` with a configurable `bias_mode` parameter (`strict`/`balanced`/`active` → 0.70/0.60/0.50). Default `strict`. Read via `self.parameters.get("bias_mode", "strict")`, same pattern as `buffer`/`rr_ratio`. Runner passes it through.
- [ ] **E-2-12** Add `broker_accounts.bias_mode` column (`TEXT DEFAULT 'strict' CHECK IN ('strict','balanced','active')`). Worker reads it from the account config and passes into strategy params. Pre-migration rows behave as `strict`. **Pro-only** — Starter accounts forced to `strict`.

---

### WEEK 3 — US Indices + Tier Enforcement

- [ ] **E-3-1** Add NAS100, US30, SPX500 strategy runners (Pro-only). Session window: NYSE open 15:30–17:30 NGT. Separate runner from London/NY forex strategy.
- [ ] **E-3-2** Tier enforcement in `worker.py`: read `plan_tier` from `broker_accounts` at startup. Starter accounts skip signals for Pro-only symbols (NAS100, US30, SPX500). Fail-closed: if tier read fails, halt and log `[TIER_GATE_ERROR]`.
- [ ] **E-3-3** Dashboard market tabs: Starter view shows forex markets; Pro view adds `[NAS100 ⚡] [US30 ⚡] [SPX500 ⚡] [BTC 🔒 Soon]`. Pro-locked tabs show "Unlock with Pro" on hover for Starter users.
- [x] **E-3-4** Engine halt banner: full-width banner when engine is halted (daily loss limit hit). Impossible to miss. Include reason + estimated reset time (UTC midnight).
- [ ] **E-3-5** Notification system for halt events: email user if engine is down >15 minutes. Log `[HALT_NOTIFY]`.
- [x] **E-3-6** Remove hardcoded "Uptime 99.7%" from Overview dashboard. Remove until real uptime data is available.
- [x] **E-3-7** PropFirmPanel: persist daily limit and consecutive losses config across page reloads (currently resets on every reload). Save to localStorage.
- [ ] **E-3-8** Pro Trade-Selectivity mode selector in Settings → Risk. Three options (Strict default / Balanced / Active), each showing **real backtested numbers** from E-2-10 — not adjectives. Pro/trial only, wrapped in `<ProGuard>`; Starter sees a locked teaser. Persists to `broker_accounts.bias_mode` with a confirmation toast ("Applies from your next trading session"). Log changes as `[BIAS_MODE]` audit entries.
- [ ] **E-3-9** No-trade-day explanation in the Live Logic Feed + cold-start state. When daily bias is `None` (mid-range close), surface: "Gold closed mid-range — no clear institutional draw. You're on Strict selectivity, so Glass Box is standing aside today. Switch to Balanced for more setups." Mandatory companion to E-3-8 — a selectivity dial requires showing its consequence.

---

### WEEK 4 — Live Data + Shareable Audit Link

- [ ] **E-4-1** Wire live verdict feed to Supabase realtime subscription. Currently polling — switch to `supabase.channel('signals').on('INSERT', ...)`. Reduces dashboard latency from ~2s to near-instant.
- [~] **E-4-2** Build shareable audit link feature: `POST /api/audit/generate` creates a UUID-keyed public record in Supabase. Returns `https://glassbox.io/audit/{uuid}`. Starter + Pro feature (generation is gated, viewing is public — no account needed to view). *(UI + Share button exist; data currently URL-encoded in token, not server-stored — server-side UUID storage still needed)*
- [~] **E-4-3** Audit link page (`/audit/{uuid}`): show trade entry/exit, ICT logic narrative, broker account name, timestamp. No auth required to view. *(`SharePage.tsx` exists at `/share/:token`; route and page done, server-side fetch pending)*
- [ ] **E-4-4** Audit link empty state doubles as an acquisition page: session times (next London/NY scan), scanning in progress message, "Want your own Glass Box?" signup CTA for Telegram followers.
- [x] **E-4-5** Verdict sidebar trigger on Overview recent signals rows. Currently clicking a row does nothing — should open the VerdictSidebar.
- [x] **E-4-6** PropFirmPanel: add profit target tracker field (completes the Pro tier spec). Daily drawdown and profit target must both display in Pro view.
- [x] **E-4-7** Add date range filter to Trades page.
- [ ] **E-4-8** Add "Explain this" tooltips for ICT terms in the dashboard (FVG, MSS, BOS, CHoCH, OB). Port the `Term` component from the landing page.

---

### WEEK 5 — Billing (Paystack)

- [ ] **E-5-1** Integrate Paystack subscriptions for Starter ($15/mo) and Pro ($49/mo). Use Paystack's subscription API, not one-off charge.
- [ ] **E-5-2** Paystack webhook handler (`POST /api/webhooks/paystack`): validate HMAC-SHA512 signature on every event. On `charge.success`: call Supabase RPC `activate_subscription(user_id, plan)` as an atomic transaction. Fail-closed if signature invalid (return 401, log `[WEBHOOK_INVALID]`).
- [x] **E-5-3** Add billing/subscription tab to Settings page. Show: current plan, next billing date, "Upgrade to Pro" CTA for Starter users, "Manage billing" link to Paystack customer portal. *(tab exists as stub; Paystack integration still needed)*
- [ ] **E-5-4** Plan tier gate in account creation: set `plan_tier` in `user_profiles` and `broker_accounts` from the `?plan=` query param at signup.
- [x] **E-5-5** Upgrade nudge: when a Starter user tries to add a second broker account, show modal — "Multiple accounts are a Pro feature. Upgrade to Pro ($49/mo) to add up to 10 accounts."
- [ ] **E-5-6** Landing page — add social proof section before public launch. Placeholder copy until real testimonials available.
- [ ] **E-5-7 STRETCH** FVG zones overlay on charts.
- [ ] **E-5-8** Add trial fields to `user_profiles`: `trial_tier TEXT DEFAULT 'pro'`, `trial_started_at TIMESTAMPTZ DEFAULT NOW()`, `trial_expires_at TIMESTAMPTZ DEFAULT NOW() + INTERVAL '30 days'`. Auto-set on new user creation trigger.
- [ ] **E-5-9** Trial expiry cron job: Supabase pg_cron task runs every hour, finds users where `trial_expires_at < NOW()` and `plan_tier` is still null/trial, marks account as `trial_expired`. Worker stops executing signals for expired-trial accounts (same fail-closed logic as tier gate).
- [ ] **E-5-10** Landing page CTA: change all instances of "Request Early Access" to "Start 30-Day Free Trial — No Credit Card Required." The trial is the primary acquisition hook.
- [ ] **E-5-11** Trial countdown banner on dashboard: appears on all dashboard pages during trial. Shows "X days remaining in your Pro trial" with a soft upgrade CTA. Not alarming — informative. Disappears when user converts to a paid plan.
- [ ] **E-5-12** Day 30 plan selection screen: full-page modal that appears when `trial_expires_at` is reached. Three clear paths: (1) Stay on Pro $49/mo, (2) Continue with Starter $15/mo, (3) Pause account (read-only). Cannot be dismissed without choosing a path.
- [ ] **E-5-13** Trial email drip campaign (5 emails via Resend/SendGrid): Day 1 welcome, Day 7 check-in ("Your first week on Pro"), Day 21 nudge ("9 days left — here's what you'll lose"), Day 28 urgency ("2 days left — choose your plan"), Day 30 cutoff ("Your trial has ended").
- [ ] **E-5-14** Audit link permanence post-trial: links generated during trial remain live permanently regardless of plan chosen. Add DB note to `audit_links` table: no cascade delete on user account changes.

---

### WEEK 6 — Landing Page + QA

- [ ] **E-6-1** Landing page final polish: two-track pricing cards fully matching the approved pricing ($15 Starter / $49 Pro), feature comparison table, social proof section live.
- [ ] **E-6-2** Full end-to-end QA pass: Starter signup → MT5 connect → signal executes → audit link generated → audit link viewed without account → upgrade flow → Paystack billing → Pro features unlock.
- [x] **E-6-3 STRETCH** Session summary cards: auto-post to Overview after each London/NY session closes. Show: scan count, verdict count, trade count, session P&L, halt events.
- [ ] **E-6-4 STRETCH** Date range filter on audit link page for signal providers reviewing their history.

---

## DEFERRED — Pick Up After Relevant Milestone Ships

---

### T-DEFER-1: Lifetime Deal Logistics
**What:** Spec how to sell lifetime accounts before Paystack monthly billing ships.
**Why:** Immediate cash + early community seeding. $99 Starter / $199 Pro lifetime, capped 50-100 users.
**Pros:** Revenue before subscription billing is live; creates word-of-mouth.
**Cons:** Permanent support obligation; anchor weight if product pivots.
**Context:** The trading tool market (Fox Signals $69, Forex Tester $49-150) responds well to lifetime deals. Cap tightly. Logistics: WHERE to sell (Gumroad/Lemon Squeezy), how to manually provision lifetime tier in Supabase, how lifetime users are treated when monthly billing ships.
**Effort:** S (human) / XS (CC)
**Priority:** P2
**Blocked by:** Week 5 Paystack billing live and tested

---

### T-DEFER-2: Referral / Viral Loop
**What:** Product-level referral mechanic — e.g. $5/mo credit per referred Starter user.
**Why:** Accelerates the B2B2C flywheel without paid acquisition.
**Pros:** Compounds organic growth; followers who refer others become more sticky.
**Cons:** Billing complexity; abuse surface (fake referrals).
**Context:** Design requires real user data to calibrate incentive amount. Don't speculate without knowing actual churn / LTV. First: observe whether organic sharing is working from audit links alone.
**Effort:** M (human) / S (CC)
**Priority:** P2
**Blocked by:** 30+ paying users with observed referral behavior

---

### T-DEFER-3: Pricing Page Copy
**What:** Write headline + value prop for each tier in ≤10 words each.
**Why:** Landing page is incomplete without clear tier differentiation.
**Pros:** Improves conversion from landing page.
**Cons:** Requires knowing which features resonate (validate with first users first).
**Context:** Current plan: Starter = "auto-execute ICT signals on your MT5 account" / Pro = "full ICT transparency for your prop firm challenge." Validate with first 5 users which framing resonates before finalising.
**Effort:** XS (human)
**Priority:** P3
**Blocked by:** Week 6 landing page sprint

---

### T-DEFER-4: Cold Start UX
**What:** Design the dashboard experience between "first login" and "first trade executes."
**Why:** New users who see an empty dashboard and don't know what's happening churn fast.
**Pros:** Reduces early churn from "nothing is happening."
**Cons:** Over-engineering before validating the product works end-to-end.
**Context:** Week 2 onboarding checklist (connect MT5 → risk config → wait for session) partially addresses this. The specific moment: user completes checklist, knows Glass Box is scanning, and waits. Clock says 16 hours to next London session. What do they see? Session countdown timer? Last EURUSD structure analysis?
**Effort:** S (human) / S (CC)
**Priority:** P2
**Blocked by:** Week 2 onboarding ships + 3+ users observed in cold start state

---

### T-DEFER-5: Edge Function Cold-Start Mitigation
**What:** Migrate `/audit/{uuid}` serving from Supabase Edge Function to Supabase RPC (runs in DB, no cold start) for burst traffic handling.
**Why:** Viral Telegram link sharing creates burst traffic. Edge Functions have cold-start latency (~500ms-2s) that hurts first impressions.
**Pros:** Sub-100ms audit link loads; survives viral traffic spike.
**Cons:** RPC is a Postgres stored procedure — slightly more complex to maintain.
**Context:** Acceptable for beta (50-100 users). Migrate when p95 audit link latency >1s in production. Trigger: monitor `[AUDIT]` log response times after first viral share.
**Effort:** S (human) / S (CC)
**Priority:** P2
**Blocked by:** Audit link live in production + traffic observed

---

### T-DEFER-6: MT5 Broker Normalization
**What:** A broker normalization layer that maps canonical symbol names (XAUUSD, EURUSD) to broker-specific names (XAUUSDm, GOLD, EURUSDm) plus validates minimum spread/swap thresholds.
**Why:** Different MT5 brokers use different symbol names and have wildly different spreads (especially XAUUSD). The current ict_model.py assumes symbol names work across all brokers.
**Pros:** Multi-broker support; protects users from executing on symbols with prohibitive spreads.
**Cons:** Requires maintaining a broker compatibility table.
**Context:** Current workaround: CLAUDE.md documents live suffix (EURUSDm) vs backtest (EURUSD). This needs to scale to XAUUSD, NAS100 etc across IC Markets, Exness, FBS, etc. Required before any multi-broker public rollout.
**Effort:** M (human) / S (CC)
**Priority:** P2
**Blocked by:** Second MT5 broker user onboarded

---

### T-DEFER-7: Provider Onboarding Infrastructure (Phase 2)
**What:** A referral link mechanism that auto-provisions Glass Box accounts for a signal provider's Telegram followers.
**Why:** The 10x vision: provider posts their Glass Box referral link → followers click → accounts auto-created → followers auto-linked to provider's signal feed.
**Pros:** Removes the "followers must manually sign up" friction; scales the B2B2C motion.
**Cons:** Significant engineering (referral link generation, follower account provisioning, provider↔follower data model).
**Context:** Current state: followers must manually go to glassbox.io/signup. Phase 1 (6-week build) proves the model works manually first. This is Phase 2, post-PMF. Do NOT build before at least 1 active provider relationship is established.
**Effort:** L (human) / M (CC)
**Priority:** P1 (Phase 2)
**Blocked by:** Active signal provider partnership established + first Starter user from Telegram conversion

---

## ENGINEERING BACKLOG

### T-ENG-1: Pattern Overlay Suite
FVG zones in Week 5 (stretch). Full suite (OB blocks, MSS markers, BOS levels) post-launch.

### T-ENG-2: Crypto Strategy Runner
BTC/ETH — 24/7, separate strategy needed (not London/NY session model). Post-launch.

### ~~T-ENG-3: Replay Mode~~ ✅ Done
`TradeReplayChart.tsx`, `PlaybackControls.tsx`, `TimeframeSelector.tsx`, `EventLog.tsx`, `ContextCascade.tsx`, `useReplaySession.ts` all exist. Shipped ahead of schedule.

### ~~T-ENG-4: Session Summary Cards~~ ✅ Done
See E-6-3. `useSessionSummaries.ts` exists; summary cards auto-generated after London/NY session close.
