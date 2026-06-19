# Glass Box — Production Readiness

Last updated: 2026-06-16
Branch: claude/gstack-global-install-f3ubqy

This document tracks everything Glass Box needs before it can acquire paying users — product, pricing, marketing, and architecture. Updated from the full product diagnostic session on 2026-06-16.

---

## Status Overview

| Area | Status | Blocker |
|---|---|---|
| Core trading engine | ✅ Operational | — |
| Multi-account execution | ✅ Operational | — |
| Live dashboard (Live Mode + Replay) | ✅ Operational | — |
| Trade history + VerdictSidebar | ✅ Operational | — |
| Prop Firm Panel | ✅ Operational | Profit target field missing |
| Landing page | 🔶 In progress | Pricing wrong, two CTAs missing |
| Settings page | 🔶 In progress | Risk tab not wired, no billing tab |
| Billing / subscription | ❌ Not built | #1 blocker to monetisation |
| Legal / compliance review | ❌ Not done | Blocks public launch of signal-following use case |
| Shareable audit link | ❌ Not built | Blocks B2B2C Telegram acquisition motion |
| Onboarding flow | ❌ Not built | New users land on empty dashboard |

---

## Go-To-Market Strategy

*From office-hours session — approved 2026-06-16. Full doc: `.md/GLASS_BOX_OVERVIEW.md`*

### Target Segments

**Tier 1 — Starter ($15/mo): The Telegram Signal Follower**
- Passive investor following ICT-adjacent Telegram signal channels, primarily Nigeria and emerging markets
- Job to be done: auto-execute signals from a source they trust, and have an audit log they can share with someone experienced to explain what happened
- Word of mouth is the primary growth mechanism for this segment
- Acquisition: DM 3–5 Telegram ICT signal providers, offer free 6-month Pro account in exchange for a single post to their channel

**Tier 2 — Pro ($49/mo): The Prop Firm Challenge Candidate**
- ICT-educated trader running or about to run an FTMO/The5ers challenge with a bot
- Job to be done: know in real time that the bot is following the firm's rules; audit any trade if challenged
- Acquisition: prop firm challenge communities, YouTube ICT content, comparison vs generic MT5 EAs

### Recommended Launch Approach

Dual-launch, Starter-first bias:
1. First 30 days: focus on Telegram signal provider partnerships (community-first)
2. Simultaneously: finish billing integration and landing page two-track structure
3. Upgrade path: in-app nudge from Starter to Pro when user adds a second broker account

### The Assignment (Week 1)

DM five ICT signal providers on Telegram. Not to sell. To ask: "I'm building a transparency layer for MT5 execution — would you be willing to look at a demo? I think it could make your channel look more professional." Goal: one "yes, show me" = first real demand signal.

---

## Pricing

*From deep-research session and market analysis — 2026-06-16*

### Market Research Findings

| Comparable product | Price | Model |
|---|---|---|
| ICT Silver Bullet EA (MQL5) | $349–$449 | One-time |
| ICT UNO EA v2 | $14.99 | One-time |
| Prop Firm One Premium | $44.99/mo | Subscription |
| Tradesea OmniProp | $97/mo | Subscription |
| Telegram signal services | $50–$150/mo | Subscription |
| Nigerian VIP signal tiers | $49–$199/mo | Subscription |
| Fox Signals (AppSumo lifetime) | $69 | One-time |

**Nigerian SaaS impulse-buy threshold:** $10–$15/mo. Above $15, users enter deliberation mode.

### Recommended Pricing Structure

| Tier | Price | Accounts | Core value |
|---|---|---|---|
| **Observer** | Free | 0 (view only) | Read-only dashboard + shareable audit link — enables B2B2C signal provider motion |
| **Starter** | $15/mo | 1 | Auto-execution on Starter markets + full audit log + shareable link |
| **Pro** | $49/mo | Up to 10 | Everything above + Replay Mode + full Prop Firm Panel + US Indices |
| **Enterprise** | Custom | 50+ | Dedicated VM, SLA, custom risk config |

**Why $15 not $20 for Starter:** Nigerian impulse-buy threshold is $10–$15. At $15, you stay below the deliberation line. The target Starter user is coming from free Telegram signals — the gap from $0 to $15 is smaller than $0 to $20.

