# Glass Box Frontend — Design Review

Generated: 2026-06-16
Branch: claude/gstack-global-install-f3ubqy
Repo: calibaba276/trade-bot

---

## Landing Page

### What's Working

The "glass box vs. black box" positioning is strong and consistent throughout. The `Term` tooltip system for jargon (FVG, MSS, ICT) is genuinely good UX for non-technical Starter-tier users. The PropFirmWidget on the landing page lets challenge candidates preview the product before signing up. The TrustBar signals (`<20ms Execution Latency`, `Azure Key Vault Security`) are specific and credible. The `HeroLiveFeed` component that streams market activity in the hero is a strong real-time credibility signal.

### Critical Issue — Pricing Mismatch

`Landing.tsx` (pricing section) shows **Starter = $49/mo** and **Pro = $99/mo**. The approved strategy doc settled on **$15/mo Starter** and **$49/mo Pro**. This is not a minor discrepancy. The entire Starter tier pricing rationale was that $15 is "below the threshold of deliberation" — an impulse buy. $49 is not. Fix this before any marketing outreach.


### Issues

**One acquisition track, not two**
The hero has a single CTA path. The strategy doc specifically calls for a landing page with two visible tracks: "I want to auto-execute signals" (Starter, Telegram follower) and "I'm running a prop firm challenge" (Pro). Right now both users land in the same undifferentiated hero. The Telegram signal follower doesn't immediately see themselves in the copy — the hero is written entirely for the Pro/transparency narrative.

**"Watch Live Demo" → `#features`**
This CTA scrolls to the features section, not a demo. Replay Mode is your biggest differentiator for the Pro tier — if you can't show it live on the landing page, rename the CTA. "See how it works" or "Read the feature breakdown" is more honest.

**Dead footer links**
`About`, `Blog`, `Careers`, `Contact` — all `href="#"`. For a financial product this is a trust issue. Remove these until the pages exist, or replace them with something real.

**"Start Free Trial" with no billing**
The page promises "30-day free trial, no credit card required" but billing isn't live. Change the CTA to "Request Early Access" or "Join the Waitlist" until billing ships. A promise you can't honor at checkout kills trust harder than no promise at all.

**No social proof**
Zero testimonials, community signals, or use counts. Even placeholder language anchored in the actual target communities would help ("Used by traders in FTMO challenge communities"). The prop firm candidate is specifically skeptical of bot claims — this is the hardest segment to convert without social proof.

**Missing B2B2C concept**
The shareable audit link for signal providers isn't surfaced anywhere on the landing page. The B2B2C motion requires that providers can see their followers' Glass Box results without logging in. Add "Share your audit trail — let your signal provider see exactly what happened" somewhere in the feature list. This is the key trust mechanism for the Starter tier.

---

## Auth Pages (Login + SignUp)

### What's Working

The live NGT clock in the auth header is remarkable. `GLASS BOX v2.1 · LONDON SESSION · 09:43:22 NGT` — that single status line does more trust-building than a paragraph of marketing copy. "All sessions logged" in the footer is perfectly brand-consistent. The `AUTHENTICATE` button label is exact. Zero-radius inputs are clean and intentional. No social login clutter.

### Issues

**Hardcoded hex colors throughout**
Auth pages use `bg-[#141921]`, `bg-[#0f1419]`, `#2a3040`, etc. The entire design token system in `index.css` exists to avoid this. Every color in these files should be a CSS variable (`bg-bg-surface`, `bg-bg-base`, `border-border-subtle`). Auth was built before or outside the token system and needs to be brought into it, or a future brand change means hunting hex values instead of changing one variable.

**No password hint**
`SignUp.tsx` validates minimum 6 characters after submit. Show the constraint before: a small hint below the password field ("At least 6 characters"). Errors on submit are worse UX than inline hints.

**No "Forgot password" link on Login**
This will generate support tickets. Standard omission, easy fix.

**Post-signup flow**
After signing up, the user sees a success message then redirects to `/sign-in` after 3 seconds. The user then has to log in again. If Supabase email confirmation sends the user back to the app, the post-confirmation redirect should go straight to `/dashboard`. The current flow is: sign up → wait 3s → sign in again → dashboard. One step too many.

**Inconsistency between Login and SignUp**
Login shows the live trading session (`getTradingSession()`: "LONDON SESSION", "NY SESSION", etc.). SignUp shows "ACCESS REQUEST" — a different pattern. Either add the session display to SignUp or replace Login's session label with "AUTHENTICATION" for consistency. The live session is the stronger choice — keep it in both.

---

## Dashboard — Overview

