# Glass Box Frontend — Design Review

Generated: 2026-06-16
Branch: claude/gstack-global-install-f3ubqy
Repo: calibaba276/trade-bot

---

## Landing Page

### What's Working

The "glass box vs. black box" positioning is strong and consistent throughout. The `Term` tooltip system for jargon (FVG, MSS, ICT) is genuinely good UX for non-technical Starter-tier users. The PropFirmWidget on the landing page lets challenge candidates preview the product before signing up. The TrustBar signals (`<20ms Execution Latency`, `Azure Key Vault Security`) are specific and credible. The `HeroLiveFeed` component that streams market activity in the hero is a strong real-time credibility signal.

### Open Issues

**"Watch Live Demo" → `#features`**
This CTA scrolls to the features section, not a demo. Replay Mode is your biggest differentiator for the Pro tier — if you can't show it live on the landing page, rename the CTA. "See how it works" or "Read the feature breakdown" is more honest.

**Dead footer links**
`About`, `Blog`, `Careers`, `Contact` — all `href="#"`. For a financial product this is a trust issue. Remove these until the pages exist, or replace them with something real.

**"Start Free Trial" with no billing**
The page promises "30-day free trial, no credit card required" but billing isn't live. Change the CTA to "Request Early Access" or "Join the Waitlist" until billing ships. A promise you can't honor at checkout kills trust harder than no promise at all.

**No social proof**
Zero testimonials, community signals, or use counts. Even placeholder language anchored in the actual target communities would help ("Used by traders in FTMO challenge communities"). The prop firm candidate is specifically skeptical of bot claims — this is the hardest segment to convert without social proof.

**Missing B2B2C concept on landing page**
The shareable audit link for signal providers isn't surfaced anywhere on the landing page. Add "Share your audit trail — let your signal provider see exactly what happened" somewhere in the feature list.

### Resolved

- ✅ **Pricing mismatch** — now shows $15/mo Starter and $49/mo Pro
- ✅ **Two acquisition tracks** — hero has separate paths for signal follower and prop firm challenger

---

## Auth Pages (Login + SignUp)

### What's Working

The live NGT clock in the auth header is remarkable. `GLASS BOX v2.1 · LONDON SESSION · 09:43:22 NGT` — that single status line does more trust-building than a paragraph of marketing copy. "All sessions logged" in the footer is perfectly brand-consistent. The `AUTHENTICATE` button label is exact. Zero-radius inputs are clean and intentional. No social login clutter.

### Open Issues

**Hardcoded hex colors throughout**
Auth pages use `bg-[#141921]`, `bg-[#0f1419]`, `#2a3040`, etc. The entire design token system in `index.css` exists to avoid this. Every color in these files should be a CSS variable (`bg-bg-surface`, `bg-bg-base`, `border-border-subtle`). Auth was built before or outside the token system and needs to be brought into it, or a future brand change means hunting hex values instead of changing one variable.

### Resolved

- ✅ **No password hint** — "At least 6 characters" hint now shows inline in SignUp
- ✅ **No "Forgot password" link** — link now exists on Login
- ✅ **Post-signup flow** — confirmation message now says the link takes you to dashboard (no 3s redirect to /sign-in)
- ✅ **Inconsistency between Login and SignUp** — both pages now show the live session + NGT clock

---

## Dashboard — Overview

### What's Working

The 4-card stat grid (Engine Status, Today P&L, Open Positions, Win Rate 30d) is clean. `LiveLogicFeed` + `PropFirmPanel` in a 3:2 grid column split is the right layout. The win rate progress bar in the stat card is a nice micro-detail. The Recent Signals table provides a useful entry point.

### Resolved

- ✅ **No onboarding state for new users** — empty state with "Connect your first MT5 account" CTA added; `OnboardingModal` added for first-login flow
- ✅ **"Uptime 99.7%" hardcoded** — removed; engine status is now market-hours-derived
- ✅ **Overview recent signals not clickable** — rows now have "Verdict →" link that opens VerdictSidebar

---

## Dashboard — Live Feed

### What's Working

The auto-scroll with pause-on-manual-scroll is thoughtful UX that very few log UIs get right. The "PAUSED / Resume →" pill is clean. The per-market tab system is well implemented.

### Issues

**Intro paragraph undersells the product**
`FeedPage.tsx` — "The bot's internal thought process, streamed in real time" is fine but generic. This is the transparency USP. Rewrite to something more specific: "Every pattern scanned, every condition verified, every order logged — timestamped in West Africa Time. This is the full audit trail."

**Naming inconsistency**
The sidebar calls it "Live Feed", the page heading calls it "Live Logic Feed", the component is `LiveLogicFeed`. Pick one name and use it everywhere.

---

## Dashboard — Replay Mode