**Why $49 for Pro:** Prop Firm One Premium charges $44.99/mo with no replay and no ICT-specific transparency. Glass Box is $4 more expensive and significantly more capable for ICT traders. At ~5% of a typical FTMO challenge fee ($600–$1,000), the insurance framing holds.

### Pre-Launch Monetisation (Before Billing Ships)

Lifetime deal to generate immediate cash and seed the early community:
- **Starter lifetime: $99** (= 6.6 months)
- **Pro lifetime: $199** (= ~4 months)

Cap at 50–100 users to create urgency. These early users become the word-of-mouth community. The trading tool market expects and responds well to lifetime deals (Fox Signals $69, Forex Tester $49–$150).

### Pricing Page: What Each Tier Includes

| Feature | Observer (Free) | Starter ($15/mo) | Pro ($49/mo) |
|---|---|---|---|
| Accounts | View only | 1 | Up to 10 |
| Auto-execution | — | ✓ | ✓ |
| Live Logic Feed | ✓ (view) | ✓ | ✓ |
| Shareable audit link | ✓ | ✓ | ✓ |
| Trade history + CSV | ✓ | ✓ | ✓ |
| Replay Mode | — | — | ✓ |
| Prop Firm Panel (full with profit target) | — | Basic | ✓ |
| Live ICT condition feed | — | — | ✓ |
| Multi-account execution | — | — | ✓ |
| US Indices (NAS100, US30, SPX500) | — | — | ✓ |
| Crypto (BTC, ETH) | — | — | Coming Soon |

---

## Frontend Design Review Summary

*Full review doc: `.md/GLASS_BOX_DESIGN_REVIEW.md` — 2026-06-16*

### Fix Before Any User Sees This

| Priority | Issue | Fix |
|---|---|---|
| 1 | Landing page shows $49/$99 — strategy approved $15/$49 | Update `Landing.tsx` pricing section |
| 2 | RiskTab "Save Defaults" button is non-functional | Wire it up or add "coming soon" label |
| 3 | No onboarding flow for first-time users | Add checklist + empty-state CTA for new accounts |

### Build Next

| Priority | Feature | Why |
|---|---|---|
| 1 | Shareable audit link | Unlocks the Telegram B2B2C acquisition motion |
| 2 | Billing/subscription tab in Settings | Without this, nothing monetises |
| 3 | Profit target tracker in PropFirmPanel | Completes the Pro tier spec |

### Other Key Issues Found

**Landing page:**
- Single CTA track — needs two visible paths: "auto-execute signals" (Starter) and "prop firm challenge" (Pro)
- "Watch Live Demo" scrolls to features section, not a demo — rename or link properly
- Footer dead links (About, Blog, Careers) — remove until pages exist
- "Start Free Trial" promise with no billing live — change to "Request Early Access"
- No social proof section

**Auth pages:**
- Hardcoded hex colours (`#141921`, `#0f1419`) — should use design tokens (`bg-bg-surface`, `bg-bg-base`)
- No "Forgot password" link on Login
- No password length hint on SignUp
- Post-signup redirects to `/sign-in` — should go to `/dashboard` after email confirmation

**Dashboard:**
- Overview "Uptime 99.7%" appears hardcoded — remove until real
- Overview recent signals rows are not clickable (no VerdictSidebar trigger)
- "Chart Debugger" in sidebar should be renamed "Replay Mode" to match marketing
- Mixed emoji + Unicode icons in sidebar nav — standardise
- No date range filter in Trades page
- PropFirmPage config (daily limit, consecutive losses) resets on every page reload — needs persistence
- Settings has no subscription/billing tab
- No notification system for engine halt events

**New concepts to add:**
1. Observer free tier (enables B2B2C motion)
2. Onboarding checklist for new users
3. Engine halt banner (full-width, impossible to miss)
4. Profit target tracker in PropFirmPanel
5. "Explain this" tooltips for ICT terms in the dashboard (port from landing page `Term` component)
6. Session summary cards after each London/NY session closes
7. Upgrade nudge when Starter user tries to add a second account

---

## Market Tiering Architecture

*Discussion — 2026-06-16*

### Which Markets Per Tier

