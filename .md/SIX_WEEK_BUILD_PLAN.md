# Glass Box — 6-Week Build Plan: Complete Task Breakdown
### Updated 2026-06-21 — includes 30-day free trial decision

**Document purpose:** Every task across the 6-week GTM sprint, written in full detail, grouped by discipline. Every item here was discussed and decided across planning sessions. Nothing is speculative.

**How to read this:**
- Tasks are grouped by section (Backend, Frontend, Security, UX, Billing, etc.)
- Each task shows: which week, who owns it (You or Engineering), time estimate, full description, why it matters, and what "done" looks like
- Time estimates: XS = under 2h · S = half-day · M = full day · L = 2–3 days · XL = full week
- `[YOU]` = human task requiring no code · `[ENG]` = engineering task

---

## PRICING & TRIAL STRATEGY (DECIDED 2026-06-21)

### The Trial Decision

**30-day free trial on Pro — no credit card required.**

Every new user starts with full Pro access for 30 days. At Day 30, they see a mandatory choice screen:
1. **Stay on Pro — $49/mo** (keep everything)
2. **Continue with Starter — $15/mo** (keep auto-execution + audit links, lose Replay Mode / Indices / multi-account)
3. **Account paused** (read-only until they choose a plan)

**Why this reverses the "no free tier" decision:**
The original reasoning — "a free tier lets people consume audit links without converting" — was correct for a *permanent* free tier. A 30-day trial with a hard cutoff is a completely different mechanic. After Day 30, they pay or lock out.

The trust barrier for a trading product is uniquely high:
- Users are handing over MT5 broker credentials
- A bot is executing real trades on their live account with real money
- Glass Box is a new product with zero public social proof at launch
- The Nigerian market has extreme skepticism of new financial tools due to widespread scams

A try-before-you-buy mechanism is not optional for this product category. It is the primary conversion mechanism.

**Why Pro trial specifically (not Starter):**
Loss aversion is 2× stronger than desire for gain (Kahneman, verified in SaaS conversion data). A user who spends 30 days on Pro and then faces losing Replay Mode, US Indices, and multi-account capability is more motivated to pay than a Starter user who has never experienced those features. The Starter fallback path ensures no one churns entirely — even users who can't afford $49 can pay $15.

**Trial constraints:**
- 1 broker account during trial (same as Starter — prevents abuse of multi-account feature)
- Email verification required before trial starts
- Trial tracks at the Pro level but is capped at 1 account

---

## SECTION 1 — STRATEGY ENGINE & BACKEND LOGIC

---

### WEEK 1 · EURUSD Strategy Rewrite
**Owner:** ENG · **Estimate:** M–L · **File:** `backend/strategies/ict_model.py`

**What:**
Audit and rewrite the EURUSD ICT strategy to eliminate any lookahead bias or repainting. Every condition check must be strictly point-in-time — the strategy can only use data that would have been available at the exact moment a decision was being made.

**Why it matters:**
If the current backtest is using future candle data to confirm conditions, every backtest result is fabricated. You cannot trust a strategy that shows an 80% win rate if that win rate is built on data the bot couldn't have known at trade time. This is the foundation everything else is built on — if the EURUSD engine is not clean, nothing else matters.

**The 8-phase ICT model must be audited phase by phase:**
1. Phase 1 (Asian session high/low capture): Confirm high/low are captured from *closed* candles only
2. Phase 2 (Sweep detection): Confirm the sweep is confirmed from the close of the sweep candle, not mid-candle
3. Phase 3 (MSS swing detection): The swing low/high identification must use only candles `i-1` and earlier, never the current forming candle
4. Phase 4 (MSS break confirmation): Must wait for a closed candle below the swing low, not a mid-candle wick
5. Phase 5 (FVG detection): Three-candle pattern — all three candles must be closed
6. Phase 6 (Entry): Entry at FVG bottom must be a limit order placed *after* the FVG is confirmed, not at the moment of the confirming candle's open
7. Phase 7 (SL placement): SL above the sweep point — calculated from closed data only
8. Phase 8 (TP calculation): Based on entry and SL — purely arithmetic, no lookahead issue

**Acceptance criteria:**
- Backtest on 6-month EURUSD data shows no trades where the condition-confirmation candle and the entry candle are the same candle
- Every `self.get_historical_prices()` call uses an end index strictly before the current bar
- Code review confirms no reference to index `0` (current forming bar) in any condition check

---

### WEEK 2 · XAUUSD Strategy Runner
**Owner:** ENG · **Estimate:** M · **Files:** `backend/runners/ict_xauusd.py` (new), `backend/strategies/ict_model.py`

**What:**
Run a second instance of the ICT strategy engine for XAUUSD (Gold). The strategy logic is identical to EURUSD — same 8-phase model, same London (09:00–11:00 WAT) and NY (13:00–17:00 WAT) session windows. XAUUSD is available on both Starter and Pro tiers.

**Why it matters:**
Gold is the most-traded instrument by Nigerian retail traders. The Telegram signal channels targeted for the Starter acquisition strategy are predominantly Gold channels. Gating XAUUSD behind Pro would cut the Starter market in half before launch. This is non-negotiable for the Starter tier to have meaningful value.

**Technical notes:**
- Backtest symbol: `XAUUSD` (no suffix, Polygon format)
- Live symbol: `XAUUSDm` (broker suffix — confirm with IC Markets, the suffix may vary by broker)
- XAUUSD position sizing uses the Forex formula (`risk / sl_distance / 100_000`) but with a different pip value — verify the lot size calculation produces correct dollar risk before going live
- The runner is a copy of `ict_eurusd.py` with `SYMBOL = "XAUUSD"` / `"XAUUSDm"` substituted

**Acceptance criteria:**
- Backtest on XAUUSD 6-month data completes without errors
- Live runner connects to MT5, subscribes to XAUUSD tick feed, publishes verdicts with `symbol: "XAUUSD"` to Redis
- Verdicts appear in the Supabase `signals` table with correct symbol field

---

### WEEK 3 · NAS100, US30, SPX500 Runners (Pro-Only)
**Owner:** ENG · **Estimate:** L · **Files:** `backend/runners/ict_indices.py` (new)

**What:**
Three new strategy runners for US Indices. These are Pro-only instruments (and accessible to trial users since trial = Pro). Session window is NYSE open: 15:30–17:30 WAT.

**Why it matters:**
US Indices complete the Pro tier value proposition. The prop firm trader persona — the primary Pro target — often runs NAS100 or US30 challenges alongside forex. During the 30-day trial, showing users that US Indices work increases the likelihood they stay on Pro rather than downgrading to Starter at Day 30.

**Important pre-conditions to verify before building:**
- Confirm IC Markets (and other supported brokers) serve NAS100, US30, SPX500 on MT5 and under what symbol names (NAS100, USTEC, US100 — broker-specific)
- Confirm Polygon.io serves these for backtesting
- Run a short backtest to confirm the ICT strategy logic produces sensible results on index candles

**Session window:**
NYSE opens at 14:30 UTC = 15:30 WAT. Strategy window: 15:30–17:30 WAT.

**Acceptance criteria:**
- Backtest on NAS100 produces verdicts without errors
- Live runner publishes NAS100/US30/SPX500 verdicts during 15:30–17:30 WAT window only
- A Pro-tier worker (and trial worker) executes these signals; a Starter-tier worker skips them with `[TIER_GATE]` log entry

---

### WEEK 5 (STRETCH) · FVG Zone Structured Data
**Owner:** ENG · **Estimate:** M · **Files:** `backend/services/verdict.py`, `backend/strategies/ict_model.py`

**What:**
Update `build_verdict()` to include FVG zone data as a structured object that the frontend chart renderer can use to draw shaded rectangles.

**Target state:**
```python
verdict = {
  ...existing fields...,
  "fvg_zone": {
    "top": 1.08561,
    "bottom": 1.08490,
    "direction": "bearish",
    "confirmed_at": "2026-01-23T09:24:59Z"
  }
}
```

