# Glass Box — 6-Week Build Plan: Complete Task Breakdown

**Document purpose:** Every task across the 6-week GTM sprint, written in full detail, grouped by discipline. Every item here was discussed and decided across planning sessions. Nothing is speculative.

**How to read this:**
- Tasks are grouped by section (Backend, Frontend, Security, UX, Billing, etc.)
- Each task shows: which week, who owns it (You or Engineering), time estimate, full description, why it matters, and what "done" looks like
- Time estimates: XS = under 2h · S = half-day · M = full day · L = 2–3 days · XL = full week
- `[YOU]` = human task requiring no code · `[ENG]` = engineering task

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
- Every `self.get_historical_prices()` call uses an end index that is strictly before the current bar
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
- XAUUSD position sizing uses the Forex formula (`risk / sl_distance / 100_000`) but with a different pip value — XAUUSD is priced in dollars per troy ounce, not in pips the same way as EURUSD. Verify the lot size calculation produces correct dollar risk before going live.
- The runner is a copy of `ict_eurusd.py` with `SYMBOL = "XAUUSD"` / `"XAUUSDm"` substituted

**Acceptance criteria:**
- Backtest on XAUUSD 6-month data completes without errors
- Live runner connects to MT5, subscribes to XAUUSD tick feed, publishes verdicts with `symbol: "XAUUSD"` to Redis
- Verdicts appear in the Supabase `signals` table with correct symbol field

---

### WEEK 3 · NAS100, US30, SPX500 Runners (Pro-Only)
**Owner:** ENG · **Estimate:** L · **Files:** `backend/runners/ict_indices.py` (new)

**What:**
Three new strategy runners for US Indices. These are Pro-only instruments. Session window is NYSE open: 15:30–17:30 WAT (Nigerian Time), which is different from the London/NY forex windows.

**Why it matters:**
US Indices complete the Pro tier value proposition. The prop firm trader persona — the primary Pro target — often runs NAS100 or US30 challenges alongside forex. Having these instruments makes Glass Box a complete prop firm solution, not a forex-only tool.

**Important pre-conditions to verify before building:**
- Confirm IC Markets (and other supported brokers) serve NAS100, US30, SPX500 on MT5 and under what symbol names (NAS100, USTEC, US100 — broker-specific)
- Confirm Polygon.io serves these for backtesting
- The ICT strategy logic was designed for London session forex. Applying it to US indices in a different session requires verifying the same pattern logic holds — FVG detection on NAS100 M15 during NYSE open. Run a short backtest to confirm the logic doesn't produce nonsensical results on index candles.

**Session window for indices:**
NYSE opens at 14:30 UTC. In WAT (UTC+1) that is 15:30. The strategy window for indices should be 15:30–17:30 WAT to capture the first two hours of NYSE open — the highest volatility period for indices.

**Tier enforcement (covered in Security/Infrastructure section):**
The worker.py will skip NAS100/US30/SPX500 signals for Starter accounts. The runner itself publishes to all accounts — the tier filter is in the worker.

**Acceptance criteria:**
- Backtest on NAS100 produces verdicts without errors
- Live runner publishes NAS100/US30/SPX500 verdicts during 15:30–17:30 WAT window only
- A Pro-tier worker executes these signals; a Starter-tier worker skips them with `[TIER_GATE]` log entry

---

### WEEK 5 (STRETCH) · FVG Zone Structured Data
**Owner:** ENG · **Estimate:** M · **Files:** `backend/services/verdict.py`, `backend/strategies/ict_model.py`

**What:**
Update `build_verdict()` to include FVG zone data as a structured object that the frontend chart renderer can use to draw shaded rectangles.

**Current state:** FVG is stored as `fvg_top: float` and `fvg_bottom: float` in the verdict. The frontend can draw two price lines but cannot draw a filled rectangle between them using the current data structure.

**Target state:**
```python
verdict = {
  ...existing fields...,
  "fvg_zone": {
    "top": 1.08561,
    "bottom": 1.08490,
    "direction": "bearish",  # or "bullish"
    "confirmed_at": "2026-01-23T09:24:59Z"
  }
}
```

The frontend TradingView chart uses the `fvg_zone` object to render a semi-transparent rectangle between `fvg_bottom` and `fvg_top` using a custom series primitive or a positioned overlay div.

**Acceptance criteria:**
- Verdicts in Supabase `signals` table contain the `fvg_zone` JSONB object
- Chart overlay renders a shaded rectangle (blue for bullish FVG, red for bearish FVG) between the two price levels

---

## SECTION 2 — DATABASE & SCHEMA ARCHITECTURE

---

### WEEK 1 · `user_profiles` Table
**Owner:** ENG · **Estimate:** S · **File:** Supabase migration SQL

**What:**
Create the `user_profiles` table. This is the source of truth for each user's subscription tier.

**Schema:**
```sql
CREATE TABLE user_profiles (
  id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
  plan_tier TEXT NOT NULL DEFAULT 'starter'
    CHECK (plan_tier IN ('starter', 'pro', 'enterprise', 'lifetime_starter', 'lifetime_pro')),
  plan_expires_at TIMESTAMPTZ,         -- NULL = no expiry (lifetime or active subscription)
  onboarding_complete BOOLEAN DEFAULT FALSE,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Auto-create a user_profiles row for every new signup
CREATE OR REPLACE FUNCTION handle_new_user()
RETURNS TRIGGER LANGUAGE plpgsql SECURITY DEFINER AS $$
BEGIN
  INSERT INTO public.user_profiles (id)
  VALUES (NEW.id);
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

**Why it matters:**
Every tier enforcement decision flows from this table. The worker reads it (via the denormalized `broker_accounts.plan_tier` column) to decide which signals to execute. The frontend reads it to show or hide Pro features. This table must exist before any billing or tier enforcement work begins.

**Acceptance criteria:**
- New user signup automatically creates a `user_profiles` row with `plan_tier = 'starter'`
- User can only read and update their own row (RLS confirmed with two test accounts)
- Trigger fires correctly on every auth.users INSERT

---

### WEEK 1 · Denormalize `plan_tier` into `broker_accounts`
**Owner:** ENG · **Estimate:** S · **File:** Supabase migration SQL, `backend/services/worker.py`

**What:**
Add a `plan_tier` column to `broker_accounts`. Create a Postgres trigger that keeps it synchronized with `user_profiles.plan_tier`. This allows the worker to read the tier without a JOIN.

```sql
ALTER TABLE broker_accounts
ADD COLUMN plan_tier TEXT DEFAULT 'starter'
  CHECK (plan_tier IN ('starter', 'pro', 'enterprise', 'lifetime_starter', 'lifetime_pro'));

-- Sync trigger: when user_profiles.plan_tier changes, update all their accounts
CREATE OR REPLACE FUNCTION sync_plan_tier()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
  UPDATE broker_accounts
  SET plan_tier = NEW.plan_tier
  WHERE user_id = NEW.id;
  RETURN NEW;
END;
$$;

CREATE TRIGGER on_plan_tier_change
  AFTER UPDATE OF plan_tier ON user_profiles
  FOR EACH ROW EXECUTE FUNCTION sync_plan_tier();
```

**Why it matters:**
`worker.py` runs in a tight loop processing signals. Adding a JOIN to every signal-processing cycle adds an unnecessary database round-trip. Since plan_tier changes are rare (only on billing events), denormalization is the correct approach here.

**Acceptance criteria:**
- `worker.py` startup reads a single `broker_accounts` row and has `plan_tier` available with no additional queries
- Updating `user_profiles.plan_tier` automatically updates all `broker_accounts` rows for that user within milliseconds

---

### WEEK 1 · Three Missing DB Indexes
**Owner:** ENG · **Estimate:** XS · **File:** Supabase migration SQL

**What:**
Add three indexes that are missing and will cause slow queries as data grows.

```sql
-- 1. Join performance: broker_accounts by user
CREATE INDEX IF NOT EXISTS idx_broker_accounts_user_id
  ON broker_accounts(user_id);

-- 2. Dashboard trade history: per account, sorted by date
CREATE INDEX IF NOT EXISTS idx_signals_account_created
  ON signals(account_id, created_at DESC);

-- 3. Dashboard market filter: filter by symbol + sort by date
CREATE INDEX IF NOT EXISTS idx_signals_symbol_created
  ON signals(symbol, created_at DESC);