| Market | Asset class | Tier | Build priority | Session logic |
|---|---|---|---|---|
| EURUSD | Forex | Starter + Pro | Live now | London 09:00–11:00, NY 13:30–16:00 NGT |
| XAUUSD | Gold | Starter + Pro | #1 — build next | Same London/NY windows |
| GBPUSD | Forex | Starter + Pro | #2 | Same windows |
| USDJPY | Forex | Starter + Pro | #2 | Same windows |
| NAS100 | US Indices | Pro only | #3 | NYSE open 15:30–17:30 NGT |
| US30 | US Indices | Pro only | #3 | NYSE open 15:30–17:30 NGT |
| SPX500 | US Indices | Pro only | #3 | NYSE open 15:30–17:30 NGT |
| BTC/ETH | Crypto | Pro only | #4 | 24/7, separate strategy needed |

**Why XAUUSD on Starter is non-negotiable:** Gold is the most traded instrument by Nigerian retail traders. Many Telegram signal channels the Starter acquisition plan depends on are Gold channels. Gating XAUUSD behind Pro cuts the Starter target market in half before launch.

**Why US Indices are Pro-only:** Require a different session window (NYSE open, not London) — a backend config change. Naturally associated with prop firm challenge accounts, which is the Pro target persona.

**Why Crypto is Pro + deferred:** Runs 24/7 with its own strategy logic (confirmed — not the same London/NY session model). Separate runner build required. Don't block indices on crypto.

### How It Works (Architecture)

**Scanning is global, filtering is per-account:**

1. Strategy engine runs one instance per active symbol (one `ict.py` for EURUSD, one for XAUUSD, etc.)
2. Every verdict is published to Redis `signals` channel with a `symbol` field
3. Each worker (one per broker account) reads the account's `enabled_symbols` list from `broker_accounts.symbol`
4. Worker skips any signal whose symbol is not in the account's enabled list
5. All enabled-symbol signals execute on the same single broker account

**Storage:** `broker_accounts.symbol` stores a comma-separated list (`"EURUSD,XAUUSD,GBPUSD"`). No DB migration needed — the existing column accepts this format and is backward compatible with single-value records.

**User experience:**
- Account is pre-configured with all tier-applicable markets at creation (all checked by default)
- User can deselect any markets they don't want from Settings
- Deselecting a market means: "don't execute signals for this symbol on my account" — not "stop scanning globally"

**Dashboard market tabs:**
- Starter view: `[EURUSD] [GBPUSD] [XAUUSD] ...`
- Pro view: `[EURUSD] [GBPUSD] [XAUUSD] ... [NAS100 ⚡] [US30 ⚡] [SPX500 ⚡] [BTC 🔒 Soon]`
- Pro-locked markets show "Unlock with Pro" on hover for Starter users

---

## Critical Path to First Revenue

In order:

1. **Legal/compliance review** — pre-public-launch blocker for the signal-following use case. Run beta/waitlist-only until resolved. Fallback if unfavourable: reposition Starter as "personal automation tool" (user sets up their own ICT rules, not copying a third-party signal).

2. **Billing integration** — nothing monetises without this. Top engineering priority. Enables Starter + Pro subscriptions and the plan-tier gate for market access.

3. **Shareable audit link** — small feature, big unlock. Signal providers need to share their followers' Glass Box results without logging in. Without this, the B2B2C acquisition motion doesn't work.

4. **Landing page two-track structure** — two CTAs: "auto-execute signals" (Starter) and "prop firm challenge" (Pro). Correct pricing to $15/$49.

5. **Onboarding flow** — first-login checklist so new users know to connect their MT5 account and what happens next.

6. **XAUUSD market expansion** — make `broker_accounts.symbol` configurable as a list, run a second strategy instance for XAUUSD. This immediately increases Starter tier value for the Nigerian market.

---

## 30 / 60 / 90 Day Success Criteria

**30 days:**
- Billing integration live
- Landing page live (two audience tracks)
- At least 1 signal provider partnership active
- Legal/compliance review complete or beta-gated launch in place

**60 days:**
- 10 paying Starter users
- First Pro account sold
- Month-1 churn below 20%

**90 days:**
- Word-of-mouth referral rate visible in attribution data
- At least one prop firm challenge success story documented
- Month-2 churn below 15%