**Acceptance criteria:**
- Verdicts in Supabase `signals` table contain the `fvg_zone` JSONB object
- Chart overlay renders a shaded rectangle between the two price levels

---

## SECTION 2 — DATABASE & SCHEMA ARCHITECTURE

---

### WEEK 1 · `user_profiles` Table (with Trial Fields)
**Owner:** ENG · **Estimate:** S · **File:** Supabase migration SQL

**What:**
Create the `user_profiles` table. Includes trial tracking fields so every new signup automatically receives a 30-day Pro trial.

**Schema:**
```sql
CREATE TABLE user_profiles (
  id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
  plan_tier TEXT DEFAULT NULL
    CHECK (plan_tier IS NULL OR plan_tier IN (
      'starter', 'pro', 'enterprise', 'lifetime_starter', 'lifetime_pro'
    )),
  -- NULL plan_tier means "on trial" — trial_tier determines what they can access

  trial_tier TEXT NOT NULL DEFAULT 'pro'
    CHECK (trial_tier IN ('starter', 'pro')),
  trial_started_at TIMESTAMPTZ DEFAULT NOW(),
  trial_expires_at TIMESTAMPTZ DEFAULT NOW() + INTERVAL '30 days',
  trial_email_day1_sent BOOLEAN DEFAULT FALSE,
  trial_email_day7_sent BOOLEAN DEFAULT FALSE,
  trial_email_day21_sent BOOLEAN DEFAULT FALSE,
  trial_email_day28_sent BOOLEAN DEFAULT FALSE,
  trial_email_day30_sent BOOLEAN DEFAULT FALSE,

  plan_expires_at TIMESTAMPTZ,
  onboarding_complete BOOLEAN DEFAULT FALSE,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Auto-create user_profiles row + set trial for every new signup
CREATE OR REPLACE FUNCTION handle_new_user()
RETURNS TRIGGER LANGUAGE plpgsql SECURITY DEFINER AS $$
BEGIN
  INSERT INTO public.user_profiles (id, trial_started_at, trial_expires_at)
  VALUES (
    NEW.id,
    NOW(),
    NOW() + INTERVAL '30 days'
  );
  RETURN NEW;
END;
$$;

CREATE TRIGGER on_auth_user_created
  AFTER INSERT ON auth.users
  FOR EACH ROW EXECUTE FUNCTION handle_new_user();

-- Row Level Security
ALTER TABLE user_profiles ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Users can read own profile"
  ON user_profiles FOR SELECT USING (auth.uid() = id);
CREATE POLICY "Users can update own profile"
  ON user_profiles FOR UPDATE USING (auth.uid() = id);
```

**Helper function: what tier is the user effectively on right now?**
```sql
CREATE OR REPLACE FUNCTION effective_tier(profile user_profiles)
RETURNS TEXT AS $$
BEGIN
  -- Paid plan takes priority
  IF profile.plan_tier IS NOT NULL THEN
    RETURN profile.plan_tier;
  END IF;
  -- Active trial
  IF profile.trial_expires_at > NOW() THEN
    RETURN profile.trial_tier;  -- 'pro' by default
  END IF;
  -- Trial expired, no plan chosen
  RETURN 'trial_expired';
END;
$$ LANGUAGE plpgsql IMMUTABLE;
```

**Why the `trial_tier` is separate from `plan_tier`:**
`plan_tier` is NULL until the user pays. This makes it easy to query "users who have never paid" vs "users on a paid plan." `trial_tier` tracks what access level the trial provides (always 'pro' currently, but could be 'starter' for a downgraded trial in future).

**Acceptance criteria:**
- New user signup automatically creates a `user_profiles` row with `trial_expires_at = NOW() + 30 days`
- `effective_tier()` returns 'pro' for a new user, 'trial_expired' after 30 days, and the paid tier once they convert
- RLS confirmed: user can only read/update their own row

---

### WEEK 1 · Denormalize Effective Tier into `broker_accounts`
**Owner:** ENG · **Estimate:** S · **File:** Supabase migration SQL, `backend/services/worker.py`

**What:**
Add a `plan_tier` column to `broker_accounts`. A trigger keeps it synchronized with the user's effective tier (from `user_profiles`). Worker reads this column without a JOIN.

```sql
ALTER TABLE broker_accounts
ADD COLUMN plan_tier TEXT DEFAULT 'pro'
  CHECK (plan_tier IN (
    'starter', 'pro', 'enterprise',
    'lifetime_starter', 'lifetime_pro', 'trial_expired'
  ));

-- Sync trigger: when effective tier changes, update all accounts for that user
CREATE OR REPLACE FUNCTION sync_effective_tier()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
DECLARE
  eff_tier TEXT;
BEGIN
  -- Recalculate effective tier
  IF NEW.plan_tier IS NOT NULL THEN
    eff_tier := NEW.plan_tier;
  ELSIF NEW.trial_expires_at > NOW() THEN
    eff_tier := NEW.trial_tier;
  ELSE
    eff_tier := 'trial_expired';
  END IF;

  UPDATE broker_accounts
  SET plan_tier = eff_tier
  WHERE user_id = NEW.id;

  RETURN NEW;
END;
$$;

CREATE TRIGGER on_tier_change
  AFTER UPDATE OF plan_tier, trial_expires_at ON user_profiles
  FOR EACH ROW EXECUTE FUNCTION sync_effective_tier();
```

**Key behavior:**
- New user (trial active) → `broker_accounts.plan_tier = 'pro'`
- Trial expired, no payment → `broker_accounts.plan_tier = 'trial_expired'`
- User pays for Starter → `broker_accounts.plan_tier = 'starter'`
- User pays for Pro → `broker_accounts.plan_tier = 'pro'`

**Acceptance criteria:**
- New account's `broker_accounts.plan_tier` = 'pro' (trial)
- 30 days later (simulated), updates to 'trial_expired'
- Paystack payment for Starter → updates to 'starter'

---

### WEEK 1 · Three Missing DB Indexes
**Owner:** ENG · **Estimate:** XS · **File:** Supabase migration SQL

```sql
CREATE INDEX IF NOT EXISTS idx_broker_accounts_user_id
  ON broker_accounts(user_id);
CREATE INDEX IF NOT EXISTS idx_signals_account_created
  ON signals(account_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_signals_symbol_created
  ON signals(symbol, created_at DESC);
```

**Acceptance criteria:** `EXPLAIN ANALYZE` on common dashboard queries shows Index Scan, not Seq Scan.

---

### WEEK 2 · `broker_accounts.symbol` Multi-Value Support
**Owner:** ENG · **Estimate:** S · **Files:** `backend/services/worker.py`, `backend/services/orchestrator.py`

**What:**
Change `broker_accounts.symbol` to accept a comma-separated list (`"EURUSD,XAUUSD,GBPUSD"`). Worker reads the list and skips signals for symbols not in it.

**Trial user defaults:** New accounts created during trial get all Pro-eligible symbols:
`"EURUSD,XAUUSD,GBPUSD,USDJPY,NAS100,US30,SPX500"`

When a user converts to Starter at Day 30, their symbol list is updated to Starter-eligible only:
`"EURUSD,XAUUSD,GBPUSD,USDJPY"`

**Acceptance criteria:**
- Worker with `symbol = "EURUSD,XAUUSD"` executes verdicts for both
- Trial user receives NAS100 signals correctly
- Starter conversion at Day 30 removes NAS100/US30/SPX500 from symbol list

---

### WEEK 4 · `audit_links` Table
**Owner:** ENG · **Estimate:** S · **File:** Supabase migration SQL

```sql
CREATE TABLE audit_links (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  signal_id UUID NOT NULL REFERENCES signals(id) ON DELETE CASCADE,
  created_by UUID NOT NULL REFERENCES auth.users(id),
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Public read (no auth required to view an audit link)
ALTER TABLE audit_links ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Public read on audit_links"
  ON audit_links FOR SELECT USING (true);
CREATE POLICY "Authenticated users create audit links"
  ON audit_links FOR INSERT WITH CHECK (auth.uid() = created_by);
```