### Resolved

- ✅ **Naming collision** — nav item renamed "Replay Mode"
- ✅ **Mixed icon system** — sidebar icons are now Unicode glyphs, not emoji

---

## Dashboard — Trades

### What's Working

One of the strongest pages. CSV export is a practical feature that prop firm users need. Direction/status/scenario filters are the right choices. Pagination at 25 rows is appropriate. The `VerdictSidebar` integration is the core differentiating feature of the product and it works well here.

### Resolved

- ✅ **No date range filter** — date range filter added to Trades page
- ✅ **"View" button underselling** — renamed "Verdict →"
- ✅ **"SL" column header** — expanded to "Stop Loss" for clarity

---

## Dashboard — Prop Firm Panel / Page

### What's Working

The Halt Simulation is excellent — showing "X losing trades before halt at $Y daily limit" is one of the most useful tools for a prop firm candidate evaluating whether to trust the bot. The color-coded progress bar (green → amber → pulsing red) is exactly right. The two-column layout (live constraints left, configuration right) is clean.

### Resolved

- ✅ **Config doesn't persist** — PropFirmPage config now persists to localStorage
- ✅ **Profit target progress missing** — profit target field and progress bar added to PropFirmPage config
- ✅ **Daily reset timezone label** — label now reads "Resets at midnight UTC (1:00 AM NGT)"

---

## Dashboard — Settings

### Open Issues

**No account limit enforcement**
There's no restriction on how many accounts a Starter user can add. When billing is live, the Starter plan (1 account) vs Pro plan (10 accounts) tier gate needs to be enforced here. Wire this before billing ships.

**No follow-up message after adding an account**
After adding an MT5 account, there's no message about what happens next. Add: "The engine will begin scanning your account during the next Session."

### Resolved

- ✅ **RiskTab "Save Defaults" non-functional** — "Save Defaults" now saves to localStorage
- ✅ **No billing/subscription tab** — Subscription & Billing tab now exists in Settings
- ✅ **Upgrade intercept** — when a Starter user tries to add a second account, an upgrade modal appears ("Pro plan supports up to 10 accounts")

---

## Dashboard — Layout

### Open Issues

**Documentation link is dead**
The sidebar has a "?" Documentation link that goes `href="#"`. Either remove it or link to real docs.

### Resolved

- ✅ **No notification system** — toast notification system added (`ToastContainer`); market open/close events fire toasts; engine halt banner displays across the full dashboard

---

## Things to Remove

| Item | Location | Status |
|---|---|---|
| Footer dead links (About, Blog, Careers) | `Landing.tsx` | ❌ Still `href="#"` — trust issue |
| "Start Free Trial" CTA / free trial copy | `Landing.tsx` | ❌ Billing not live; promise can't be honored |

---

## New Concepts — Status

| Feature | Status |
|---|---|
| Shareable audit link | ✅ Done — `SharePage.tsx` + Share Audit button; note: data is URL-encoded, not server-stored (security gap) |
| Onboarding checklist for new users | ✅ Done — `OnboardingModal.tsx` + empty state CTA |
| Engine halt banner | ✅ Done — red banner across full dashboard |
| Profit target tracker in PropFirmPanel | ✅ Done — progress bar + profit target field in PropFirmPage |
| Session summary cards | ✅ Done — auto-generated after London/NY session close |
| Upgrade nudge at account add limit | ✅ Done — modal intercepts when Starter tries to add second account |
| "Explain This" tooltips in dashboard | ❌ Not done — `Term` component not ported from landing page to dashboard/feed |

---

## Summary

The design system is solid — the token architecture, `font-mono` consistency, and component library are well thought out. The VerdictSidebar is genuinely differentiated and the PropFirmPanel's color-coded drawdown bar is the right instinct. The auth pages' live NGT clock is one of the best brand moments in the product.

### Still to fix

| Priority | Issue | Fix |
|---|---|---|
| 1 | Footer dead links (About, Blog, Careers, Contact) | Remove columns or replace with real pages |
| 2 | "Start Free Trial" / "30-day free trial" copy | Change to "Request Early Access" until billing ships |
| 3 | Auth pages use hardcoded hex colors | Replace inline styles with CSS variables |
| 4 | "Explain This" tooltips not in dashboard | Port `Term` component to Live Logic Feed and VerdictSidebar |
| 5 | Documentation link is dead | Remove until docs exist |
| 6 | No social proof (fabricated data) | Replace placeholder stats and testimonials with real data before marketing |
| 7 | No account limit enforcement in Settings | Wire Starter/Pro tier gate before billing ships |
| 8 | Share link encodes data in URL | Move to server-side `shared_sessions` table in Supabase |

---

*Glass Box — See everything. Trust what you see.*
