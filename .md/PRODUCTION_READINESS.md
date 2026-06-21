# Glass Box — Production Readiness Review

Generated: 2026-06-17
Branch: main

---

## What the current changes have addressed

All critical issues from the original design review are fixed:

- Pricing is correct — $15/mo Starter, $49/mo Pro
- Two acquisition tracks in the hero (signal follower vs. prop challenger)
- Onboarding empty state when no accounts connected
- "Uptime 99.7%" hardcoded string is gone — engine status is now market-hours-derived
- Overview recent signals rows are clickable ("Verdict →")
- RiskTab "Save Defaults" now saves to localStorage (functional)
- Subscription & Billing tab exists
- Forgot password link exists on Login
- Password hint ("At least 6 characters") shown inline in SignUp
- Post-signup message now says the confirmation link takes you to dashboard (not a 3s redirect to /sign-in)
- Auth pages are consistent — both show the live session + NGT clock
- Sidebar icons are Unicode glyphs, not emoji
- Nav item renamed "Replay Mode"
- Date range filter on Trades page
- "View" button renamed "Verdict →"
- "SL" column header is now "Stop Loss"
- PropFirmPage config persists to localStorage
- Profit target field exists in PropFirmPage config
- Daily reset timezone label says "midnight UTC (1:00 AM NGT)"
- Engine halt banner across the full dashboard
- Session Summary cards on Overview
- Shareable audit link feature (Share Audit button + `/share/:token` page)
- Toast notification system (ToastContainer, market open/close events)
- Upgrade intercept modal when Starter tries to add a second account

---

## What still needs work before real users

### Hard blockers

**1. Billing is a stub** (`SettingsPage.tsx` — BillingTab)

The "Upgrade" button is `disabled` with "Coming Soon". Tier is toggled via a developer preview switcher in the header. Nothing actually gates features by a real paid subscription. Until Stripe/Lemonsqueezy is wired:

- All users get the same dashboard
- The tier switcher button is visible to real users (they can give themselves Pro for free)
- `useTierStore` reads from Zustand with no Supabase/auth backing

**Fix required:** Hide the tier preview switcher from non-dev users, or persist tier to `user_metadata` in Supabase so it's at least tied to a real account state. The upgrade button should either open an email/waitlist form or be removed entirely.

---

**2. ~~Share link encodes trade data in the URL~~** ✅ Fixed

The `shared_sessions` table (migration `20260618000000_shared_sessions.sql`) stores immutable snapshot data server-side. Share links are `/share/:uuid` — the page fetches from Supabase. Snapshots cannot be modified once created (no UPDATE policy). Only the authenticated owner can create or delete them. This satisfies the B2B2C trust requirement.

---

**3. Footer dead links** (`Landing.tsx` — Footer component)

About, Blog, Careers, Contact are all still `href="#"`. For a financial product this is a real trust issue. Remove these columns until the pages exist.

---

**4. Landing page CTAs promise "30-day free trial, no credit card required"** (`Landing.tsx`)

**✅ Strategy approved (2026-06-21) — keep this copy.** The 30-day Pro free trial is the confirmed acquisition strategy. The CTA is correct. What's missing is the *backend* to honour it: trial tracking in `user_profiles`, expiry cron, Day 30 plan selection screen, and Paystack billing. These are Week 5 engineering tasks. Do NOT change the CTA to "Request Early Access" — the free trial is the plan.

**What still needs building (Week 5):**
- `user_profiles.trial_expires_at` field + expiry cron (pg_cron hourly)
- Trial countdown banner on dashboard
- Day 30 plan selection screen (mandatory, cannot be dismissed)
- Paystack subscription checkout for Starter ($15/mo) and Pro ($49/mo)

---

**5. "Start Free Trial" in navbar** (`Landing.tsx` — NavBar)

Same as above — keep this. The navbar CTA is correct for the approved trial strategy.

---

### Medium priority

**6. Auth pages use inline CSS var styles instead of Tailwind tokens**

`Login.tsx` and `SignUp.tsx` use `style={{ border: "0.5px solid var(--border-muted)" }}` inline rather than Tailwind design tokens. Not a launch blocker but means these pages sit outside the token system — a future brand change requires hunting inline styles rather than changing one variable.