**Trial users can generate audit links.** Audit links created during the trial remain live permanently regardless of what plan the user chooses at Day 30 — no cascade delete on user plan changes.

---

### WEEK 5 · `activate_subscription` Supabase RPC
**Owner:** ENG · **Estimate:** M · **File:** Supabase migration SQL

```sql
CREATE OR REPLACE FUNCTION activate_subscription(
  p_user_id UUID,
  p_plan TEXT
)
RETURNS VOID LANGUAGE plpgsql SECURITY DEFINER AS $$
BEGIN
  IF p_plan NOT IN (
    'starter', 'pro', 'enterprise', 'lifetime_starter', 'lifetime_pro'
  ) THEN
    RAISE EXCEPTION 'Invalid plan: %', p_plan;
  END IF;

  UPDATE user_profiles
  SET
    plan_tier = p_plan,
    plan_expires_at = CASE
      WHEN p_plan LIKE 'lifetime_%' THEN NULL
      ELSE NOW() + INTERVAL '1 month'
    END,
    updated_at = NOW()
  WHERE id = p_user_id;

  -- broker_accounts.plan_tier updated by trigger automatically

  INSERT INTO subscription_events (user_id, plan, event_type, created_at)
  VALUES (p_user_id, p_plan, 'activated', NOW());
END;
$$;
```

**Also needed: `handle_trial_expiry` function called by cron job:**
```sql
CREATE OR REPLACE FUNCTION handle_trial_expiry()
RETURNS VOID LANGUAGE plpgsql SECURITY DEFINER AS $$
BEGIN
  -- Mark all expired trials with no paid plan
  UPDATE user_profiles
  SET updated_at = NOW()
  WHERE plan_tier IS NULL
    AND trial_expires_at < NOW();
  -- The sync_effective_tier trigger fires and sets broker_accounts.plan_tier = 'trial_expired'
END;
$$;

-- Run every hour via pg_cron
SELECT cron.schedule('check-trial-expiry', '0 * * * *', 'SELECT handle_trial_expiry()');
```

---

## SECTION 3 — SECURITY

---

### WEEK 1 · Row Level Security Audit
**Owner:** ENG · **Estimate:** S

Confirm RLS is enabled with correct policies on every table before any user signs up.

**Tables to audit:**
| Table | Required policies |
|---|---|
| `user_profiles` | User reads/updates own row only |
| `broker_accounts` | User reads/updates/inserts own accounts only |
| `signals` | User reads signals for their own accounts only |
| `audit_links` | Public SELECT, authenticated INSERT (created_by = auth.uid()) |

**Test:** Two test accounts. User A's signals must return 0 rows when queried as User B.

**Acceptance:** Cross-user query shows 0 leaked rows. All tables confirmed.

---

### WEEK 1 · MT5 Credentials Audit (No Plaintext in Logs)
**Owner:** ENG · **Estimate:** XS · **Files:** `backend/services/worker.py`, `backend/brokers/mt5_broker.py`, `backend/services/orchestrator.py`

**What:** Grep all log statements for MT5 ACCOUNT, PASSWORD, SERVER values.

```bash
grep -rn "logger\." backend/ | grep -i "account\|password\|server"
grep -rn 'f".*{.*account\|password\|server' backend/
```

**Acceptance:** Zero log statements write raw credentials.

---

### WEEK 2 · Trial Abuse Prevention
**Owner:** ENG · **Estimate:** S

**Abuse vector:** Users create multiple email accounts to keep getting 30-day free trials indefinitely.

**Mitigations (layered):**

1. **Email verification required** before trial activates. The trigger that sets `trial_started_at` should only fire after email is confirmed, not at signup. Set `trial_started_at = NULL` on row creation; update to `NOW()` when Supabase `auth.users.email_confirmed_at` is set.

2. **1 broker account maximum** during trial. Before allowing a second account to be added, check `plan_tier` in the session. Trial users hit the same upgrade nudge as Starter users.

3. **Beta cap (50 users)** is still in place. At 50 total accounts, new signups are rejected regardless of email.

4. **IP-level heuristic (future, post-launch):** If the same IP registers 3+ accounts in 24 hours, flag for review. Do not implement in beta — over-engineering for 50 users.

**Acceptance:** Trial users with multiple email addresses can only create 1 broker account per email. The beta cap enforces a ceiling.

---

### WEEK 5 · Paystack Webhook Signature Validation
**Owner:** ENG · **Estimate:** M · **File:** `backend/api/webhooks.py` (new)

**What:**
Every Paystack webhook must be validated with HMAC-SHA512 before processing.

**Implementation:**
```python
import hmac
import hashlib
import json
from fastapi import Request, HTTPException
from backend.config.secrets import get_azure_secret

async def validate_paystack_webhook(request: Request) -> dict:
    body = await request.body()
    signature = request.headers.get("x-paystack-signature", "")
    secret = get_azure_secret("PAYSTACK-SECRET-KEY")

    expected = hmac.new(
        secret.encode("utf-8"),
        body,
        hashlib.sha512
    ).hexdigest()

    # compare_digest prevents timing attacks — NEVER use ==
    if not hmac.compare_digest(signature, expected):
        logger.warning("[WEBHOOK_INVALID] Paystack signature mismatch")
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    return json.loads(body)

@app.post("/api/webhooks/paystack")
async def paystack_webhook(request: Request):
    event = await validate_paystack_webhook(request)

    if event.get("event") == "charge.success":
        user_email = event["data"]["customer"]["email"]
        plan_code = event["data"]["plan"]["plan_code"]
        plan = resolve_plan_from_code(plan_code)

        user = supabase.auth.admin.get_user_by_email(user_email)
        supabase.rpc("activate_subscription", {
            "p_user_id": user.id,
            "p_plan": plan
        }).execute()

        logger.info(f"[BILLING] Subscription activated: {user_email} → {plan}")

    return {"status": "ok"}
```

**Paystack secret in Azure Key Vault:**
```bash
az keyvault secret set --vault-name calibabasecret --name PAYSTACK-SECRET-KEY --value <secret>
```

**Acceptance:** Tampered body → HTTP 401. Valid signature → plan activated. All outcomes logged.

---

### WEEK 3 · Tier Enforcement in Worker (Fail-Closed)
**Owner:** ENG · **Estimate:** M · **File:** `backend/services/worker.py`

**What:**
Worker reads `plan_tier` from `broker_accounts`. Enforces: Pro-only symbols (NAS100/US30/SPX500) are skipped for Starter accounts. Trial-expired accounts skip ALL signals.

```python
PRO_ONLY_SYMBOLS = frozenset({"NAS100", "US30", "SPX500"})

class Worker:
    def __init__(self, account_id):
        account = self._fetch_account(account_id)
        if account is None:
            logger.error(f"[TIER_GATE_ERROR] Cannot load account {account_id}. Halting.")
            raise RuntimeError("Account not found")

        self.plan_tier = account.get("plan_tier")
        if self.plan_tier is None:
            logger.error(f"[TIER_GATE_ERROR] plan_tier missing on {account_id}. Halting.")
            raise RuntimeError("plan_tier not set")

    def handle_signal(self, signal: dict):
        symbol = signal.get("symbol", "")

        # Trial expired — stop all execution
        if self.plan_tier == "trial_expired":
            logger.info(f"[TIER_GATE] Trial expired for account {self.account_id}. Skipping all signals.")
            return

        # Pro-only symbols for Starter accounts
        if symbol in PRO_ONLY_SYMBOLS and self.plan_tier == "starter":
            logger.info(f"[TIER_GATE] Skipping {symbol} — Starter account")
            return

        self._execute_signal(signal)
```

**Trial users (plan_tier = 'pro'):** Execute all signals including NAS100/US30/SPX500. Trial users get the full Pro experience.

**Acceptance:**
- Trial user → all signals execute (including NAS100)
- Trial expired → all signals skipped with [TIER_GATE] log
- Starter → NAS100/US30/SPX500 skipped
- Missing plan_tier → worker halts with [TIER_GATE_ERROR]