```

**Why it matters:**
At 50 users × 10 signals/day × 30 days = 15,000 rows in the first month. Without these indexes, every Trade History page load does a full table scan. This is invisible in development (< 100 rows) but causes 3–10 second load times in production at scale. Fix it before it becomes a problem.

**Acceptance criteria:**
- `EXPLAIN ANALYZE` on `SELECT * FROM signals WHERE account_id = $1 ORDER BY created_at DESC LIMIT 25` shows "Index Scan" not "Seq Scan"

---

### WEEK 2 · `broker_accounts.symbol` Multi-Value Support
**Owner:** ENG · **Estimate:** S · **Files:** `backend/services/worker.py`, `backend/services/orchestrator.py`

**What:**
Change `broker_accounts.symbol` from single-value text (`"EURUSD"`) to a comma-separated list (`"EURUSD,XAUUSD,GBPUSD"`). Worker reads the list and skips signals for symbols not in it.

**Why it matters:**
With XAUUSD launching in Week 2, users need to receive signals for multiple symbols on one account. Currently the column only holds one symbol — adding XAUUSD support requires this change.

**Backward compatibility:**
Existing rows with `symbol = "EURUSD"` continue to work exactly as before. The parsing code is:
```python
enabled_symbols = {s.strip() for s in account['symbol'].split(',')}
# "EURUSD" → {"EURUSD"}
# "EURUSD,XAUUSD" → {"EURUSD", "XAUUSD"}
```

**Default for new accounts:**
Starter accounts default to `"EURUSD,XAUUSD,GBPUSD,USDJPY"` (all Starter-eligible markets).
Pro accounts default to `"EURUSD,XAUUSD,GBPUSD,USDJPY,NAS100,US30,SPX500"`.

**Acceptance criteria:**
- Worker with `symbol = "EURUSD,XAUUSD"` receives and executes verdicts for both EURUSD and XAUUSD
- Worker with `symbol = "EURUSD"` skips XAUUSD verdicts silently
- No existing accounts break after migration

---

### WEEK 4 · `audit_links` Table
**Owner:** ENG · **Estimate:** S · **File:** Supabase migration SQL

**What:**
Create the `audit_links` table to store shareable audit link records.

```sql
CREATE TABLE audit_links (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),  -- this IS the public URL key
  signal_id UUID NOT NULL REFERENCES signals(id) ON DELETE CASCADE,
  created_by UUID NOT NULL REFERENCES auth.users(id),
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index for fast lookup by URL key
CREATE INDEX idx_audit_links_id ON audit_links(id);

-- RLS: anyone can SELECT (public read for audit link viewers)
ALTER TABLE audit_links ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Public read on audit_links"
  ON audit_links FOR SELECT USING (true);

CREATE POLICY "Authenticated users can create audit links"
  ON audit_links FOR INSERT WITH CHECK (auth.uid() = created_by);
```

**Why it matters:**
The shareable audit link is the core Telegram acquisition mechanic. Without this table, the B2B2C motion has no technical foundation. The public SELECT policy is intentional — anyone with the UUID link should be able to view the trade data, no login required.

---

### WEEK 5 · `activate_subscription` Supabase RPC
**Owner:** ENG · **Estimate:** M · **File:** Supabase migration SQL

**What:**
A Postgres stored procedure that atomically activates a user's subscription after a confirmed Paystack payment.

```sql
CREATE OR REPLACE FUNCTION activate_subscription(
  p_user_id UUID,
  p_plan TEXT
)
RETURNS VOID
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
  -- Validate plan value
  IF p_plan NOT IN ('starter', 'pro', 'enterprise', 'lifetime_starter', 'lifetime_pro') THEN
    RAISE EXCEPTION 'Invalid plan: %', p_plan;
  END IF;

  -- Update user profile
  UPDATE user_profiles
  SET
    plan_tier = p_plan,
    plan_expires_at = CASE
      WHEN p_plan LIKE 'lifetime_%' THEN NULL
      ELSE NOW() + INTERVAL '1 month'
    END,
    updated_at = NOW()
  WHERE id = p_user_id;

  -- Denormalized update on all accounts (trigger handles this, but be explicit)
  UPDATE broker_accounts
  SET plan_tier = p_plan
  WHERE user_id = p_user_id;

  -- Log the activation
  INSERT INTO subscription_events (user_id, plan, event_type, created_at)
  VALUES (p_user_id, p_plan, 'activated', NOW());
END;
$$;
```

**Why it matters:**
Paystack webhooks are the trigger for plan activation. Without an atomic RPC, a webhook handler might update `user_profiles` but crash before updating `broker_accounts`, leaving the user in a split state (user profile says Pro, accounts say Starter). The RPC wraps both updates in a single database transaction — either both happen or neither does.

---

## SECTION 3 — SECURITY

---

### WEEK 1 · Row Level Security Audit
**Owner:** ENG · **Estimate:** S

**What:**
Before any public user signs up, confirm RLS is enabled with correct policies on every table.

**Tables to audit:**
| Table | Expected policies |
|---|---|
| `user_profiles` | User reads/updates own row only |
| `broker_accounts` | User reads/updates/inserts own accounts only |
| `signals` | User reads signals for their own accounts only |
| `audit_links` | Public SELECT, authenticated INSERT (created_by = auth.uid()) |

**Test procedure:**
1. Create two test Supabase accounts (User A and User B)
2. Insert a signal for User A's account
3. Query `SELECT * FROM signals` as User B — must return 0 rows from User A
4. Query `SELECT * FROM broker_accounts` as User B — must return 0 rows from User A

**Why it matters:**
A missing RLS policy is a complete data privacy failure. Every trade, every broker credential reference, every account detail would be readable by any authenticated user. This is a critical security requirement — not an enhancement.

**Acceptance criteria:**
- All four tables have RLS enabled and verified
- Cross-user query test shows 0 rows leaked
- Test results documented

---

### WEEK 1 · MT5 Credentials Audit (No Plaintext in Logs)
**Owner:** ENG · **Estimate:** XS · **Files:** `backend/services/worker.py`, `backend/brokers/mt5_broker.py`, `backend/services/orchestrator.py`

**What:**
Grep all log statements across the execution stack to confirm that MT5 ACCOUNT, PASSWORD, and SERVER values are never written to log files.

**Why it matters:**
The VM stores rotating log files (10MB × 5 backups). If the VM is ever compromised, those log files must not contain broker credentials. The credentials are in Azure Key Vault specifically so they never touch disk in plaintext.

**Procedure:**
```bash
# Search for any log statement that might include credential variable names
grep -rn "logger\." backend/ | grep -i "account\|password\|server"
# Also search for f-strings that might interpolate credentials
grep -rn "f\".*{.*account\|password\|server" backend/
```

**Acceptance criteria:**
- No log statement writes raw MT5 credentials
- If account ID (a number, not secret) is logged for debugging, confirm it's the account ID number only, not the password

---

### WEEK 5 · Paystack Webhook Signature Validation
**Owner:** ENG · **Estimate:** M · **File:** `backend/api/webhooks.py` (new)

**What:**
Every Paystack webhook must be validated with HMAC-SHA512 before processing. This is the most critical security requirement in the billing integration.

**Why it matters:**
Without signature validation, any attacker who discovers your webhook URL can send a fake `charge.success` event with any email address and upgrade any account to Pro for free. This is not a theoretical risk — it is a well-known attack against payment webhooks with no signature verification.

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

    # Use compare_digest to prevent timing attacks
    # NEVER use signature == expected (timing-vulnerable)
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
        plan = resolve_plan_from_code(plan_code)  # "starter" or "pro"

        user = supabase.auth.admin.get_user_by_email(user_email)
        supabase.rpc("activate_subscription", {
            "p_user_id": user.id,
            "p_plan": plan
        }).execute()

        logger.info(f"[BILLING] Subscription activated: {user_email} → {plan}")

    return {"status": "ok"}
```

**Paystack secret storage:**
Store the Paystack secret key in Azure Key Vault:
```bash
az keyvault secret set \
  --vault-name calibabasecret \
  --name PAYSTACK-SECRET-KEY \
  --value "<your-paystack-secret-key>"
```

**Acceptance criteria:**
- Webhook with tampered body returns HTTP 401
- Webhook with valid signature and `charge.success` event activates the subscription
- Webhook with unrecognized event type returns 200 with no action (do not reject unknown events — Paystack will retry on failure)
- All outcomes logged with `[BILLING]` or `[WEBHOOK_INVALID]` tag

---

### WEEK 3 · Tier Enforcement in Worker (Fail-Closed)
**Owner:** ENG · **Estimate:** M · **File:** `backend/services/worker.py`

**What:**
Worker reads `plan_tier` from `broker_accounts` at startup. For every incoming signal, if the symbol is Pro-only and the account is Starter, the worker skips the signal.