---

**7. "Explain This" tooltips not ported to dashboard**

The `Term` glossary component from the landing page isn't used anywhere in the dashboard. The Live Feed streams events like "MSS confirmed on EURUSD" and "Fair Value Gap detected" with no in-context explanation. Starter-tier users who "don't know what's going on" have no recourse. Low effort to add — the component already exists.

---

**8. Documentation link is dead** (`DashboardLayout.tsx` — sidebar)

The "?" Documentation link is `href="#"`. Remove it until docs exist.

---

**9. Social proof is placeholder data** (`Landing.tsx` — SocialProof component)

Stats ("340+ Traders", "12,000+ Trades executed", "68% win rate") and testimonials (`@tunde_fx`, `@chiamaka_trades`, etc.) are fabricated. Fine for internal review but must be replaced with real data before any marketing outreach. Fabricated social proof for a financial product is a regulatory and trust liability.

---

## Summary table

| Item | Status | Blocker? |
|---|---|---|
| Pricing ($15/$49) | ✅ Fixed | — |
| Two hero acquisition tracks | ✅ Fixed | — |
| Onboarding empty state | ✅ Fixed | — |
| RiskTab functional save | ✅ Fixed | — |
| PropFirm config persistence | ✅ Fixed | — |
| Profit target tracker | ✅ Fixed | — |
| Engine halt banner | ✅ Fixed | — |
| Session summary cards | ✅ Fixed | — |
| Shareable audit link (UI) | ✅ Fixed | `shared_sessions` table in Supabase; server-stored, immutable snapshots |
| Toast notifications | ✅ Fixed | — |
| Billing / tier gating | ⚠ Stub | **Yes** — tier switcher is accessible to real users |
| Share link security | ✅ Fixed | Server-stored in `shared_sessions`; immutable; UUID-gated |
| Footer dead links | ❌ Still `href="#"` | Trust issue for financial product |
| Free trial CTA copy | ✅ Approved — keep it | Trial strategy confirmed (2026-06-21). Backend builds Week 5. |
| Dashboard `Term` tooltips | ❌ Not ported | Nice-to-have for Starter tier UX |
| Fabricated social proof | ❌ Placeholder | Must replace before marketing outreach |

---

## Recommended next actions (ordered)

1. **Persist tier to Supabase `user_metadata`** and hide the dev tier-switcher from production users. This is the minimum viable billing gate even before Stripe is wired.
2. **Remove or replace footer dead links** — strip the About/Blog/Careers/Contact columns entirely.
3. **Change "free trial" copy to "early access"** across the landing page until billing ships.
4. **Replace placeholder social proof** with real numbers before any marketing goes out.

---

## Tasks not yet accomplished

- [ ] **Wire billing / Stripe** — `BillingTab` in `SettingsPage.tsx` is still a stub. Tier is toggled in-memory by a developer preview switch. No real subscription gate exists.
- [ ] **Hide tier preview switcher from non-dev users** — or gate it behind `NODE_ENV === 'development'`.
- [ ] **Replace footer dead links** — `Landing.tsx` About/Blog/Careers/Contact are all `href="#"`.
- [ ] **Wire the 30-day free trial backend** — `user_profiles.trial_expires_at`, expiry cron, Day 30 plan selection screen, Paystack billing. The landing page CTA copy is correct and intentional — do not change it. (Week 5 task.)
- [ ] **Replace placeholder social proof** in `Landing.tsx` (fabricated stats and testimonials) with real data before any marketing outreach.
- [ ] **Port `Term` glossary tooltips to dashboard** — the ICT jargon tooltip component from the landing page is not used in the Live Feed or VerdictSidebar.
- [ ] **Wire "?" Documentation link** in `DashboardLayout.tsx` sidebar — currently `href="#"`.
- [ ] **Align auth page inline styles with design token system** — `Login.tsx` and `SignUp.tsx` use hardcoded hex values instead of Tailwind CSS variable tokens.

---

*Glass Box — See everything. Trust what you see.*