---

### WEEK 2 · Beta Registration Cap (Max 50 Users)
**Owner:** ENG · **Estimate:** XS · **File:** Supabase SQL

```sql
CREATE OR REPLACE FUNCTION check_beta_cap()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
DECLARE user_count INT;
BEGIN
  SELECT COUNT(*) INTO user_count FROM public.user_profiles;
  IF user_count >= 50 THEN
    RAISE EXCEPTION 'Beta is full. Join the waitlist at glassbox.io/waitlist';
  END IF;
  RETURN NEW;
END;
$$;

CREATE TRIGGER enforce_beta_cap
  BEFORE INSERT ON public.user_profiles
  FOR EACH ROW EXECUTE FUNCTION check_beta_cap();
```

Cap value (50) should be in a configurable `config` table — raise it without a code deploy.

---

## SECTION 4 — FRONTEND: LANDING PAGE

---

### WEEK 1 · Fix Pricing to $15/$49
**Owner:** ENG · **Estimate:** XS · **Files:** `Landing.tsx`, `PricingSection.tsx`

**What:** The current landing page shows $49/$99 (old pricing). Update to Starter = $15/mo, Pro = $49/mo. Also add the trial badge to each card.

**Pricing card additions with trial:**
```
┌──────────────────────────────────────┐
│ 🟢 30-DAY FREE TRIAL INCLUDED        │
│                                      │
│ STARTER              PRO ← POPULAR   │
│ $15/mo               $49/mo          │
│ after trial          after trial     │
└──────────────────────────────────────┘
```

---

### WEEK 1 · Landing Page Primary CTA — Free Trial
**Owner:** ENG · **Estimate:** M · **Files:** `HeroSection.tsx`, `NavBar.tsx`, `PricingSection.tsx`

**What:**
The primary CTA is now "Start 30-Day Free Trial — No Credit Card Required."

**Hero section buttons:**
```
[Start 30-Day Free Trial — Free →]    [See How It Works]
 primary (brand-blue, large)           secondary (ghost)
 /sign-up                              scrolls to HowItWorks
```

Note: The "no credit card" message is not just a subtitle — it must appear in the button row itself (as a small line beneath the primary button), since this is the primary trust signal.

```jsx
<div className="flex flex-col items-start gap-2">
  <Button size="lg" className="bg-brand-blue text-white" asChild>
    <Link href="/sign-up">Start 30-Day Free Trial →</Link>
  </Button>
  <span className="text-xs text-text-muted">
    No credit card required · Full Pro access · Cancel anytime
  </span>
</div>
```

**Why this outperforms "Request Early Access":**
"Request Early Access" communicates scarcity and exclusivity — useful when you have demand that exceeds supply. Glass Box in beta has the opposite problem: getting anyone to try it at all. "Start 30-Day Free Trial" is a concrete, low-risk offer with a clear value proposition. No persuasion needed.

**NavBar:** Change "Start Free Trial" to "Start Free Trial" (same) — the NavBar CTA should link to `/sign-up` and can keep the shorter label.

**Pricing section each card:**
- Starter card: "Start Free Trial → Try Pro free, then $15/mo"
- Pro card: "Start Free Trial → Try Pro free, then $49/mo"
- Enterprise: "Contact Us"

---

### WEEK 1 · Landing Page Quick Fixes (4 items)
**Owner:** ENG · **Estimate:** S total

**Fix 1 — Remove dead footer links:**
Delete About, Blog, Careers links until those pages exist.

**Fix 2 — Two-track audience paths in hero:**
Add subtitle copy beneath the primary trial CTA that addresses both personas:
- "For signal followers: auto-execute ICT setups on your MT5 account."
- "For prop firm traders: enforce your daily drawdown limit automatically."
These can be two small `<p>` tags or two feature chips below the CTA buttons.

**Fix 3 — Fix "Watch Live Demo" button:**
Either link to a real screen-recording video or rename to "See How It Works."

**Fix 4 — Add ICT term tooltips:**
Every bolded technical term (FVG, MSS, ICT, OB, BOS) on the landing page must have a plain-English `<Tooltip>` from shadcn/ui. Use the glossary from DESIGN.md Section 7.

---

### WEEK 6 · Social Proof Section
**Owner:** ENG + You · **Estimate:** M · **Files:** `Landing.tsx`, `TestimonialsSection.tsx` (new)

3 testimonial cards between PropFirmSection and PricingSection. Beta placeholder quotes until real user testimonials are collected (with permission) in Week 6.

---

## SECTION 5 — FRONTEND: AUTHENTICATION

---

### WEEK 2 · Auth Page Design Token Fix
**Owner:** ENG · **Estimate:** XS

Replace hardcoded hex colors (`#141921`, `#0f1419`) on auth pages with design tokens (`bg-bg-surface`, `bg-bg-base`).

---

### WEEK 2 · Forgot Password Link
**Owner:** ENG · **Estimate:** XS

Add "Forgot your password?" link to the Login page triggering Supabase's password reset flow.

---

### WEEK 2 · Password Length Hint on SignUp
**Owner:** ENG · **Estimate:** XS

Add `Minimum 8 characters` hint below the password field on the SignUp page.

---

### WEEK 2 · Fix Post-Signup Redirect
**Owner:** ENG · **Estimate:** XS

After email confirmation, redirect to `/dashboard` (not `/sign-in`). Set in `<Auth redirectTo="/dashboard" />` and in Supabase Dashboard → Authentication → Redirect URLs.

**Trial context:** The onboarding checklist must appear for new trial users on their first `/dashboard` visit. This redirect fix is a dependency for that.

---

## SECTION 6 — FRONTEND: DASHBOARD & CORE UI

---

### WEEK 1 · Wire RiskTab "Save Defaults" Button
**Owner:** ENG · **Estimate:** S · **File:** `RiskTab.tsx` or `Settings.tsx`

Wire to save `risk_amount`, `rr_ratio`, `breakeven_buffer`, `max_daily_drawdown_pct` to the broker_accounts row. Show a success toast on save. Values persist on page reload.

---

### WEEK 3 · Remove Hardcoded "Uptime 99.7%"
**Owner:** ENG · **Estimate:** XS

Delete the hardcoded string from Overview. The Engine Status card already shows real state.

---

### WEEK 3 · Verdict Sidebar Trigger on Overview Signals Rows
**Owner:** ENG · **Estimate:** S

Add `onClick` handler to Overview signal rows that opens the VerdictSidebar with the selected signal's data.

---

### WEEK 3 · Rename "Chart Debugger" → "Replay Mode"
**Owner:** ENG · **Estimate:** XS

Update sidebar navigation label and icon (`Rewind` or `Play` from Lucide).

---

### WEEK 3 · Standardize Sidebar Icons (Lucide Only)
**Owner:** ENG · **Estimate:** XS

Replace all emoji in sidebar nav with Lucide icons. Use: `LayoutDashboard`, `Activity`, `Rewind`, `List`, `Shield`, `Settings`, `HelpCircle`, `LogOut`.

---

### WEEK 3 · Engine Halt Banner
**Owner:** ENG · **Estimate:** M · **Files:** `DashboardLayout.tsx`, account status context

Full-width banner on all dashboard pages when engine is halted. Background: `bg-bear-dim`, left border: `border-l-4 border-bear`. Shows reason, time until reset, and is auto-dismissed when status returns to 'active'.

---

### WEEK 3 · Halt Notification Email (15-Minute Delay)
**Owner:** ENG · **Estimate:** M · **File:** Supabase Edge Function

When `broker_accounts.status = 'halted'` and remains halted for 15+ minutes, send an email. Log: `[HALT_NOTIFY]`.

---

### WEEK 3 · PropFirmPanel Config Persistence
**Owner:** ENG · **Estimate:** S

Save PropFirm page config (daily limit, consecutive losses, profit target, challenge end date) to a `prop_firm_config JSONB` column on `broker_accounts`. Load on mount. Persist on save.