**Implementation:**
```python
PRO_ONLY_SYMBOLS = frozenset({"NAS100", "US30", "SPX500"})

class Worker:
    def __init__(self, account_id):
        account = self._fetch_account(account_id)
        if account is None:
            logger.error(f"[TIER_GATE_ERROR] Cannot load account {account_id}. Worker halting.")
            raise RuntimeError("Account not found")

        self.plan_tier = account.get("plan_tier")
        if self.plan_tier is None:
            logger.error(f"[TIER_GATE_ERROR] plan_tier missing on account {account_id}. Halting.")
            raise RuntimeError("plan_tier not set")

    def handle_signal(self, signal: dict):
        symbol = signal.get("symbol", "")

        if symbol in PRO_ONLY_SYMBOLS and self.plan_tier == "starter":
            logger.info(
                f"[TIER_GATE] Skipping {symbol} signal — account is Starter tier"
            )
            return

        # Proceed with execution
        self._execute_signal(signal)
```

**Fail-closed design:**
If `plan_tier` cannot be read (database error, missing column), the worker raises and halts rather than defaulting to allowing all symbols. Defaulting to "allow all" would give away Pro features in error states — unacceptable.

**Acceptance criteria:**
- Starter worker receives NAS100 signal → logs `[TIER_GATE]` → no MT5 order submitted
- Pro worker receives NAS100 signal → order submitted normally
- Worker with missing `plan_tier` logs `[TIER_GATE_ERROR]` and exits — orchestrator respawns it

---

### WEEK 2 · Beta Registration Cap (Max 50 Users)
**Owner:** ENG · **Estimate:** XS · **File:** Supabase SQL

**What:**
Limit public signups to 50 users during beta. The 51st signup attempt is rejected with a clear message.

**Implementation (Supabase trigger):**
```sql
CREATE OR REPLACE FUNCTION check_beta_cap()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
DECLARE
  user_count INT;
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

**Why:**
The legal review cap and the "create scarcity" lifetime deal strategy both require a hard cap. Once 50 users are in, new visitors should see "Beta is full — join the waitlist" rather than a generic error.

**Note:** The cap value (50) should be configurable. Store it in a `config` table or as a Supabase secret so you can raise it without a code deploy.

---

## SECTION 4 — FRONTEND: LANDING PAGE

---

### WEEK 1 · Fix Pricing to $15/$49
**Owner:** ENG · **Estimate:** XS · **Files:** `Landing.tsx`, `PricingSection.tsx`

**What:**
The current landing page shows $49/$99 (old pricing). Change everywhere to: Starter = $15/mo, Pro = $49/mo.

**Every location to update:**
- PricingSection card headers
- Hero section micro-copy (if it references price)
- NavBar CTA tooltip (if any)
- Any `<meta>` description tags referencing pricing
- The Starter card's value line: "Less than the cost of one losing manual trade"

**Why:**
$15 is the Nigerian impulse-buy threshold. $49 positions Glass Box $4 above Prop Firm One Premium (the nearest competitor at $44.99/mo). The pricing was approved through market research — the UI must match.

---

### WEEK 1 · Two-Track CTA Structure
**Owner:** ENG · **Estimate:** M · **Files:** `HeroSection.tsx`, `PricingSection.tsx`

**What:**
Replace the single CTA with two distinct, visible paths targeting both user personas.

**Hero section — two CTA buttons side by side:**
```
[Auto-execute signals on my MT5 →]     [Run my prop firm challenge →]
   primary (brand-blue)                   secondary (ghost/outline)
   /sign-up?plan=starter                  /sign-up?plan=pro
```

The primary (Starter) CTA is more prominent because Starter acquisition is the focus of the first 30 days.

**Pricing section — each card has its own CTA:**
- Starter card: "Get Early Access — Starter" → `/sign-up?plan=starter`
- Pro card: "Get Early Access — Pro" → `/sign-up?plan=pro`
- Enterprise card: "Contact for Enterprise" → mailto or contact form

**Why:**
Archetype 1 (signal follower) and Archetype 3 (prop firm candidate) have completely different motivations. A single generic CTA addresses neither of them directly. Two-track CTAs let each persona self-identify and follow a journey tailored to them.

---

### WEEK 1 · Landing Page Quick Fixes (4 items)
**Owner:** ENG · **Estimate:** S total · **Files:** `Landing.tsx`, `Footer.tsx`, `HeroSection.tsx`, `NavBar.tsx`

**Fix 1 — Remove dead footer links:**
Delete links to About, Blog, Careers pages until those pages exist. Keep only: Terms, Privacy, and any live social links. Dead links are a trust signal failure.

**Fix 2 — "Start Free Trial" → "Request Early Access":**
There is no free trial. There is no billing live yet. Change every instance of "Start Free Trial" to "Request Early Access." This is an honesty requirement — false promises destroy trust faster than any other single issue on a landing page.

**Fix 3 — Fix "Watch Live Demo" button:**
This button currently scrolls to the features section, not a demo. Either:
- Option A: Link to a real screen-recording demo video (if you have one)
- Option B: Rename to "See How It Works" — this is honest about what it does (scrolls to the HowItWorks section)

**Fix 4 — Add "Explain this" tooltips on ICT terms:**
The landing page introduces FVG, MSS, ICT, OB, BOS to a cold audience. Every bolded technical term must have a plain-English tooltip. These are already specified in DESIGN.md Section 7. Port the `<Term>` component and apply it to all ICT terms in the WhatIsGlassBox and HowItWorks sections.

---

### WEEK 6 · Social Proof Section
**Owner:** ENG + You · **Estimate:** M · **Files:** `Landing.tsx`, `TestimonialsSection.tsx` (new)

**What:**
Add a testimonials section between the PropFirmSection and PricingSection.

**Structure:** 3 testimonial cards in a horizontal row (stack vertically on mobile). Each card:
- Quote (2–3 sentences max)
- Name + optional Telegram handle
- Plan badge (STARTER / PRO in the tier color)
- Avatar (initials if no photo)

**For beta:** Use placeholder testimonials clearly marked as "Early Beta Feedback" until you have 3 real paying user quotes with permission.

**Why:**
No social proof is a conversion killer. Visitors from Telegram who don't know you personally need third-party validation. A signal provider's followers have never heard of Glass Box — testimonials bridge the credibility gap.

---

## SECTION 5 — FRONTEND: AUTHENTICATION

---

### WEEK 2 · Auth Page Design Token Fix
**Owner:** ENG · **Estimate:** XS · **Files:** Sign-in component, Sign-up component

**What:**
Replace hardcoded hex colors (`#141921`, `#0f1419`) on auth pages with design tokens (`bg-bg-surface`, `bg-bg-base`).

**Why:**
Every component should reference the design system's tokens, not raw hex values. If the palette ever changes, hardcoded values are missed in find-replace and cause visual inconsistency. This takes 15 minutes and has zero risk.

**Acceptance:** Run a grep for `#141921` and `#0f1419` across auth component files — zero results.

---

### WEEK 2 · Forgot Password Link
**Owner:** ENG · **Estimate:** XS · **File:** Sign-in component

**What:**
Add a "Forgot your password?" link below the login form. It should trigger Supabase's built-in password reset flow.

**Implementation:**
Supabase Auth UI React handles this natively. Add a link styled as `text-brand-blue text-sm` that either:
- Changes the `<Auth />` component's `view` prop to `"forgotten_password"`, OR
- Calls `supabase.auth.resetPasswordForEmail(email)` directly with the user's entered email

**Acceptance:** Clicking "Forgot password?" sends a password reset email from Supabase and shows a confirmation message.

---

### WEEK 2 · Password Length Hint on SignUp
**Owner:** ENG · **Estimate:** XS · **File:** Sign-up component

**What:**
Add `Minimum 8 characters` as a hint below the password field on the SignUp page.

**Why:**
Supabase enforces a minimum password length. Without a hint, users try passwords like "abc123" and get a cryptic auth error. The hint prevents this frustrating UX loop entirely.

---

### WEEK 2 · Fix Post-Signup Redirect
**Owner:** ENG · **Estimate:** XS · **Files:** Sign-up component, Supabase project settings

**What:**
After email confirmation, users currently land on `/sign-in`. Change this so they land on `/dashboard` already logged in.

**Two-part fix:**
1. In `<Auth redirectTo="/dashboard" />` — set the redirect URL on the Auth component
2. In Supabase Dashboard → Authentication → URL Configuration: add `https://yourdomain.com/dashboard` to the Redirect URLs allowlist. Supabase will reject redirectTo values not on the allowlist.

**Why:**
Redirecting a new user back to the login page after they've just confirmed their identity is confusing and creates unnecessary friction. The confirmation link already authenticated them — send them directly to the product.

---

## SECTION 6 — FRONTEND: DASHBOARD & CORE UI

---

### WEEK 1 · Wire RiskTab "Save Defaults" Button
**Owner:** ENG · **Estimate:** S · **File:** `RiskTab.tsx` or `Settings.tsx`