### What's Working

The 4-card stat grid (Engine Status, Today P&L, Open Positions, Win Rate 30d) is clean. `LiveLogicFeed` + `PropFirmPanel` in a 3:2 grid column split is the right layout. The win rate progress bar in the stat card is a nice micro-detail. The Recent Signals table provides a useful entry point.

### Issues

**No onboarding state for new users**
First login: empty stat cards, empty recent signals, empty feed. There's no next action visible. The user needs a prominent "Connect your first MT5 account → Settings" CTA. Without it, first-time users don't know what to do and will churn. The `EmptyState` component exists — use it at the page level for new users with zero accounts connected.

**"Uptime 99.7%" appears to be hardcoded**
The Engine Status card sub-text includes "Uptime 99.7% · realtime stream connected". If this is not real uptime data from your infrastructure, remove it. Fabricated precision actively damages trust for technical users.

**Overview recent signals rows are not clickable**
The Trades page opens the `VerdictSidebar` from a "View" button. The Overview's Recent Signals table has no such interaction — rows just sit there. Either make entire rows clickable (opens VerdictSidebar), or add a "View" link per row like Trades has.

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

## Dashboard — Chart Debugger (Replay Mode)

### Issues

**Naming collision**
The sidebar says "Chart Debugger". The marketing copy calls it "Replay Mode." A Pro user who bought specifically for "Replay Mode" will scan the nav and not immediately find it. Rename the nav item to "Replay Mode" or "Chart Replay."

**Mixed icon system in sidebar**
Nav uses text glyphs for most items (▦, ≋, ≡, ⚙) but emoji for Chart Debugger (📈) and Prop Firm Panel (🛡). Emoji render differently across OS/browser, breaking visual consistency. Replace both with Unicode symbols.

---

## Dashboard — Trades

### What's Working

One of the strongest pages. CSV export is a practical feature that prop firm users need. Direction/status/scenario filters are the right choices. Pagination at 25 rows is appropriate. The `VerdictSidebar` integration is the core differentiating feature of the product and it works well here.

### Issues

**No date range filter**
Direction, status, and scenario filters exist but there's no date filter. A prop firm user auditing a specific challenge week needs to filter by date range. This is a notable gap.

**"View" button is underselling**
The button that opens the VerdictSidebar is labeled "View". "Verdict →" or "See Verdict" is more brand-consistent and tells users what they're about to open.

**SL column coloring could be misread**
`text-bear` (red) on the Stop Loss column could be misread as "this trade is a loss" by a new user. The coloring is semantically correct (red = risk) but consider expanding the column header from "SL" to "Stop Loss" for clarity.

---

## Dashboard — Prop Firm Panel / Page

### What's Working

The Halt Simulation is excellent — showing "X losing trades before halt at $Y daily limit" is one of the most useful tools for a prop firm candidate evaluating whether to trust the bot. The color-coded progress bar (green → amber → pulsing red) is exactly right. The two-column layout (live constraints left, configuration right) is clean.

### Issues

**Config doesn't persist**
`PropFirmPage.tsx` holds `dailyLimit` and `maxConsec` in local React state. Every page reload resets to $1000 / 3. This configuration needs to be stored per broker account in Supabase. Until billing is live, `localStorage` is an acceptable interim solution.

**Profit target progress is missing**
The product spec explicitly calls for "profit target progress" in the Prop Firm Panel. This tracks how close the user is to hitting the challenge's profit target (e.g., 8% for FTMO Phase 1). This field is not in `PropFirmPanel.tsx`. Without it, the panel only shows downside protection — not upside progress. This is a significant gap in the Pro tier value proposition.

**Daily reset timezone label**
`PropFirmPanel.tsx` calculates reset time from UTC midnight. The trading day is in NGT (UTC+1). The label should specify the timezone: "Resets at midnight UTC (1:00 AM NGT)" so Nigerian users understand exactly when limits clear.

---

## Dashboard — Settings

### Issues

**RiskTab "Save Defaults" is non-functional**
The `RiskTab` renders inputs with `defaultValue` but no `onChange` handlers. The "Save Defaults" button has no save function. This is a placeholder that *looks* functional. Either wire it to actually save to Supabase/localStorage, or add a visible "Coming soon" badge on the tab. A fake save button is actively misleading.

**No billing/subscription tab**
The Settings page has "Broker Accounts", "Risk Configuration", "Profile & Security". It is missing "Subscription & Billing." This is the #1 dependency in the strategy doc and the natural upgrade path from Starter to Pro lives here. The tab should exist now, even as a stub that shows current plan and a "Billing integration coming soon" message.