---

### WEEK 4 · Supabase Realtime Verdict Feed
**Owner:** ENG · **Estimate:** M · **Files:** `RealtimeProvider.tsx`, `LiveLogicFeed.tsx`

Switch from polling to Supabase WebSocket subscriptions. New signals appear in the Live Feed within 1–2 seconds of backend publish. Reference:
```js
supabase.channel('signals')
  .on('postgres_changes', { event: 'INSERT', schema: 'public', table: 'signals' },
      (payload) => dispatch({ type: 'NEW_SIGNAL', signal: payload.new }))
  .subscribe();
```

---

### WEEK 4 · PropFirmPanel Profit Target Tracker (Pro)
**Owner:** ENG · **Estimate:** S

Progress bar showing earned P&L vs profit target. Pro-only feature (accessible to trial users). Shows dollar amount + percentage + days remaining to challenge end date.

---

### WEEK 4 · Date Range Filter on Trades Page
**Owner:** ENG · **Estimate:** S

shadcn/ui DatePicker for date range. On change, update Supabase query with `created_at >= start AND created_at <= end`. Export CSV respects filter.

---

### WEEK 4 · "Explain This" ICT Tooltips in Dashboard
**Owner:** ENG · **Estimate:** S · **Files:** `VerdictSidebar.tsx`, `LiveLogicFeed.tsx`

Port `<Term>` component from landing page to dashboard. Apply to FVG, MSS, BOS, CHoCH, OB, PDH/PDL, Sweep Point, R:R, Breakeven throughout VerdictSidebar and LiveLogicFeed. Keyboard-accessible.

---

### WEEK 5 · Trial Countdown Banner
**Owner:** ENG · **Estimate:** S · **File:** `DashboardLayout.tsx`

A soft, informative banner that appears on all dashboard pages while the user is in trial.

**Design:**
```
┌──────────────────────────────────────────────────────────────────────────┐
│  ⏱  You're on a 30-day Pro trial — 22 days remaining.                   │
│      After Day 30, choose Pro ($49/mo) or Starter ($15/mo). No pressure. │
│                                                          [View Plans →]  │
└──────────────────────────────────────────────────────────────────────────┘
```

- Background: `bg-bg-elevated border border-border-muted` (subtle — not alarming)
- Not dismissible (informational, always visible during trial)
- Changes tone as trial expires:
  - Days 1–20: neutral informational (as above)
  - Days 21–27: `bg-amber-dim border-amber` — "9 days left"
  - Days 28–29: `bg-bear-dim border-bear` — "2 days left — choose your plan"
  - Day 30+: replaced by the Day 30 plan selection screen (see below)

**Data source:** `user_profiles.trial_expires_at`. Display is computed: `Math.ceil((trial_expires_at - now) / 86400000)` days remaining.

**Acceptance:** Banner visible on all pages during trial. Color changes correctly at each threshold. Disappears immediately when user converts to a paid plan (realtime subscription on `user_profiles.plan_tier`).

---

### WEEK 5 · Day 30 Plan Selection Screen
**Owner:** ENG · **Estimate:** M · **File:** `TrialExpiredModal.tsx` (new), `DashboardLayout.tsx`

**What:**
When `trial_expires_at < NOW()` and `plan_tier IS NULL`, show a full-page modal that cannot be dismissed without choosing a plan.

**Design:**
```
┌────────────────────────────────────────────────────────────────────────┐
│                                                                        │
│  Your 30-day Pro trial has ended.                                      │
│  You've executed [N] trades and generated [N] audit links.             │
│  Choose how you'd like to continue:                                    │
│                                                                        │
│  ┌───────────────────────┐  ┌────────────────────────────────────┐    │
│  │  STARTER              │  │  PRO              ← Recommended    │    │
│  │  $15/mo               │  │  $49/mo                            │    │
│  │                       │  │                                    │    │
│  │  ✓ 1 account          │  │  ✓ Up to 10 accounts               │    │
│  │  ✓ Auto-execution     │  │  ✓ US Indices (NAS100, US30, SPX)  │    │
│  │  ✓ Audit links        │  │  ✓ Replay Mode                     │    │
│  │  ✗ Replay Mode        │  │  ✓ Full Prop Firm Panel            │    │
│  │  ✗ US Indices         │  │  ✓ Multi-account                   │    │
│  │  ✗ Multi-account      │  │                                    │    │
│  │                       │  │                                    │    │
│  │  [Choose Starter]     │  │  [Stay on Pro]                     │    │
│  └───────────────────────┘  └────────────────────────────────────┘    │
│                                                                        │
│  [Pause my account — I'll decide later]                                │
│   (Your trade history and audit links are saved permanently.)          │
│                                                                        │
└────────────────────────────────────────────────────────────────────────┘
```

**Behavioral notes:**
- Cannot be dismissed with ESC or clicking outside — user must choose a path
- "Choose Starter" → triggers Paystack checkout for Starter plan
- "Stay on Pro" → triggers Paystack checkout for Pro plan
- "Pause my account" → sets a `paused: true` flag on `user_profiles`. Dashboard becomes read-only. Banner at top: "Your account is paused. [Choose a plan to resume →]"
- If user already started a Paystack checkout and it failed, show a "Try again" state

**Personalisation:** Show real numbers from their trial — "You've executed 14 trades and generated 3 audit links" — this is loss aversion made concrete. They're not losing abstract features; they're losing the ability to keep doing what they've been doing.

**Acceptance:** Trial-expired user with no paid plan cannot use any execution feature. Read-only access to their history is preserved. They can upgrade at any time by clicking "Choose a plan" in the top banner.

---

### WEEK 5 · Billing Tab in Settings
**Owner:** ENG · **Estimate:** M · **Files:** `Settings.tsx`, `SubscriptionTab.tsx` (new)

**Trial state in billing tab:**
```
You're on a 30-day Pro trial.
Trial ends: July 21, 2026 (22 days remaining)

[Upgrade to Pro now — $49/mo]   [See what's included in Starter]
```

**Paid Starter state:**
```
Current Plan: STARTER — $15/mo
Next billing: July 21, 2026
[Manage Billing ↗]    [Upgrade to Pro — $49/mo]
```

**Paid Pro state:**
```
Current Plan: PRO — $49/mo
Next billing: July 21, 2026
[Manage Billing ↗]
```

---

### WEEK 5 · Upgrade Nudge Modal
**Owner:** ENG · **Estimate:** S · **Files:** `Settings.tsx`, `UpgradeNudgeModal.tsx` (new)

When a Starter user (post-trial) tries to add a second broker account, show the upgrade modal. Trial users see a different message: "Multiple accounts unlock after your trial ends and you choose a plan."

---

## SECTION 7 — FRONTEND: CHARTS & TRADING VISUALIZATION

---

### WEEK 4 · Shareable Audit Link Page (`/audit/[uuid]`)
**Owner:** ENG · **Estimate:** L · **Files:** `/audit/[uuid].tsx` (new), `backend/api/audit.py` (new)

**Trial users can generate audit links** — this is a Starter + Pro feature and trial counts as Pro. Links remain live permanently after trial ends.

**Page design:**
```
GLASS BOX AUDIT — TRADE #4E21F3
SELL — EURUSD — 23 Jan 2026 — 10:25:00 WAT

Entry: 1.08490 | SL: 1.08762 | TP: 1.07980 | R:R: 3.12

── ICT CONDITIONS VERIFIED ──────
✓ Swept High: 1.08742
✓ MSS Confirmed
✓ Bearish FVG: 1.08490 → 1.08561
✓ Entry at FVG Bottom

── EXECUTION ─────────────────────
Status: FILLED  · Latency: 18ms

─────────────────────────────────────────────────────────
This audit was generated by Glass Box — the MT5 execution
engine that shows you everything it does and why.

Want auto-execution on YOUR account?
→ [Start 30-Day Free Trial — No Credit Card Required]
─────────────────────────────────────────────────────────
```