**What:**
The Settings > Risk tab "Save Defaults" button currently does nothing. Wire it to persist the form values to Supabase.

**Target schema:** Save risk config to the `broker_accounts` row for the user's account:
- `risk_amount` (float) — dollar amount at risk per trade
- `rr_ratio` (float) — risk-reward ratio target
- `breakeven_buffer` (int) — ticks of profit before SL moves to entry
- `max_daily_drawdown_pct` (float) — halt threshold

**UX:** After successful save, show a shadcn/ui `toast()` confirmation: "Risk configuration saved." On save failure, show: "Could not save — please try again."

**Why:**
Non-functional buttons signal an unfinished product. For beta users, this is especially damaging — they are evaluating whether to pay. A broken button in Settings is a red flag.

---

### WEEK 3 · Remove Hardcoded "Uptime 99.7%"
**Owner:** ENG · **Estimate:** XS · **Files:** `Overview.tsx` or `StatCards.tsx`

**What:**
Delete the hardcoded "Uptime 99.7%" string from the Overview dashboard.

**Why:**
This is fabricated data. Showing users a metric that isn't real damages trust the moment they notice it. Remove it entirely — the Engine Status card already shows the real running/halted state.

**Acceptance:** No hardcoded uptime percentage appears on the dashboard in any production code path.

---

### WEEK 3 · Verdict Sidebar Trigger on Overview Signals Rows
**Owner:** ENG · **Estimate:** S · **Files:** `OverviewPage.tsx`, `VerdictSidebar.tsx`

**What:**
The "Recent Signals" table rows on the Overview page currently do nothing when clicked. Add an `onClick` handler that opens the VerdictSidebar with the selected signal's full data.

**Implementation:**
```tsx
// In the signals table row
<tr
  className="cursor-pointer hover:bg-bg-elevated transition-colors"
  onClick={() => dispatch({ type: 'SELECT_VERDICT', verdict: signal })}
>
  ...row content...
</tr>
```

The `VerdictSidebar` already exists and accepts a verdict object. This task is purely wiring the click event.

**Why:**
The signal rows are the most visible data in the Overview. They are currently inert. Clicking them is the most natural next action for a user who wants to understand what the bot did — that should be one click away from anywhere in the dashboard.

---

### WEEK 3 · Rename "Chart Debugger" → "Replay Mode"
**Owner:** ENG · **Estimate:** XS · **File:** `Sidebar.tsx` or `DashboardLayout.tsx`

**What:**
Change the sidebar navigation item from "Chart Debugger" to "Replay Mode." Change the icon from whatever debugging icon is used to `Rewind` or `Play` from Lucide.

**Why:**
"Replay Mode" is the name used everywhere in marketing copy, the pricing table, and the product overview. "Chart Debugger" is a development-era internal name. Consistency between marketing promise and in-product label is not optional.

---

### WEEK 3 · Standardize Sidebar Icons (Lucide Only)
**Owner:** ENG · **Estimate:** XS · **File:** `Sidebar.tsx`

**What:**
Replace every emoji and Unicode symbol in the sidebar navigation with Lucide icons.

**Mapping:**
- Overview → `LayoutDashboard`
- Live Feed → `Activity`
- Replay Mode → `Rewind` or `Play`
- Trade History → `List`
- Prop Firm Panel → `Shield`
- Settings → `Settings`
- Documentation → `HelpCircle`
- Sign Out → `LogOut`

**Why:**
Visual inconsistency (mixing emoji 🔴 with Lucide icons in the same navigation) signals that different parts of the app were built without a coherent design system. The DESIGN.md specifies Lucide exclusively — this is a 20-minute fix.

---

### WEEK 3 · Engine Halt Banner
**Owner:** ENG · **Estimate:** M · **Files:** `DashboardLayout.tsx`, account status context

**What:**
A full-width, prominent banner that appears across all dashboard pages when the trading engine is halted.

**Design:**
```
┌───────────────────────────────────────────────────────────────────────────┐
│  ⛔  ENGINE HALTED — Daily loss limit reached ($280 / $1,000 limit).      │
│      No new trades will be taken until 00:00 UTC (resets in 14h 22m).    │
│      Existing open positions continue running to their stop loss or TP.  │
└───────────────────────────────────────────────────────────────────────────┘
```

- Background: `bg-bear-dim` (dark red)
- Left border: `border-l-4 border-bear` (solid red left edge)
- Dismiss button: `[✕]` in top-right. Dismisses for the current session but reappears on page reload while halt is still active.
- Auto-dismiss: Disappears automatically when `broker_accounts.status` changes back to `'active'`
- Must appear on: Overview, Live Feed, Trades, Prop Firm Panel, Settings — every page inside the dashboard layout

**Data source:** Subscribe to `broker_accounts` realtime and check `status === 'halted'`. The halt banner condition is: any of the user's accounts has `status = 'halted'`.

**Why:**
A prop firm user whose engine is halted needs to know immediately — regardless of which page they're viewing. Missing a halt event during a prop firm challenge could mean the difference between passing and failing.

---

### WEEK 3 · Halt Notification Email (15-Minute Delay)
**Owner:** ENG · **Estimate:** M · **File:** Supabase Edge Function or backend service

**What:**
When a broker account's status changes to `'halted'`, and it remains halted for more than 15 minutes, send an email to the account owner.

**Why:**
Users may not have the dashboard open when a halt triggers. The halt could happen at any time during the London or NY session. Email ensures they know what happened without requiring 24/7 dashboard monitoring.

**Implementation approach:**
Option A (recommended): Supabase Database Webhook → Edge Function. On `broker_accounts.status = 'halted'` INSERT/UPDATE, the webhook fires and the Edge Function records a `halt_events` row with `halted_at`. A scheduled Edge Function (CRON via pg_cron) checks every 5 minutes for halt events older than 15 minutes where `email_sent = false`, sends the email via Resend or SendGrid, and marks `email_sent = true`.

**Log format:** `[HALT_NOTIFY] Account {account_id} halted at {time}. Email sent to {email}.`

**Acceptance:** Simulated halt on test account → email arrives within 20 minutes. Email does not send again if the account remains halted (no duplicate sends).

---

### WEEK 3 · PropFirmPanel Config Persistence
**Owner:** ENG · **Estimate:** S · **Files:** `PropFirmPage.tsx`, Supabase

**What:**
The PropFirm page configuration (daily limit, consecutive losses max, challenge end date) resets to defaults on every page reload. Persist it to Supabase.

**Storage approach:**
Add JSONB columns to `broker_accounts`:
```sql
ALTER TABLE broker_accounts
ADD COLUMN prop_firm_config JSONB DEFAULT '{}';
```

Example value:
```json
{
  "daily_loss_limit_usd": 200,
  "max_consecutive_losses": 3,
  "profit_target_usd": 800,
  "challenge_end_date": "2026-07-21"
}
```

**On page mount:** Read `prop_firm_config` from the broker account row and populate form defaults. On save: PATCH the row with the updated config. Show a save confirmation toast.

**Why:**
A prop firm user who has set FTMO Phase 1 rules ($200 daily limit, 3 max consecutive losses) should not have to re-enter their challenge parameters every time they reload the page. This is basic usability.

---

### WEEK 4 · Supabase Realtime Verdict Feed
**Owner:** ENG · **Estimate:** M · **Files:** `RealtimeProvider.tsx`, `LiveLogicFeed.tsx`

**What:**
Switch the live verdict feed from polling to Supabase realtime WebSocket subscriptions.

**Current state:** Dashboard polls for new signals every ~5–30 seconds. New verdicts appear with up to 30 seconds of delay.

**Target state:** New signals appear within 1–2 seconds of being published by the backend — as close to real-time as the network allows.

**Implementation (from DESIGN.md §9):**
```js
// In RealtimeProvider, after auth session confirmed:
supabase.channel('signals')
  .on('postgres_changes', {
    event: 'INSERT',
    schema: 'public',
    table: 'signals'
  }, (payload) => {
    dispatch({ type: 'NEW_SIGNAL', signal: payload.new });
  })
  .subscribe();

supabase.channel('broker_accounts')
  .on('postgres_changes', {
    event: 'UPDATE',
    schema: 'public',
    table: 'broker_accounts',
    filter: `user_id=eq.${userId}`
  }, (payload) => {
    dispatch({ type: 'ACCOUNT_UPDATE', account: payload.new });
  })
  .subscribe();
```

**Acceptance:** Publish a test verdict from the Python backend. It appears in the dashboard Live Feed within 2 seconds — verified by watching the dashboard while running the backend.

---

### WEEK 4 · PropFirmPanel Profit Target Tracker
**Owner:** ENG · **Estimate:** S · **Files:** `PropFirmPanel.tsx`, `PropFirmPage.tsx`