**No account limit enforcement**
There's no restriction on how many accounts a Starter user can add. When billing is live, the Starter plan (1 account) vs Pro plan (10 accounts) tier gate needs to be enforced here. Wire this before billing ships.

**No follow-up message after adding an account**
After adding an MT5 account, there's no message about what happens next. Add: "The engine will begin scanning your account during the next London session (09:00 NGT)."

---

## Dashboard — Layout

### Issues

**Documentation link is dead**
The sidebar has a "?" Documentation link that goes `href="#"`. Either remove it or link to real docs.

**No notification system**
There's no way for the engine to push critical alerts to the user (e.g., "Engine halted — daily loss limit reached" or "New trade executed"). An alert badge on the topbar, or a subtle toast system, would be valuable for engaged users who want real-time awareness without watching the feed all day.

---

## Things to Remove

| Item | Location | Reason |
|---|---|---|
| Footer dead links (About, Blog, Careers) | `Landing.tsx` | Breaks trust for a financial product |
| "Uptime 99.7%" hardcoded string | `Overview.tsx` Engine Status card | Remove until it reflects real data |
| RiskTab "Save Defaults" button | `SettingsPage.tsx` | Non-functional; misleads users |

---

## New Concepts to Add (Prioritized)

### 1. Shareable Audit Link *(Starter tier unlocking feature)*
A "Share Session" button in the Trades or Feed page that generates a public read-only URL for a session or trade history. The signal provider clicks this link and sees the follower's Glass Box results without an account. This is the entire B2B2C acquisition motion and it is not in the product yet. Without it, providers cannot act as the expert interpreters that the Starter tier acquisition model depends on.

### 2. Onboarding Checklist for New Users *(first-login experience)*
After sign-up, show a dismissible checklist before the empty dashboard:
- Step 1 — Connect your MT5 account (→ Account Settings)
- Step 2 — Set your risk configuration
- Step 3 — The bot begins scanning at the next London session (09:00 NGT)

This replaces the current "empty everything" first impression.

### 3. Engine Halt Banner *(critical alert)*
When the bot halts due to daily loss limit, display a red banner across the top of the entire dashboard — not just a small status in a card. This is the alert that matters most to a prop firm candidate. It should be impossible to miss.

### 4. Profit Target Tracker in PropFirmPanel *(completing the Pro tier spec)*
Add a "Profit Target" field to the PropFirmPage config with a progress bar. Shows percentage toward the challenge profit target. This is in the product spec and is currently absent.

### 5. "Explain This" Tooltips in the Dashboard
The landing page has the `Term` component for ICT jargon glosses. The dashboard doesn't. The Live Logic Feed streams events like "MSS confirmed on EURUSD" and "Fair Value Gap detected" with no explanation. Port the tooltip system to the dashboard, at minimum in the Live Logic Feed and VerdictSidebar. This makes the product accessible to Starter-tier users who "don't know what's going on."

### 6. Session Summary Cards *(passive user retention)*
After each London or NY session closes, auto-generate a summary card on the Overview: "London Session — 3 scans, 1 verdict, 1 trade executed, +$47 · No halt conditions triggered." Push this as a pinned entry at the top of the Live Logic Feed. Passive users who don't watch the feed all day still get transparency without real-time attention.

### 7. Upgrade Nudge at Account Add Limit
When a Starter user tries to add a second MT5 account, intercept with a modal: "Pro plan supports up to 10 accounts — upgrade for $49/mo." This is the highest-intent moment to convert a Starter user to Pro.

---

## Summary

The design system is solid — the token architecture, `font-mono` consistency, and component library are well thought out. The VerdictSidebar is genuinely differentiated and the PropFirmPanel's color-coded drawdown bar is the right instinct. The auth pages' live NGT clock is one of the best brand moments in the product.

### Fix before any user sees this

| Priority | Issue | Fix |
|---|---|---|
| 1 | Pricing shows $49/$99, strategy approved $15/$49 | Update `Landing.tsx` pricing section |
| 2 | RiskTab save button is non-functional | Wire it up or mark "coming soon" |
| 3 | No onboarding flow for first-time users | Add checklist + empty state CTA |

### Build next

| Priority | Feature | Why |
|---|---|---|
| 1 | Shareable audit link | Unlocks the Telegram B2B2C acquisition motion |
| 2 | Billing/subscription tab in Settings | Without this nothing monetizes |
| 3 | Profit target tracker in PropFirmPanel | Completes the Pro tier spec you're charging $49/mo for |

---

*Glass Box — See everything. Trust what you see.*
