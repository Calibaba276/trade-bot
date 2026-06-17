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

**2. Share link encodes trade data in the URL** (`utils/share.ts`)

The share token is a base64-encoded payload of the trade data itself (no server round-trip — `decodeShare(token)` reconstructs from URL params). This means:

- Share links can be arbitrarily large (many trades = enormous URL)
- No server-side audit — anyone can craft a fake share link with modified trade data
- Signal providers cannot trust the data they're shown

**Fix required:** Share links need to store the payload in Supabase and serve it server-side. A `shared_sessions` table with `id`, `user_id`, `trade_ids[]`, `created_at` — the link is `/share/:uuid`, the page fetches from Supabase. This is the B2B2C trust mechanism and it only works if the data can't be fabricated by the sender.

---

**3. Footer dead links** (`Landing.tsx` — Footer component)

About, Blog, Careers, Contact are all still `href="#"`. For a financial product this is a real trust issue. Remove these columns until the pages exist.

---

**4. Landing page CTAs promise "30-day free trial, no credit card required"** (`Landing.tsx`)

This promise appears in the hero trust strip and in the pricing section footer. Billing isn't live. A promise that can't be honored at checkout kills trust harder than no promise at all.

**Fix required:** Change to "Request Early Access" or "Join Waitlist" until billing ships.

---

**5. "Start Free Trial" in navbar** (`Landing.tsx` — NavBar)

Same issue — links to `/sign-up` and implies a free trial that can't actually be activated.

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
| Shareable audit link (UI) | ✅ Exists | Share data is URL-encoded, not server-stored |
| Toast notifications | ✅ Fixed | — |
| Billing / tier gating | ⚠ Stub | **Yes** — tier switcher is accessible to real users |
| Share link security | ⚠ URL payload | **Yes** — data can be client-fabricated; links can be huge |
| Footer dead links | ❌ Still `href="#"` | Trust issue for financial product |
| Free trial CTA copy | ❌ Billing not live | Promise can't be honored at checkout |
| Dashboard `Term` tooltips | ❌ Not ported | Nice-to-have for Starter tier UX |
| Fabricated social proof | ❌ Placeholder | Must replace before marketing outreach |

---

## Recommended next actions (ordered)

1. **Persist tier to Supabase `user_metadata`** and hide the dev tier-switcher from production users. This is the minimum viable billing gate even before Stripe is wired.
2. **Move share links to server-side** (`shared_sessions` table in Supabase). The B2B2C motion only works if providers can trust the audit data.
3. **Remove or replace footer dead links** — strip the About/Blog/Careers/Contact columns entirely.
4. **Change "free trial" copy to "early access"** across the landing page until billing ships.
5. **Replace placeholder social proof** with real numbers before any marketing goes out.

---

*Glass Box — See everything. Trust what you see.*