**What:**
Add a profit target progress tracker to the Prop Firm Panel. Pro-only feature.

**Design:**
```
PROFIT TARGET
━━━━━━━━━━━━━━━━━━━░░░░░░░░░░  45% toward target
Earned: $3,600 / $8,000 target   18 days remaining
```

- Progress bar: `bg-bull` fill on `bg-bg-elevated` track
- Show dollar amount and percentage
- "Days remaining" = challenge end date (from `prop_firm_config`) minus today
- Update dynamically as trades close

**Why:**
The #1 job-to-be-done for Pro users is "pass my prop firm challenge." FTMO Phase 1 requires an 8% profit target. Without a profit target tracker, Pro users are missing the most important metric that tells them whether they're on track. This is the feature that makes the Prop Firm Panel actually useful for challenge management.

---

### WEEK 4 · Date Range Filter on Trades Page
**Owner:** ENG · **Estimate:** S · **Files:** `TradeHistory.tsx` or `TradePage.tsx`

**What:**
Add a date range picker to the top of the Trade History table. The table shows only trades within the selected date range. CSV export also respects the filter.

**Implementation:**
Use shadcn/ui's Calendar or DatePicker component for a date range input. On change, update the Supabase query:
```js
.from('signals')
.select('*')
.eq('account_id', accountId)
.gte('created_at', startDate.toISOString())
.lte('created_at', endDate.toISOString())
.order('created_at', { ascending: false })
```

Default: Last 30 days.

---

### WEEK 4 · "Explain This" ICT Tooltips in Dashboard
**Owner:** ENG · **Estimate:** S · **Files:** `VerdictSidebar.tsx`, `LiveLogicFeed.tsx`

**What:**
Add hover tooltips to ICT terms throughout the dashboard using the `<Term>` component from the landing page.

**Terms and tooltips to add:**

| Term | Tooltip |
|---|---|
| FVG | A price gap where the market moved so fast that buyers and sellers never fully traded at those levels. Smart money returns to fill these gaps. |
| MSS | Market Structure Shift — the moment the market definitively changes direction, identified when price breaks a prior swing point. |
| BOS | Break of Structure — confirmation that the prior swing high or low has been decisively broken. |
| CHoCH | Change of Character — an early signal of direction reversal before full MSS confirmation. |
| OB | Order Block — a price zone where large institutional orders were previously placed. Price often returns to this zone. |
| PDH / PDL | Previous Day High / Low — the highest and lowest prices from the prior session. Key reference levels. |
| Sweep Point | The price level where the market swept past a key high or low to trigger retail stop losses, before reversing. |
| R:R | Risk-to-Reward ratio. 3R means for every $1 risked, the target is $3 profit. |
| Breakeven | Moving the stop loss to the entry price — meaning the trade can no longer result in a loss. |

**Apply tooltips in:**
- VerdictSidebar: all condition row labels
- LiveLogicFeed: event type labels
- PropFirmPanel: metric labels where relevant

**Accessibility:** Tooltips must be keyboard-triggerable (focus), not hover-only.

---

### WEEK 5 · Billing Tab in Settings
**Owner:** ENG · **Estimate:** M · **Files:** `Settings.tsx`, `SubscriptionTab.tsx` (new)

**What:**
Add a "Subscription & Billing" tab to the Settings page.

**Starter view:**
```
Current Plan: STARTER
$15 / month · Next billing: July 21, 2026

[Manage Billing ↗]

──────────────────────────────
Upgrade to Pro — $49/mo

✓ Up to 10 broker accounts
✓ US Indices (NAS100, US30, SPX500)
✓ Replay Mode
✓ Full Prop Firm Panel with profit target

[Upgrade to Pro →]
```

**Pro view:**
```
Current Plan: PRO
$49 / month · Next billing: July 21, 2026

[Manage Billing ↗]   [Cancel Plan]
```

**"Manage Billing"** links to Paystack's customer portal URL for the user's subscription (Paystack provides this URL in the subscription object).

**Why:**
Without a billing tab, users have no way to manage their subscription from within the app. "Cancel Plan" being hard to find increases support overhead. A clear, honest billing page reduces churn anxiety.

---

### WEEK 5 · Upgrade Nudge Modal
**Owner:** ENG · **Estimate:** S · **Files:** `Settings.tsx`, `UpgradeNudgeModal.tsx` (new)

**What:**
When a Starter user clicks "Add Account," show a modal instead of the Add Account form.

**Modal design:**
```
┌─────────────────────────────────────────────────┐
│  🔒 Multiple Accounts — Pro Feature             │
│                                                  │
│  You're on the Starter plan (1 broker account). │
│  Upgrade to Pro to connect up to 10 accounts    │
│  and run multi-account prop firm challenges.    │
│                                                  │
│  Pro — $49/mo                                   │
│  ✓ Up to 10 accounts                            │
│  ✓ US Indices                                   │
│  ✓ Replay Mode                                  │
│                                                  │
│  [Upgrade to Pro →]         [Maybe Later]       │
└─────────────────────────────────────────────────┘
```

**Why:**
Two purposes: (1) prevents silent failure when a Starter user tries to use a Pro feature, and (2) creates a natural, non-pushy upsell moment at exactly the right time — when the user has just demonstrated interest in a Pro feature.

---

## SECTION 7 — FRONTEND: CHARTS & TRADING VISUALIZATION

---

### WEEK 4 · Shareable Audit Link Page (`/audit/[uuid]`)
**Owner:** ENG · **Estimate:** L · **Files:** `/audit/[uuid].tsx` (new), `backend/api/audit.py` (new)

**What:**
A public page at `/audit/{uuid}` showing the full verdict for a specific trade. No authentication required to view.

**Page sections:**

**1. Header:**
```
GLASS BOX AUDIT — TRADE #4E21F3
SELL — EURUSD — 23 Jan 2026 — 10:25:00 WAT
Generated by [provider name or "a Glass Box user"]
```

**2. Trade summary:**
Entry / SL / TP / R:R in a clean grid. Direction badge (SELL ▼ in red, BUY ▲ in green).