**Trial CTA on audit link page:** The acquisition CTA at the bottom now reflects the trial offer. A Telegram follower who sees this page should see "30-day free trial, no credit card" — removing every possible barrier to clicking through.

**Empty state (no trades yet):**
```
Glass Box is scanning for setups...
Next London session: 09:00 WAT (opens in 6h 14m)

Want your own execution account?
[Start 30-Day Free Trial — Free →]
```

---

### WEEK 4–5 · Realtime Chart Overlays in Live Mode
**Owner:** ENG · **Estimate:** M

Realtime subscription triggers chart overlay updates (FVG zones, MSS levels) as soon as a verdict is published. New overlays appear within 2 seconds.

---

### WEEK 5 · Replay Mode Slider (Pro + Trial)
**Owner:** ENG · **Estimate:** M · **Files:** `ReplaySlider.tsx`, `ChartDebuggerPage.tsx`

Timeline slider for scrubbing through past sessions. Available to Pro accounts and trial users. Starter accounts (post-trial) see: "Replay Mode is available on Pro ($49/mo)."

---

## SECTION 8 — UX & PRODUCT DESIGN

---

### WEEK 2 · First-Login Onboarding Checklist
**Owner:** ENG · **Estimate:** L · **Files:** `OnboardingChecklist.tsx` (new), `OverviewPage.tsx`

**Trial context added to checklist:**
The checklist should show the trial status prominently:

```
┌───────────────────────────────────────────────────────────┐
│  🟢 30-Day Pro Trial Active — 30 days remaining           │
│  Complete your setup to start receiving trade signals.    │
├───────────────────────────────────────────────────────────┤
│  ✓  1. Connect your MT5 account         [Connected ✓]    │
│  ○  2. Set your risk configuration      [Configure →]    │
│  ○  3. Choose your markets              [Select →]       │
│  ○  4. Next London session              09:00 WAT (6h)   │
└───────────────────────────────────────────────────────────┘
```

**Step details:**

**Step 1 — Connect MT5 account:** Links to Settings > Broker Accounts. During trial, user can add 1 account.

**Step 2 — Set risk configuration:** Links to Settings > Risk. Recommended trial config: $10–$25/trade risk amount. Show this as a hint: "For your trial, we recommend starting with a small risk amount ($10–$25) while you get comfortable."

**Step 3 — Choose markets:** Trial users see all Pro markets pre-selected (EURUSD, XAUUSD, GBPUSD, USDJPY, NAS100, US30, SPX500). They can deselect any they don't want.

**Step 4 — Session countdown:** Live countdown to next London session (09:00 WAT) or NY session (13:00 WAT).

**Completion:** All 4 steps checked → show success state: "You're all set. Glass Box is scanning. Your first trade is on the way." → persist `onboarding_complete = true`.

---

### WEEK 3–4 · Cold-Start Experience (Post-Checklist, Pre-First-Trade)
**Owner:** ENG · **Estimate:** M

Replace empty chart state with:
1. "Glass Box is scanning" pulsing status card
2. Session countdown timer
3. Last 5 scan log events (shows the engine is actively running even with no verdict)
4. "While you wait" link to Replay Mode to explore past sessions

This is critical for trial retention. A trial user who sees nothing for 14 hours will not convert.

---

### WEEK 3 · Pro-Locked Market Tab Overlay
**Owner:** ENG · **Estimate:** S

NAS100/US30/SPX500 tabs are accessible to trial users (trial = Pro). Starter users (post-trial) see lock icons and "Unlock with Pro" upgrade tooltip.

---

## SECTION 9 — BILLING & MONETISATION

---

### WEEK 1 · Paystack Account Setup (YOUR TASK)
**Owner:** YOU · **Estimate:** XS (30 min) · **When:** Days 1–3 of Week 1

Create a Paystack business account and submit for identity verification. Verification takes 1–5 business days — start in Week 1 to clear by Week 3. Go to paystack.com → Settings → Business Profile → submit business details + government ID + bank account.

---

### WEEK 5 · Trial Email Drip Campaign
**Owner:** ENG · **Estimate:** M · **File:** Supabase Edge Function (email-drip.ts) or cron-based service

**What:**
5 automated emails triggered by trial timeline. Use Resend or SendGrid via Supabase Edge Functions.

**Email schedule and content:**

**Day 1 — Welcome (sent on signup):**
- Subject: "Your 30-day Glass Box Pro trial has started"
- Body: Brief welcome, your trial includes [full feature list], recommended first step (connect your MT5 account), link to dashboard
- Include: recommended risk amount for trial ($10–$25)

**Day 7 — Check-In:**
- Subject: "7 days in — what has Glass Box done on your account?"
- Body: Pull real data — "You've received [N] signals, [N] trades executed." If N=0: "No signals yet? Here's why" (session timing explanation) + link to Replay Mode to see historical trades
- If N>0: "Here's your first week audit link" — generate one automatically

**Day 21 — Urgency Begins:**
- Subject: "9 days left on your Pro trial — here's what you'll keep"
- Body: Feature comparison (Pro vs Starter). "Everything you've been using: Replay Mode, US Indices, multi-account — stays if you upgrade to Pro ($49/mo) or goes away if you choose Starter."
- CTA: "Stay on Pro — $49/mo"
- Secondary CTA: "Continue with Starter — $15/mo"

**Day 28 — Hard Deadline:**
- Subject: "2 days left — choose your plan before your trial ends"
- Body: Direct and clear. Your trial ends on [date]. "Your [N] trades, your [N] audit links, your trade history — all preserved regardless of which plan you choose."
- CTA: "Choose your plan now →"

**Day 30 — Trial Ended:**
- Subject: "Your Glass Box trial has ended — your account is paused"
- Body: "Your trial is over. Your trade history and audit links are saved. Choose a plan to continue receiving signals."
- CTA: "Choose your plan →" links to Day 30 screen in dashboard

**Implementation:**
The `trial_email_dayN_sent` boolean columns in `user_profiles` prevent duplicate sends. The cron job checks these flags before sending.

**Acceptance:** Each email sends exactly once per user at the correct trial day. No duplicate sends. Real trade count data populated from Supabase query.

---

### WEEK 5 · Paystack Subscription Integration (Full)
**Owner:** ENG · **Estimate:** XL

**Architecture:**
1. User clicks "Stay on Pro" or "Choose Starter" on Day 30 screen
2. Frontend calls Paystack JS SDK to initiate checkout
3. Paystack processes payment → sends webhook to backend
4. Backend validates HMAC-SHA512 signature → calls `activate_subscription` RPC
5. Frontend subscribes to `user_profiles` realtime → plan_tier updates → UI re-renders

**Create Paystack plans:**
- "Glass Box Starter Monthly" → $15/mo
- "Glass Box Pro Monthly" → $49/mo
Store plan codes in Azure Key Vault: `PAYSTACK-STARTER-PLAN-CODE`, `PAYSTACK-PRO-PLAN-CODE`.

**Frontend checkout:**
```js
const initializePayment = (planCode: string) => {
  const handler = PaystackPop.setup({
    key: process.env.NEXT_PUBLIC_PAYSTACK_PUBLIC_KEY,
    email: user.email,
    plan: planCode,
    callback: (response) => {
      setPaymentState('processing');
      // Webhook handles plan activation — show "Payment received" to user
    },
    onClose: () => setPaymentState('idle')
  });
  handler.openIframe();
};
```

**Test the full loop in Paystack test mode:**
Test card: `4084 0840 8408 4081`, CVV `408`, any future expiry.

**Acceptance:** End-to-end: checkout → webhook → RPC → plan_tier updates → trial banner disappears → dashboard shows correct post-trial state.

---

### PRE-LAUNCH · Lifetime Deal Manual Provisioning (YOUR TASK)
**Owner:** YOU · **Estimate:** XS (5 min per user)

