# Glass Box — TODOS

Deferred items from planning. Pick up when the relevant milestone ships.

---

## From 6-Week GTM Plan (2026-06-21)

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
**Context:** Current plan: Starter = "auto-execute ICT signals on your MT5 account" / Pro = "full ICT transparency for your prop firm challenge." Validate with first 5 users which framing resonates before finalizing.
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

## Engineering Backlog

### T-ENG-1: Pattern Overlay Suite
FVG zones in Week 5 (stretch). Full suite (OB blocks, MSS markers, BOS levels) post-launch.

### T-ENG-2: Crypto Strategy Runner
BTC/ETH — 24/7, separate strategy needed (not London/NY session model). Post-launch.

### T-ENG-3: Replay Mode
Chart replay for historical trade review. Pro-only feature. Post-launch.

### T-ENG-4: Session Summary Cards
Auto-posted to overview after each London/NY session closes. Shows: N scans, N verdicts, N trades, P&L, halt events. Post-Week-4 (requires live data infrastructure).