**3. ICT conditions checklist:**
All condition rows with ✓ or — (not ✗ — a condition being false for this trade is not an error, it's just not applicable).

**4. Execution details:**
Status (FILLED/REJECTED), latency, timestamp.

**5. Acquisition CTA (bottom):**
```
────────────────────────────────────────────────────────
This audit was generated by Glass Box — the MT5 execution
engine that shows you everything it does and why.

Want your own auto-execution account?
[Get Started with Glass Box — $15/mo →]
────────────────────────────────────────────────────────
```

**Empty state (no trades yet on the account):**
```
Glass Box is scanning for setups...
Next London session: TODAY at 09:00 WAT (opens in 6h 14m)
Scanning: EURUSD · XAUUSD · GBPUSD

Want your own execution account?
[Get Started — $15/mo]
```

**Backend endpoint:**
`POST /api/audit/generate` (authenticated) → validates signal belongs to calling user → creates `audit_links` row → returns `{ url: "https://glassbox.io/audit/{uuid}" }`

**Why:**
This is the single highest-leverage engineering task in the entire 6-week plan. One audit link shared in a 5,000-member Telegram channel can generate 50+ page views. At 5% conversion, that's 2–3 Starter signups from one share. Without this, the entire Telegram acquisition strategy has no technical mechanism.

---

### WEEK 4–5 · Realtime Chart Overlays in Live Mode
**Owner:** ENG · **Estimate:** M · **Files:** `CandlestickChart.tsx`, `ChartDebuggerPage.tsx`

**What:**
When the chart is in Live Mode, ICT overlays (FVG zones, MSS levels, sweep points) appear on the chart as soon as a verdict is published — not on the next manual refresh.

**Current state:** Overlays are drawn from historical signal data on page load. New signals require a page refresh to appear.

**Target state:** The realtime subscription (already delivering signals to React state) also triggers chart overlay updates.

**Implementation:**
```tsx
useEffect(() => {
  if (!latestSignal || !candleSeriesRef.current) return;

  // Add MSS level line
  candleSeriesRef.current.createPriceLine({
    price: latestSignal.mss_level,
    color: '#D29922',
    lineWidth: 1,
    lineStyle: LineStyle.Dotted,
    title: 'MSS'
  });

  // Add FVG boundary lines
  candleSeriesRef.current.createPriceLine({
    price: latestSignal.fvg_top,
    color: '#F8514980',
    lineWidth: 1,
    title: 'FVG Top'
  });
}, [latestSignal]);
```

---

### WEEK 5 · Replay Mode Slider
**Owner:** ENG · **Estimate:** M · **Files:** `ReplaySlider.tsx`, `ChartDebuggerPage.tsx`

**What:**
A timeline slider below the chart that lets Pro users scrub backward through any past session. Moving the slider rewinds the chart to that moment in time and shows only conditions known at that timestamp.

**Design:**
- Full-width `<input type="range" />` below the chart
- `accent-color: var(--brand-blue)` for the thumb and active track
- Tick marks below the slider for each trade in the current date range
- Label showing the selected timestamp in WAT format
- `[◀ Previous Trade]` and `[Next Trade ▶]` buttons to jump between trades

**Behavior:**
1. Slider controls `replayTimestamp` state
2. Chart's visible time range re-centers on `replayTimestamp`
3. Overlays update to show only conditions from signals with `created_at <= replayTimestamp`
4. VerdictSidebar populates with the signal nearest to `replayTimestamp`

**Gate:** Pro-only. Starter users see a "Replay Mode is available on Pro" state instead of the slider.

---

## SECTION 8 — UX & PRODUCT DESIGN

---

### WEEK 2 · First-Login Onboarding Checklist
**Owner:** ENG · **Estimate:** L · **Files:** `OnboardingChecklist.tsx` (new), `OverviewPage.tsx`

**What:**
New users who log in for the first time see an onboarding checklist at the top of the Overview page instead of an empty dashboard.

**The checklist (4 steps):**

**Step 1 — Connect your MT5 account**
*"Add your broker account credentials so Glass Box can execute trades on your behalf."*
→ [Connect Account] button links to Settings > Broker Accounts

**Step 2 — Set your risk configuration**
*"Tell Glass Box how much to risk per trade and your drawdown limits."*
→ [Configure Risk] button links to Settings > Risk
- This step auto-completes when `broker_accounts.risk_amount` is non-null

**Step 3 — Choose your markets**
*"Select which forex pairs and markets you want Glass Box to scan and trade."*
→ [Choose Markets] button opens the symbol selector in Settings
- Starter users see EURUSD, XAUUSD, GBPUSD, USDJPY
- Pro users also see NAS100, US30, SPX500

**Step 4 — Wait for the next session**
*"Glass Box scans during London (09:00–11:00 WAT) and NY (13:00–17:00 WAT) sessions."*
→ Shows a live countdown timer: "Next London session opens in 14h 22m"
- This step auto-completes when the first signal is received

**Completion:**
When all 4 steps are checked, show a success state: "Glass Box is set up and scanning. Your first trade is on the way."
Then persist `user_profiles.onboarding_complete = true` and hide the checklist permanently.

**Progress persistence:**
Store step completion state in `user_profiles` as a JSONB column or individual boolean fields so the checklist reflects actual progress on page reload.

**Why:**
This is the highest-impact UX task in the entire plan. A new user who sees an empty dashboard and doesn't know what to do will churn within 24 hours. The onboarding checklist converts "I'm confused" to "I know exactly what to do next."

---

### WEEK 3–4 · Cold-Start Experience (Post-Checklist, Pre-First-Trade)
**Owner:** ENG · **Estimate:** M · **Files:** `EmptyChartState.tsx` (new), `LiveLogicFeed.tsx`

**What:**
Design the dashboard experience between "onboarding complete" and "first trade executed." The user has connected their MT5 account and knows Glass Box is scanning, but the next London session is 14 hours away.

**Why this matters:**
This is the highest-churn moment in the user lifecycle. Users who completed setup and then see nothing for 14 hours think the product is broken or their setup failed. Most will not wait — they'll cancel and demand a refund.

**Solution — the waiting state:**
Replace the empty chart with:

1. **"Glass Box is scanning" status card:**
   - Pulsing green dot + "ENGINE RUNNING — Scanning for setups"
   - Confirms the engine is active and working

2. **Next session countdown:**
   - "Next London session opens in 14h 22m"
   - Live countdown updating every minute

3. **Live scan events (even if no verdict):**
   Show the last 5 scan events from the Live Logic Feed, even if no verdict was reached:
   - "Scanning EURUSD M15 for liquidity sweep above PDH... No conditions met"
   - "Scanning XAUUSD M15... No sweep detected"
   This shows the engine is running and actively checking conditions.

4. **"While you wait" section:**
   - Link to the Replay Mode with message: "See how past trades were executed → Open Replay Mode"
   - Link to GLASS_BOX_OVERVIEW.md for understanding the ICT strategy

**Acceptance:** A user who completes onboarding on a Sunday evening sees the countdown to Monday's London session and at least 3 recent scan log entries showing active scanning.

---

### WEEK 3 · Pro-Locked Market Tab Overlay
**Owner:** ENG · **Estimate:** S · **Files:** Market tab selector component

**What:**
NAS100, US30, and SPX500 market tabs are visible to Starter users but locked. Clicking a locked tab shows a tooltip: "US Indices are available on Pro ($49/mo). Upgrade →"

**Design:**
```
[EURUSD] [XAUUSD] [GBPUSD] [USDJPY] | [NAS100 🔒] [US30 🔒] [SPX500 🔒] [BTC 🔒 Soon]
```

- Lock icon: Lucide `Lock` (12px, text-text-muted)
- Clicking locked tab: shows shadcn Popover with upgrade CTA, does not navigate
- "BTC 🔒 Soon" is a special case: grayed out, shows "Coming post-launch"

**Why:**
The locked tabs serve two purposes: they show Starter users what they're missing (creating upgrade motivation), and they prevent silent failures if a Starter account somehow tries to load Pro-only data.

---

## SECTION 9 — BILLING & MONETISATION

---

### WEEK 1 · Paystack Account Setup (YOUR TASK)
**Owner:** YOU · **Estimate:** XS (30 min)

**What:**
Create a Paystack business account and submit for identity verification.

**Steps:**
1. Go to paystack.com → Create account with your business email
2. Settings → Business Profile → Enter: business name, address, business type (Software/SaaS)
3. Submit government ID and bank account details for settlement
4. Verification typically takes 1–5 business days

**Why start in Week 1:**
Paystack requires verified status before you can charge real money. Starting verification in Week 1 means it clears by Week 3, well before the Week 5 billing integration. If you wait until Week 5 to start verification, your billing go-live date slips to Week 7.

---

### WEEK 5 · Paystack Subscription Integration (Full)
**Owner:** ENG · **Estimate:** XL · **Files:** `SubscriptionTab.tsx`, `backend/api/webhooks.py`, Supabase RPC

**What:**
Complete Paystack billing integration for Starter ($15/mo) and Pro ($49/mo) recurring subscriptions.

**Full architecture:**

**Step 1 — Create Paystack Plans:**
In your Paystack dashboard, create two recurring plans:
- Name: "Glass Box Starter Monthly" | Amount: $15.00 | Interval: monthly
- Name: "Glass Box Pro Monthly" | Amount: $49.00 | Interval: monthly

Store the plan codes in Azure Key Vault:
- `PAYSTACK-STARTER-PLAN-CODE` → plan_XXXXX
- `PAYSTACK-PRO-PLAN-CODE` → plan_YYYYY
- `PAYSTACK-PUBLIC-KEY` → pk_live_XXXXX

**Step 2 — Frontend checkout initiation:**
```js
// When user clicks "Subscribe" or "Upgrade"
const initializePayment = (planCode: string) => {
  const handler = PaystackPop.setup({
    key: process.env.NEXT_PUBLIC_PAYSTACK_PUBLIC_KEY,
    email: user.email,
    plan: planCode,
    callback: (response) => {
      // Do NOT activate subscription here — wait for webhook
      // Just show "Payment received, activating your plan..."
      setPaymentState('processing');
    },
    onClose: () => {
      setPaymentState('idle');
    }
  });
  handler.openIframe();
};
```

**Step 3 — Backend webhook handler (see Security section for full implementation)**

**Step 4 — Subscription status display:**
The frontend subscribes to `user_profiles` realtime. When `plan_tier` updates (triggered by the webhook → RPC), the billing tab re-renders automatically with the new plan.

**Test the full loop in Paystack test mode before going live:**
1. Use Paystack test card: `4084 0840 8408 4081`, CVV `408`, expiry any future date
2. Complete checkout → webhook fires to your local ngrok URL → RPC runs → plan_tier updates → dashboard shows Pro features

**Acceptance:**
- End-to-end test: checkout → webhook → plan activation → dashboard update — all within 10 seconds
- Webhook signature validation works (see Security section)
- RPC is atomic (both user_profiles and broker_accounts update together)

---

### PRE-LAUNCH · Lifetime Deal Manual Provisioning (YOUR TASK)
**Owner:** YOU · **Estimate:** XS (5 min per user)

**What:**
Before Paystack billing is live, you may sell lifetime deals manually. Here is how to provision a lifetime account in Supabase.

**Via Supabase Dashboard → SQL Editor:**
```sql
-- Replace <user_uuid> with the actual user's UUID from auth.users
BEGIN;

UPDATE user_profiles
SET
  plan_tier = 'lifetime_pro',  -- or 'lifetime_starter'
  plan_expires_at = NULL,       -- NULL = never expires
  updated_at = NOW()
WHERE id = '<user_uuid>';

UPDATE broker_accounts
SET plan_tier = 'lifetime_pro'
WHERE user_id = '<user_uuid>';

COMMIT;
```

**Finding a user's UUID:**
Supabase Dashboard → Authentication → Users → search by email → copy UUID.

**Suggested lifetime pricing (from CEO review):**
- Starter lifetime: $99 (6.6 months of equivalent value)
- Pro lifetime: $199 (~4 months of equivalent value)
- Cap: maximum 50–100 total lifetime seats to create urgency

---

## SECTION 10 — INFRASTRUCTURE & RELIABILITY

---

### WEEK 4 · Audit Link Generation Endpoint
**Owner:** ENG · **Estimate:** M · **File:** `backend/api/audit.py` (new)

**What:**
A FastAPI (or Flask) endpoint that authenticated Starter/Pro users call to generate a shareable audit link for a specific trade.

```python
@app.post("/api/audit/generate")
async def generate_audit_link(
    request: AuditLinkRequest,
    current_user: User = Depends(get_current_user)
):
    # Verify the signal belongs to this user's account
    signal = supabase.table("signals") \
        .select("*, broker_accounts!inner(user_id)") \
        .eq("id", request.signal_id) \
        .eq("broker_accounts.user_id", current_user.id) \
        .single() \
        .execute()

    if not signal.data:
        raise HTTPException(404, "Signal not found or not owned by user")

    # Create the audit link record
    audit_link = supabase.table("audit_links") \
        .insert({
            "signal_id": request.signal_id,
            "created_by": current_user.id
        }) \
        .execute()

    link_id = audit_link.data[0]["id"]
    url = f"https://glassbox.io/audit/{link_id}"

    logger.info(f"[AUDIT] Link generated: {url} for signal {request.signal_id}")
    return {"url": url}
```

**Rate limiting:**
Add a simple rate limit: max 20 audit links per user per day. Prevents abuse.

---

### WEEK 5 · Session Countdown Timer Utility
**Owner:** ENG · **Estimate:** S · **File:** `utils/sessionTimes.ts` (new)

**What:**
A frontend utility that calculates "time until next London session" or "time until next NY session" in WAT.

```typescript
type Session = {
  name: 'London' | 'New York';
  opensAt: Date;
  minutesUntilOpen: number;
};

export function getNextSession(): Session {
  const now = new Date();
  // Convert to WAT (UTC+1)
  const watHour = (now.getUTCHours() + 1) % 24;
  const watMinutes = now.getUTCMinutes();
  const dayOfWeek = now.getDay(); // 0=Sun, 6=Sat

  // London: 09:00–11:00 WAT, Mon–Fri
  // New York: 13:00–17:00 WAT, Mon–Fri

  // ... calculate next session opening time ...
  // Return the sooner of the two upcoming session opens,
  // accounting for weekends (skip to Monday 09:00 if Fri after 17:00)
}
```

**Used in:**
- Onboarding checklist Step 4
- Cold-start dashboard state
- Audit link empty state page

---

## SECTION 11 — MARKETING & GROWTH (YOUR TASKS)

---

### WEEK 1 · DM Five Telegram Signal Providers
**Owner:** YOU · **Estimate:** S (2–3 hours) · **When:** Days 1–3 of Week 1

**What:**
Identify and personally message five ICT-adjacent Telegram signal providers who serve Nigerian or African audiences. This is your most important task in the entire 6-week plan.

**The message script (use this exact framing):**
> "I'm building a transparency layer for MT5 execution — would you be willing to look at a demo? I think it could make your channel look more professional."

**Why this framing works:**
- You are not pitching a product or asking for money
- You are offering something that benefits THEM (their channel looks more credible)
- It is low-commitment: "look at a demo" is one conversation, not a partnership agreement
- Signal providers are defensive about their credibility — this framing speaks directly to their fear

**What to look for in target providers:**
- Channel size: 1,000–20,000 subscribers (large enough to matter, small enough to respond to a DM)
- Content: ICT-based signals or XAUUSD/Gold signals for Nigerian/African traders
- Engagement: Are followers asking questions? Reacting? An engaged community of 2,000 beats a ghost audience of 20,000
- Recency: The channel should have been active in the last 7 days

**Goal:**
ONE "yes, show me" response from the five DMs. That is the first real demand signal. Not revenue — a conversation.

**Done when:** At least 1 of 5 DMs results in a positive response or a scheduled demo call.

---

### WEEK 2 · Paystack Verification Follow-Up
**Owner:** YOU · **Estimate:** XS · **When:** Day 1 of Week 2

**What:**
Check Paystack verification status. If still pending, follow up with Paystack support.

**Why:**
Paystack verification sometimes stalls without a nudge. Checking at Week 2 gives you 3 weeks of buffer before the Week 5 billing integration. If it's not done by Week 3, you have a problem.

---

### WEEK 4 · Lock In First Signal Provider Partnership
**Owner:** YOU · **Estimate:** M (ongoing) · **When:** Weeks 4–5

**What:**
Convert one of the Week 1 DMs into an active partnership. Offer a free 6-month Pro account in exchange for one post to their Telegram channel featuring their Glass Box audit link.

**What you are offering:**
- 6-month Pro account: free ($49/mo × 6 = $294 of value)
- No exclusivity required — they can continue doing whatever they do
- One post to their channel is all you need: "Check out what Glass Box did on my account this week" with the audit link

**What you get:**
- Distribution to 1,000–20,000 engaged forex traders
- Social proof (a real provider used it publicly)
- Your first audit link in the wild — the B2B2C acquisition loop starts here

**Done when:** One provider has a live Glass Box Pro account and has committed (in writing, even just a message) to posting one audit link.

---

### WEEK 1–6 · Telegram Content (Ongoing)
**Owner:** YOU · **Estimate:** XS per week · **When:** 1 post per week

**Suggested posts by week:**
- Week 1: "Building a transparency layer for MT5. Here's what the live feed looks like." (screenshot of LiveLogicFeed)
- Week 2: "Gold (XAUUSD) support just shipped. Here's the first signal from today's London session."
- Week 4: "This is what an ICT trade audit looks like: [share your own audit link]"
- Week 5: "Early access is now $15/mo. 50 seats. Link in bio."
- Week 6: "Here's what Week 1 on Glass Box looked like for our beta users." (session summary)

---

### WEEK 6 · Collect First User Testimonials
**Owner:** YOU · **Estimate:** XS · **When:** End of Week 6

**What:**
Message your first 3–5 paying users and ask for a short testimonial.

**The ask:**
> "I'm putting together a few words on the landing page from early users. Would you mind sharing in 2–3 sentences how Glass Box has affected your trading? With your permission, I'd like to add it to the website."

**Critical:** Do not add any quote to the landing page without explicit written permission from the user.

**Done when:** 2 testimonials in hand with permission to publish.

---

## SECTION 12 — LEGAL & COMPLIANCE (YOUR TASKS)

---

### BEFORE PUBLIC LAUNCH · Legal/Compliance Consultation
**Owner:** YOU · **Estimate:** L (1–2 business days) · **When:** Week 1–2

**What:**
Book a consultation with a Nigerian lawyer who specialises in fintech, technology, or financial services. This is not optional before public launch.

**Questions to ask:**
1. Does auto-executing third-party Telegram signals on a user's MT5 account require an SEC Nigeria licence or any other regulatory approval?
2. Is the "personal automation tool" framing — where the user pre-configures rules and the bot executes those rules on their own account — legally distinct from operating as a licensed signal provider?
3. What disclosures must appear on the landing page before accepting payments from Nigerian users?
4. What terms of service clauses are essential for a trading automation SaaS product?
5. Are there specific data protection requirements under NDPR (Nigeria Data Protection Regulation) that apply to storing MT5 credentials, trade data, and user emails?

**Decision tree (already decided in CEO review):**
- Legal opinion is favourable → launch with full signal-following framing
- Legal opinion is unfavourable → reposition as "personal automation": user configures their own ICT rules, bot executes pre-set rules on their own account. Remove "signal following" language from all marketing.
- Either way: keep beta capped at 50 users until review is complete

**Finding a lawyer:**
- Techlaw.ng and similar Nigerian tech-focused legal directories
- The Starthub.ng community has lawyer referrals for startups
- Budget: expect ₦50,000–₦200,000 for a consultation + basic ToS review

---

### BEFORE PUBLIC LAUNCH · Terms of Service + Privacy Policy
**Owner:** YOU (with AI assistance) · **Estimate:** M · **When:** Week 2

**What:**
Before any public user signs up, the landing page must link to a Terms of Service and Privacy Policy.

**Essential clauses for Glass Box ToS:**

1. **Risk disclosure (mandatory):**
   > "Trading forex and other financial instruments involves significant risk of loss. Glass Box is an execution automation tool, not financial or investment advice. Past strategy performance does not guarantee future results. By using Glass Box, you accept that you may lose your entire deposited trading capital."

2. **No warranty of profit:**
   Explicit statement that Glass Box makes no profit guarantees and no return projections.

3. **Personal use / execution tool:**
   > "Glass Box executes trades on your personal broker account based on your configured rules. You are responsible for all trades executed on your account. Glass Box does not act as a broker, fund manager, or licensed financial adviser."

4. **Data storage:**
   MT5 credentials are encrypted and stored in Azure Key Vault. Trade logs stored in Supabase. No user data is sold to third parties. Data is used only to provide the Glass Box service.

5. **Service availability:**
   No guaranteed uptime (especially important for an early-stage product). Trading losses due to service outages are not the company's liability.

**Privacy Policy must cover (NDPR compliance):**
- What data is collected (email, MT5 account number, trade history)
- How it is stored and secured
- User right to request deletion
- Contact information for data requests

**Quick path:** Use Termly.io generator for a basic version. Have the lawyer review before publication.

---

## SECTION 13 — QA & END-TO-END TESTING (WEEK 6)

---

### Full Starter Journey Test
**Owner:** ENG · **Estimate:** L · **When:** Week 6, Days 1–2

The complete end-to-end path to test manually:

1. Land on `/` → confirm Starter and Pro CTAs are visible and correctly labeled
2. Click "Get Early Access — Starter" → confirm arrival at `/sign-up?plan=starter`
3. Complete signup → confirm email → confirm arrival at `/dashboard` (not `/sign-in`)
4. Confirm onboarding checklist appears with all 4 steps unchecked
5. Complete Step 1: Add MT5 account (use test credentials) → confirm step checks off
6. Complete Step 2: Set risk config → save → reload page → confirm values persisted
7. Complete Step 3: Confirm markets are pre-selected for Starter tier
8. Confirm Step 4 shows session countdown
9. Publish a test signal from the backend → confirm it appears in Live Feed within 2 seconds
10. Confirm signal executes on test MT5 account
11. Trade appears in Trade History → click row → VerdictSidebar opens with full ICT data
12. Generate audit link from the trade → open in incognito window → confirm trade data visible + acquisition CTA visible
13. Click acquisition CTA → confirm `/sign-up?plan=starter` loads
14. Attempt to add second account → confirm upgrade nudge modal appears
15. Click on NAS100 tab → confirm lock icon + upgrade tooltip appear (no crash)
16. Simulate halt event → confirm halt banner appears on all pages

---

### Full Pro Journey Test
**Owner:** ENG · **Estimate:** L · **When:** Week 6, Days 2–3

1. Sign up as Pro (or upgrade from Starter via Paystack test mode)
2. Confirm NAS100/US30/SPX500 tabs are accessible without lock icons
3. Open Replay Mode → confirm chart renders → move slider → confirm chart rewinds and VerdictSidebar updates
4. Set prop firm rules (daily limit $200 + profit target $800 + challenge end date) → reload → confirm values persist
5. Add second broker account → confirm no upgrade nudge (Pro can have up to 10)
6. Simulate halt → confirm halt banner + email after 15 minutes (use a test email address)
7. Simulate halt reset → confirm banner disappears
8. Confirm Billing tab shows Pro plan details with "Manage Billing" link

---

### Regression Pass
**Owner:** ENG · **Estimate:** M · **When:** Week 6, Day 4

Manual regression check on all features that existed before the 6-week sprint:
- Live Mode chart renders EURUSD candles correctly
- Trade History table loads (check pagination, filtering by direction)
- VerdictSidebar shows all ICT condition fields for pre-existing trades
- Prop Firm Panel basic metrics (daily drawdown bar) display correctly
- Sign in → dashboard → sign out cycle completes cleanly
- Mobile layout at 375px width: sidebar collapses, layout doesn't break

---

### Performance Check
**Owner:** ENG · **Estimate:** S · **When:** Week 6, Day 4

Measure against these targets:
| Metric | Target | How to measure |
|---|---|---|
| Dashboard initial load (post-auth) | < 2 seconds | Chrome DevTools Network tab |
| New signal in Live Feed | < 2 seconds from backend publish | Manual timer while watching dashboard |
| Audit link page load | < 1 second | Chrome DevTools (no auth = simpler page) |
| Paystack checkout load | < 3 seconds | Manual observation |

If any target is missed, document the bottleneck. Do not optimize prematurely — document and defer unless the miss is severe (> 5 seconds).

---

## APPENDIX: WEEK-BY-WEEK CHECKLIST

### Week 1 — Foundation
- [ ] EURUSD strategy rewrite (no lookahead bias)
- [ ] `user_profiles` table + trigger + RLS
- [ ] `plan_tier` denormalized into `broker_accounts`
- [ ] Three missing DB indexes
- [ ] RLS audit (all tables)
- [ ] MT5 credentials audit (no plaintext in logs)
- [ ] Landing page: fix pricing to $15/$49
- [ ] Landing page: two-track CTA structure
- [ ] Landing page: remove dead footer links, rename CTA button, fix demo button
- [ ] Wire RiskTab "Save Defaults" button
- [ ] **[YOU]** DM 5 Telegram signal providers
- [ ] **[YOU]** Set up Paystack account and submit verification

### Week 2 — XAUUSD + Auth
- [ ] XAUUSD strategy runner
- [ ] `broker_accounts.symbol` multi-value support
- [ ] Beta registration cap (50 users)
- [ ] Auth pages: design tokens, forgot password, password hint, post-signup redirect
- [ ] Rename "Chart Debugger" → "Replay Mode"
- [ ] Standardize sidebar icons
- [ ] First-login onboarding checklist
- [ ] **[YOU]** Check Paystack verification status
- [ ] **[YOU]** Legal consultation booked
- [ ] **[YOU]** Week 2 Telegram content post

### Week 3 — Indices + Tier Enforcement
- [ ] NAS100/US30/SPX500 runners
- [ ] Tier enforcement in worker.py (fail-closed)
- [ ] Dashboard market tabs (Starter vs Pro views)
- [ ] Engine halt banner (all pages)
- [ ] Halt notification email (15-min delay)
- [ ] PropFirmPanel config persistence
- [ ] Remove hardcoded "Uptime 99.7%"
- [ ] Verdict sidebar trigger on Overview rows
- [ ] Pro-locked market tab overlay
- [ ] Cold-start UX (post-onboarding)
- [ ] **[YOU]** Legal consultation complete, decision documented
- [ ] **[YOU]** Terms of Service + Privacy Policy published

### Week 4 — Live Data + Audit Link
- [ ] Supabase realtime verdict feed
- [ ] PropFirmPanel profit target tracker
- [ ] Date range filter on Trades page
- [ ] "Explain this" tooltips for ICT terms
- [ ] `audit_links` table
- [ ] Audit link generation API endpoint
- [ ] Audit link public page `/audit/[uuid]`
- [ ] Realtime chart overlays in Live Mode
- [ ] Session countdown timer utility
- [ ] **[YOU]** Lock in first signal provider partnership
- [ ] **[YOU]** Week 4 Telegram post (share your own audit link)

### Week 5 — Billing
- [ ] `activate_subscription` Supabase RPC
- [ ] Paystack webhook handler with HMAC-SHA512 validation
- [ ] Paystack public key in Azure Key Vault
- [ ] Paystack secret key in Azure Key Vault
- [ ] Billing tab in Settings
- [ ] Upgrade nudge modal (Starter → Pro)
- [ ] Replay Mode slider (Pro-only)
- [ ] FVG structured data in verdicts (stretch)
- [ ] Social proof placeholder section on landing page
- [ ] **[YOU]** Test Paystack checkout end-to-end in test mode

### Week 6 — QA + Launch
- [ ] Landing page final polish (complete two-track structure)
- [ ] End-to-end Starter journey test
- [ ] End-to-end Pro journey test
- [ ] Regression pass on existing features
- [ ] Performance check (load times, realtime latency)
- [ ] Session summary cards (stretch)
- [ ] **[YOU]** Collect first user testimonials
- [ ] **[YOU]** Replace placeholder testimonials with real quotes on landing page
- [ ] **[YOU]** Public launch announcement on Telegram

---

*Glass Box 6-Week Build Plan · Authored 2026-06-21 · Planning only — implementation begins on your signal.*