Before Paystack billing goes live, manually provision lifetime accounts via Supabase SQL Editor:
```sql
BEGIN;
UPDATE user_profiles
SET plan_tier = 'lifetime_pro', plan_expires_at = NULL, updated_at = NOW()
WHERE id = '<user_uuid>';
COMMIT;
```
broker_accounts.plan_tier updates automatically via trigger.

Suggested pricing: Starter lifetime $99 / Pro lifetime $199. Cap 50–100 seats.

---

## SECTION 10 — INFRASTRUCTURE & RELIABILITY

---

### WEEK 4 · Audit Link API Endpoint
**Owner:** ENG · **Estimate:** M · **File:** `backend/api/audit.py` (new)

```python
@app.post("/api/audit/generate")
async def generate_audit_link(
    request: AuditLinkRequest,
    current_user: User = Depends(get_current_user)
):
    signal = supabase.table("signals") \
        .select("*, broker_accounts!inner(user_id)") \
        .eq("id", request.signal_id) \
        .eq("broker_accounts.user_id", current_user.id) \
        .single().execute()

    if not signal.data:
        raise HTTPException(404, "Signal not found or not owned by user")

    audit_link = supabase.table("audit_links") \
        .insert({"signal_id": request.signal_id, "created_by": current_user.id}) \
        .execute()

    url = f"https://glassbox.io/audit/{audit_link.data[0]['id']}"
    logger.info(f"[AUDIT] Link generated: {url}")
    return {"url": url}
```

Rate limit: 20 audit links per user per day. Trial users have full access to generate links.

---

### WEEK 5 · Trial Expiry Cron Job
**Owner:** ENG · **Estimate:** S · **File:** Supabase pg_cron

```sql
-- Run hourly: mark expired trial accounts
SELECT cron.schedule(
  'check-trial-expiry',
  '0 * * * *',
  $$
  UPDATE user_profiles
  SET updated_at = NOW()
  WHERE plan_tier IS NULL AND trial_expires_at < NOW();
  -- The sync_effective_tier trigger fires, updating broker_accounts.plan_tier = 'trial_expired'
  $$
);
```

The worker reads `broker_accounts.plan_tier = 'trial_expired'` and halts signal execution. The dashboard reads `user_profiles.trial_expires_at` to show the Day 30 screen.

**Acceptance:** Simulate trial expiry by setting `trial_expires_at = NOW() - INTERVAL '1 hour'`. Cron runs → broker_accounts updated → worker skips signals → dashboard shows Day 30 screen.

---

### WEEK 5 · Session Countdown Timer Utility
**Owner:** ENG · **Estimate:** S · **File:** `utils/sessionTimes.ts` (new)

Function that returns "time until next London session" or "next NY session" in WAT. Accounts for weekends (no sessions Saturday/Sunday). Used in: onboarding checklist Step 4, cold-start state, audit link empty state.

---

## SECTION 11 — MARKETING & GROWTH (YOUR TASKS)

---

### WEEK 1 · DM Five Telegram Signal Providers
**Owner:** YOU · **Estimate:** S (2–3 hours) · **When:** Days 1–3

**Script:**
> "I'm building a transparency layer for MT5 execution — would you be willing to look at a demo? I think it could make your channel look more professional."

**What to look for:** 1,000–20,000 subscribers, ICT-based or Gold signals, Nigerian/African audience, active in last 7 days.

**New angle from trial decision:** You can now add: "There's a 30-day free trial, no credit card — so their followers can try it at zero risk." This makes the proposition to the provider much easier to say yes to.

**Goal:** ONE positive response = first real demand signal.

---

### WEEK 1 · Paystack Account Setup
**Owner:** YOU · **Estimate:** XS (30 min)

Submit Paystack business verification. Starts the clock on the 1–5 day review period.

---

### WEEK 4 · Lock In First Signal Provider Partnership
**Owner:** YOU · **Estimate:** M (ongoing)

Offer: free 6-month Pro account in exchange for one post featuring their Glass Box audit link.

**Updated pitch with trial:** "Your followers can start a 30-day free trial — no credit card required. You post one link, they get 30 days free, and if they love it they pay $15/mo. Zero friction for your audience."

---

### WEEK 1–6 · Telegram Content (Ongoing)
**Owner:** YOU · **Estimate:** XS per week · **1 post/week**

- Week 1: Product teaser — "Building a transparency layer for MT5"
- Week 2: XAUUSD feature live — show the first Gold signal
- Week 4: Share your own audit link — "This is what a Glass Box trade audit looks like"
- Week 5: Trial launch — "30-day free trial, no credit card. Link in bio."
- Week 6: Beta user results — session summary or testimonial

---

### WEEK 6 · Collect First User Testimonials
**Owner:** YOU · **Estimate:** XS

Message your first 3–5 paying users. Ask: "Would you share 2–3 sentences on how Glass Box has affected your trading, for the website?" Get explicit written permission before publishing.

---

## SECTION 12 — LEGAL & COMPLIANCE (YOUR TASKS)

---

### BEFORE PUBLIC LAUNCH · Legal/Compliance Consultation
**Owner:** YOU · **Estimate:** L · **When:** Week 1–2

Consult a Nigerian fintech/SaaS lawyer. Key questions:
1. Does auto-executing third-party Telegram signals require an SEC Nigeria licence?
2. Is "personal automation tool" framing legally distinct from licensed signal provision?
3. What disclosures are required before accepting Nigerian user payments?
4. Are there NDPR data protection requirements for storing MT5 credentials and trade data?

**Decision tree (decided):**
- Favourable → launch with signal-following framing
- Unfavourable → "personal automation" reframe. Either way: beta capped at 50 users.

---

### BEFORE PUBLIC LAUNCH · Terms of Service + Privacy Policy
**Owner:** YOU (with AI assistance) · **Estimate:** M · **When:** Week 2

Essential ToS clauses for Glass Box:
1. **Risk disclosure:** "Trading forex involves significant risk. Glass Box is an execution tool, not financial advice. Past performance does not guarantee future results."
2. **Trial terms:** "The 30-day free trial begins on the date of email confirmation. No credit card is required. After 30 days, the account is paused until a paid plan is selected."
3. **Subscription terms:** Monthly recurring billing via Paystack. Cancel anytime. No refunds on partial months (state clearly).
4. **Data storage:** MT5 credentials encrypted in Azure Key Vault. Trade logs in Supabase. No data sold to third parties.
5. **Service availability:** No guaranteed uptime. Not liable for trading losses due to service outages.

---

## SECTION 13 — QA & END-TO-END TESTING (WEEK 6)

---

### Full Trial-to-Paid Journey (THE PRIMARY QA FLOW)
**Owner:** ENG · **Estimate:** L · **When:** Week 6, Day 1

This is the most important QA path because it covers every major system interaction.

**Stage 1 — Sign up and start trial:**
1. Visit `/` → confirm "Start 30-Day Free Trial — No Credit Card Required" CTA is visible
2. Click CTA → confirm `/sign-up` (no plan param needed — everyone gets Pro trial)
3. Complete signup → confirm email → confirm arrival at `/dashboard`
4. Confirm onboarding checklist appears with trial badge ("30 days remaining")

**Stage 2 — Trial experience:**
5. Complete checklist: connect MT5 → set risk → choose markets (Pro markets all available)
6. Confirm trial countdown banner appears: "X days remaining"
7. Publish a test signal from backend → appears in Live Feed within 2 seconds
8. Signal executes (including NAS100 signal — trial should execute it)
9. Trade appears in Trade History → click row → VerdictSidebar opens
10. Generate audit link → open in incognito → confirm trade data visible + trial CTA "Start 30-Day Free Trial"
11. Open Replay Mode → confirm available (Pro feature, accessible during trial)
12. Open Prop Firm Panel → profit target visible (Pro feature, accessible during trial)

**Stage 3 — Trial expiry:**
13. Simulate expiry: set `trial_expires_at = NOW() - INTERVAL '1 hour'`
14. Wait for cron job (or trigger manually via SQL: `UPDATE user_profiles SET updated_at = NOW() WHERE id = '<test_id>'`)
15. Refresh dashboard → confirm Day 30 plan selection screen appears
16. Confirm cannot dismiss modal without choosing a plan
17. Confirm existing trade history is still visible in read-only state

**Stage 4 — Convert to Starter:**
18. Click "Continue with Starter — $15/mo" on Day 30 screen
19. Complete Paystack test checkout (card: `4084 0840 8408 4081`)
20. Webhook fires → `activate_subscription` RPC → `plan_tier = 'starter'`
21. Confirm Day 30 screen disappears
22. Confirm NAS100 tab now shows lock icon (Starter cannot access)
23. Confirm Replay Mode shows "Pro only" message
24. Try adding second account → confirm upgrade nudge modal

**Stage 5 — Upgrade to Pro from Starter:**
25. Click "Upgrade to Pro" in billing tab
26. Complete Paystack test checkout for Pro plan
27. Confirm `plan_tier = 'pro'`
28. Confirm NAS100 tab unlocks
29. Confirm Replay Mode is accessible again

---

### Email Drip Campaign QA
**Owner:** ENG · **Estimate:** S · **When:** Week 6, Day 2

Test each email using a test user account:
- Day 1 welcome: confirm sent immediately on email confirmation
- Day 7: manually advance `trial_started_at` to 7 days ago → confirm email sends
- Day 21: advance to 21 days ago → confirm urgency email sends with real trade count data
- Day 28: advance to 28 days ago → confirm deadline email sends
- Day 30: advance to 30 days ago → confirm expiry email sends + dashboard shows Day 30 screen

Confirm: no email sends twice (boolean flag system works).

---

### Full Pro Journey Test (Post-Trial)
**Owner:** ENG · **Estimate:** M · **When:** Week 6, Day 2

Test the full Pro journey for a user who converted to Pro at Day 30:
1. All Pro features accessible (NAS100, Replay Mode, multi-account, full Prop Firm Panel)
2. Can add second broker account (no upgrade nudge)
3. Halt event: banner appears + email after 15 minutes
4. Halt reset: banner disappears
5. Billing tab shows "Pro — $49/mo" with Manage Billing link

---

### Regression Pass
**Owner:** ENG · **Estimate:** M · **When:** Week 6, Day 3

Manual check on all pre-existing features:
- Live Mode chart renders EURUSD candles
- Trade History table loads, pagination works, direction filter works
- VerdictSidebar shows all ICT conditions
- PropFirmPanel basic metrics display
- Sign in → dashboard → sign out cycle
- Mobile layout at 375px width

---

### Performance Check
**Owner:** ENG · **Estimate:** S · **When:** Week 6, Day 3

| Metric | Target |
|---|---|
| Dashboard initial load (post-auth) | < 2 seconds |
| New signal in Live Feed | < 2 seconds from backend publish |
| Audit link page load (no auth) | < 1 second |
| Day 30 plan screen load | < 1 second |
| Paystack checkout load | < 3 seconds |

---

## APPENDIX: WEEK-BY-WEEK CHECKLIST

### Week 1 — Foundation + Trial CTA
- [ ] EURUSD strategy rewrite (no lookahead bias)
- [ ] `user_profiles` table + trial fields + trigger + RLS
- [ ] `plan_tier` denormalized into `broker_accounts` (with trial_expired state)
- [ ] Three missing DB indexes
- [ ] RLS audit (all tables)
- [ ] MT5 credentials audit (no plaintext in logs)
- [ ] Landing page: fix pricing to $15/$49 with trial badge
- [ ] Landing page: primary CTA → "Start 30-Day Free Trial — No Credit Card Required"
- [ ] Landing page: remove dead footer links
- [ ] Landing page: fix "Watch Live Demo" button
- [ ] Landing page: add ICT term tooltips
- [ ] Wire RiskTab "Save Defaults" button
- [ ] **[YOU]** DM 5 Telegram signal providers (new angle: "followers get 30-day free trial")
- [ ] **[YOU]** Set up Paystack account and submit verification

### Week 2 — XAUUSD + Auth + Trial Abuse Prevention
- [ ] XAUUSD strategy runner
- [ ] `broker_accounts.symbol` multi-value support (trial users get all Pro symbols)
- [ ] Trial abuse prevention (1 account during trial, email verification gating)
- [ ] Beta registration cap (50 users)
- [ ] Auth pages: design tokens, forgot password, password hint, post-signup redirect
- [ ] Rename "Chart Debugger" → "Replay Mode"
- [ ] Standardize sidebar icons
- [ ] First-login onboarding checklist (with trial badge)
- [ ] **[YOU]** Check Paystack verification status
- [ ] **[YOU]** Legal consultation booked
- [ ] **[YOU]** Week 2 Telegram content post (XAUUSD live)

### Week 3 — Indices + Tier Enforcement + Trial Worker Logic
- [ ] NAS100/US30/SPX500 runners
- [ ] Tier enforcement in worker.py (trial_expired halts all execution; trial='pro' executes all)
- [ ] Dashboard market tabs (trial users see all Pro markets unlocked)
- [ ] Engine halt banner (all pages)
- [ ] Halt notification email (15-min delay)
- [ ] PropFirmPanel config persistence
- [ ] Remove hardcoded "Uptime 99.7%"
- [ ] Verdict sidebar trigger on Overview rows
- [ ] Pro-locked market tab overlay (for post-trial Starter users only)
- [ ] Cold-start UX (post-onboarding)
- [ ] **[YOU]** Legal consultation complete, decision documented
- [ ] **[YOU]** Terms of Service + Privacy Policy published

### Week 4 — Live Data + Audit Link + Trial Countdown
- [ ] Supabase realtime verdict feed
- [ ] PropFirmPanel profit target tracker (Pro + trial)
- [ ] Date range filter on Trades page
- [ ] "Explain this" tooltips for ICT terms
- [ ] `audit_links` table
- [ ] Audit link generation API endpoint
- [ ] Audit link public page `/audit/[uuid]` (acquisition CTA = free trial offer)
- [ ] Realtime chart overlays in Live Mode
- [ ] Session countdown timer utility
- [ ] **[YOU]** Lock in first signal provider partnership (pitch: "followers get 30-day trial free")
- [ ] **[YOU]** Week 4 Telegram post (share your own audit link)

### Week 5 — Billing + Trial Infrastructure
- [ ] Trial countdown banner (Days 1–20 neutral, 21–27 amber, 28–29 red)
- [ ] Day 30 plan selection screen (3 paths: Pro / Starter / Pause)
- [ ] Trial expiry cron job (pg_cron, hourly, sets trial_expired)
- [ ] Trial email drip campaign (5 emails: Day 1, 7, 21, 28, 30)
- [ ] `activate_subscription` Supabase RPC (atomic)
- [ ] Paystack webhook handler with HMAC-SHA512 validation
- [ ] Paystack keys in Azure Key Vault
- [ ] Billing tab in Settings (shows trial state, then paid state)
- [ ] Upgrade nudge modal (Starter → Pro post-trial)
- [ ] Replay Mode slider (Pro + trial)
- [ ] FVG structured data in verdicts (stretch)
- [ ] Landing page social proof placeholder section
- [ ] **[YOU]** Test Paystack checkout end-to-end in test mode

### Week 6 — QA + Launch
- [ ] Landing page final polish (trial CTA prominent, pricing with trial badge)
- [ ] Full trial-to-paid journey test (all 29 steps)
- [ ] Trial email drip QA (all 5 emails)
- [ ] Full Pro journey test
- [ ] Regression pass on existing features
- [ ] Performance check (all 5 metrics)
- [ ] Session summary cards (stretch)
- [ ] **[YOU]** Collect first user testimonials
- [ ] **[YOU]** Replace placeholder testimonials with real quotes
- [ ] **[YOU]** Public launch announcement on Telegram: "30-day free trial, no credit card"

---

*Glass Box 6-Week Build Plan · Updated 2026-06-21 · 30-day Pro trial decision incorporated throughout.*
*Planning only — implementation begins on your signal.*
