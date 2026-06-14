# Glass Box Trading Engine — Comprehensive Frontend Design Guide
### For AI Agent Execution · React + Tailwind CSS + shadcn/ui

---

## 0. How to Read This Document

This guide is written for an AI agent executing the full frontend build of the Glass Box Trading Engine. It covers **two product surfaces simultaneously**:

1. **The Marketing/Landing Page** — converts visitors (total beginners → experienced traders) into sign-ups
2. **The Dashboard Application** — the logged-in product experience for active users

Every section includes: intent, audience context, visual spec, component spec, copy direction, data binding, and accessibility notes. Do not skip sections. Do not improvise where the spec is explicit.

---

## 1. Project Context & Product Philosophy

### What Glass Box Is

Glass Box is an algorithmic trading engine built on the ICT (Inner Circle Trader) methodology. It detects trade setups in the forex market using deterministic rule-based logic — not AI guesswork — and simultaneously executes those trades across 50+ MT5 broker accounts with per-account risk sizing.

The name "Glass Box" is the core brand promise: **you can see everything the bot sees, exactly when it sees it.** Unlike black-box AI bots that show you a P&L and ask you to trust them, Glass Box shows you the exact FVG it detected, the MSS level it confirmed, the sweep point it identified, and the moment the Verdict was reached.

### Three User Archetypes (Design Must Serve All Three)

**Archetype 1 — "The Curious Newcomer"**
- Has heard about forex/trading on social media
- Does not know what FVG, MSS, ICT mean
- Motivated by: passive income, automation, not having to learn trading
- Fear: being scammed, losing money, not understanding what they signed up for
- Design need: clear plain-English explanations, visible trust signals, no jargon without definition, a sense of control without complexity

**Archetype 2 — "The Struggling Trader"**
- Has been trading manually for 6–24 months
- Knows ICT concepts but executes inconsistently due to emotion
- Motivated by: discipline, removing FOMO, systematic execution
- Fear: the bot deviating from "real" ICT rules, hidden fees, not being able to verify logic
- Design need: proof that the logic is legitimate, verifiable trade breakdowns, transparency over the signal, performance metrics

**Archetype 3 — "The Prop Firm Candidate"**
- Actively pursuing FTMO / MyForexFunds / similar challenge
- Has strict daily drawdown limits, max loss rules, consistency requirements
- Motivated by: passing a prop firm challenge without emotional mistakes
- Fear: bot violating prop firm rules, missing max daily loss limits, erratic execution
- Design need: prop firm constraint panel, per-account risk controls, halt status visible at all times

---

## 2. Tech Stack & Constraints

```
Framework:        React (Vite)
Styling:          Tailwind CSS v3
Component Library: shadcn/ui (use CLI: npx shadcn-ui@latest add [component])
Auth:             Supabase
Realtime:         Supabase JS client (subscribe() for live signals/executions)
Charts:           Lightweight Charts by TradingView (npm: lightweight-charts)
Icons:            Lucide React
Fonts:            See §3
State:            React Context + useReducer for global state; React Query (TanStack) for server state
```

**Do not use:** Material UI, Chakra UI, Bootstrap, Ant Design, or any other component library in addition to shadcn/ui.

**Do not use:** `localStorage` or `sessionStorage` for sensitive data. All auth state is managed by Supabase.

---

## 3. Design System

### 3.1 Aesthetic Direction

**Theme:** Dark-first. Precision Fintech. "Terminal Meets Gallery."

The visual language should feel like a Bloomberg terminal that went to art school — dense, data-rich, and authoritative, but with typographic refinement and deliberate use of space that signals this is not a cheap dashboard cobbled together over a weekend.

Key aesthetic decisions:
- **No gradients as backgrounds** — use gradients sparingly as accent/glow effects only
- **Borders, not shadows** — use `border` for card separation; avoid `box-shadow` on cards
- **Monospaced numbers** — all price figures, percentages, and timestamps use a monospaced font
- **Status is communicated by shape + color** — never color alone (colorblind accessibility)
- **Animation is functional** — every animation communicates data change, not decoration

### 3.2 Color Palette

Define as Tailwind CSS custom colors and CSS variables:

```css
:root {
  /* Backgrounds */
  --bg-base:       #080C10;   /* deepest background — page canvas */
  --bg-surface:    #0D1117;   /* card/panel surfaces */
  --bg-elevated:   #161B22;   /* nested panels, dropdowns */
  --bg-overlay:    #1C2128;   /* modals, tooltips */

  /* Borders */
  --border-subtle: #21262D;   /* default card borders */
  --border-muted:  #30363D;   /* slightly visible separators */
  --border-active: #388BFD;   /* focused/active states */

  /* Text */
  --text-primary:  #E6EDF3;   /* body text */
  --text-secondary:#8B949E;   /* labels, captions */
  --text-muted:    #484F58;   /* disabled, placeholder */
  --text-inverse:  #0D1117;   /* text on light surfaces */

  /* Brand */
  --brand-blue:    #388BFD;   /* primary CTA, links, active state */
  --brand-blue-dim:#1F6FEB;   /* hover states */
  --brand-glow:    rgba(56, 139, 253, 0.15); /* glow/halo effects */

  /* Semantic — Trading */
  --bull-green:    #3FB950;   /* BUY signals, profit */
  --bull-dim:      #1A4A22;   /* BUY background fills */
  --bear-red:      #F85149;   /* SELL signals, loss */
  --bear-dim:      #4A1A1A;   /* SELL background fills */
  --neutral-amber: #D29922;   /* warnings, pending, prop-firm caution */
  --neutral-amber-dim: #3D2E00;

  /* Special */
  --halt-red:      #FF6B6B;   /* drawdown halt — critical */
  --breakeven:     #A8B1FF;   /* breakeven move events — indigo */
}
```

Map these to `tailwind.config.js` under `theme.extend.colors`:
```js
colors: {
  bg: {
    base:     'var(--bg-base)',
    surface:  'var(--bg-surface)',
    elevated: 'var(--bg-elevated)',
    overlay:  'var(--bg-overlay)',
  },
  border: {
    subtle: 'var(--border-subtle)',
    muted:  'var(--border-muted)',
    active: 'var(--border-active)',
  },
  brand: { blue: 'var(--brand-blue)', dim: 'var(--brand-blue-dim)' },
  bull:  { DEFAULT: 'var(--bull-green)', dim: 'var(--bull-dim)' },
  bear:  { DEFAULT: 'var(--bear-red)',   dim: 'var(--bear-dim)' },
  amber: { DEFAULT: 'var(--neutral-amber)', dim: 'var(--neutral-amber-dim)' },
  text: {
    primary:   'var(--text-primary)',
    secondary: 'var(--text-secondary)',
    muted:     'var(--text-muted)',
  },
}
```

### 3.3 Typography

**Display / Headings:** `Space Mono` — a monospaced slab that reads as both technical and editorial. Use for hero headlines and section titles.

**Body / UI:** `Geist` (Vercel's typeface — available via `npm install geist`) — clean, legible, slightly geometric. Use for all body copy, labels, descriptions.

**Numbers / Prices:** `JetBrains Mono` — strict monospaced, consistent glyph width for ticker data. Apply via a utility class `.font-mono` or a dedicated `<Num>` component.

```css
/* Load via Google Fonts or self-host */
@import url('https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=JetBrains+Mono:wght@400;500;600&display=swap');
/* Install Geist via npm */
```

**Type Scale (Tailwind classes):**
```
Display:   text-5xl font-bold tracking-tight (Space Mono)
H1:        text-3xl font-bold              (Space Mono)
H2:        text-xl  font-semibold          (Geist)
H3:        text-base font-semibold         (Geist)
Body:      text-sm  font-normal            (Geist)
Caption:   text-xs  text-text-secondary    (Geist)
Ticker:    text-sm  font-mono              (JetBrains Mono)
```

### 3.4 Spacing & Grid

- Base unit: 4px (Tailwind's default)
- Page max-width: `max-w-screen-2xl` (1536px), centered, with `px-6` on mobile, `px-8` on desktop
- Dashboard layout: fixed left sidebar (240px) + main content area
- Card padding: `p-4` (16px) standard, `p-6` (24px) for prominent panels
- Section gaps: `gap-4` between cards in a grid, `gap-6` between major sections

### 3.5 Border Radius

- Cards: `rounded-lg` (8px)
- Buttons: `rounded-md` (6px)
- Badges/chips: `rounded-full`
- Chart containers: `rounded-xl` (12px)

### 3.6 Motion Principles

- Duration: 150ms for micro-interactions (hover, focus); 300ms for panel transitions; 500ms for data reveals
- Easing: `ease-out` for entrances; `ease-in` for exits
- Live data updates: use a flash animation (`bg-brand-glow → transparent`) for 400ms when a value updates in real-time — do not use jarring full re-renders
- Do not animate layout shifts — use fixed-height containers for streaming data to prevent CLS

```css
@keyframes data-flash {
  0%   { background-color: var(--brand-glow); }
  100% { background-color: transparent; }
}
.data-updated { animation: data-flash 400ms ease-out; }
```

---

## 4. Marketing / Landing Page

### 4.1 Page Structure Overview

```
/  (public route)
├── <NavBar />             — Sticky top nav
├── <HeroSection />        — Hook + primary CTA
├── <TrustBar />           — Social proof / credibility signals
├── <WhatIsGlassBox />     — Problem → Solution (beginner-friendly)
├── <HowItWorks />         — 3-step visual process
├── <GlassBoxFeature />    — The "killer feature" visual demo section
├── <PropFirmSection />    — Targeting prop firm traders specifically
├── <PricingSection />     — Plans + CTA
├── <FAQSection />         — Objection handling
└── <Footer />             — Links, legal, socials
```

---

### 4.2 `<NavBar />`

**Behavior:** Transparent on load, transitions to `bg-bg-surface/90 backdrop-blur-md border-b border-border-subtle` after scrolling 80px. Sticky (`position: sticky; top: 0; z-index: 50`).

**Contents (left to right):**
- Logo: `⬡ GLASS BOX` — the hex icon (⬡) in `text-brand-blue`, "GLASS BOX" in Space Mono bold, all caps, `text-text-primary`
- Nav links (center, hidden on mobile): `How It Works`, `Features`, `Prop Firm`, `Pricing`
- Right: `Sign In` (ghost button) + `Start Free Trial` (solid brand-blue button)

**Mobile:** Hamburger menu → full-screen slide-down drawer with same links + both CTAs stacked.

**Component spec:**
```jsx
<nav className="sticky top-0 z-50 transition-all duration-300">
  <div className="max-w-screen-2xl mx-auto px-6 md:px-8 h-16 flex items-center justify-between">
    <Logo />
    <NavLinks className="hidden md:flex gap-8" />
    <NavActions />
  </div>
</nav>
```

---

### 4.3 `<HeroSection />`

**Purpose:** Instantly communicate what Glass Box is, to all three archetypes, without jargon. Drive one action: start trial or see demo.

**Layout:** Full viewport height (`min-h-screen`). Two-column on desktop (60/40 split): copy left, animated visual right. Single column on mobile with visual below copy.

**Background:** `bg-bg-base` with a subtle radial gradient glow centered behind the visual — `radial-gradient(ellipse 60% 50% at 70% 50%, rgba(56,139,253,0.08), transparent)`. Add a fine dot-grid pattern using CSS `background-image: radial-gradient(var(--border-subtle) 1px, transparent 1px); background-size: 24px 24px;` at 40% opacity for texture.

**Left Column — Copy:**

```
EYEBROW (text-xs uppercase tracking-widest text-brand-blue font-mono):
  "ICT-BASED · RULE-DRIVEN · FULLY TRANSPARENT"

H1 (Space Mono, text-5xl, text-text-primary, leading-tight):
  "Your Trading Rules.
   Zero Emotion.
   Every Trade Explained."

SUBHEADLINE (Geist, text-lg, text-text-secondary, max-w-md, mt-4):
  "Glass Box is an algorithmic trading engine that executes proven
   ICT setups across your broker accounts — automatically, consistently,
   and with complete visibility into every decision it makes."

MICRO-COPY (text-sm, text-text-muted, mt-2):
  "No AI guesswork. No black boxes. No surprises."

CTA ROW (mt-8, flex gap-4):
  Primary: <Button size="lg" className="bg-brand-blue text-white">
             Start Free Trial
           </Button>
  Secondary: <Button size="lg" variant="outline" className="border-border-muted">
               Watch Live Demo  →
             </Button>

TRUST MICRO (mt-6, flex items-center gap-2, text-xs text-text-muted):
  ✓ No credit card required  ·  ✓ Cancel anytime  ·  ✓ FTMO-ready config included
```

**Right Column — Animated Visual:**

This is not a screenshot. It is a **live-animated component** that simulates the Live Logic Feed. It should look like a terminal/feed panel pulled directly from the dashboard.

```jsx
// <HeroLiveFeed /> — animated simulation of the bot's thought process
// Auto-cycles through these messages with typewriter effect, one per ~2.5s:
const feedMessages = [
  { type: 'scan',    text: 'Scanning M15 for liquidity sweep above PDH...' },
  { type: 'detect',  text: 'Swept high confirmed at 1.08742 — highest sweep point locked' },
  { type: 'scan',    text: 'Price reversing below PDH — scanning for swing low...' },
  { type: 'detect',  text: 'MSS swing low identified at 1.08511' },
  { type: 'confirm', text: 'Price broke below swing low — MSS CONFIRMED ✓' },
  { type: 'detect',  text: 'Bearish FVG detected: 1.08490 → 1.08561' },
  { type: 'verdict', text: '⚡ VERDICT REACHED — SELL at 1.08490 · SL: 1.08762 · TP: 1.07980' },
  { type: 'exec',    text: 'Broadcasting to 54 accounts via Redis...' },
  { type: 'exec',    text: '54/54 orders filled · Avg latency: 18ms' },
];
```

Style the feed panel:
- Container: `bg-bg-surface border border-border-subtle rounded-xl p-4 font-mono text-xs`
- Header bar: `flex items-center gap-2 mb-3` with three colored dots (red #FF5F57, yellow #FEBC2E, green #28C840) at 10px each — macOS terminal aesthetic
- Each message line: `flex items-start gap-2 py-1`
- `type: 'scan'` → icon `⟳` in `text-text-muted`
- `type: 'detect'` → icon `◉` in `text-amber`
- `type: 'confirm'` → icon `✓` in `text-bull`
- `type: 'verdict'` → entire line in `text-brand-blue font-semibold`, with a subtle `bg-brand-glow` background on the row
- `type: 'exec'` → icon `⚡` in `text-brand-blue`
- Add a blinking cursor `|` at the end of the latest message

Below the feed panel, show a mini stat row:
```
┌─────────────────────────────────────────┐
│ 54 Accounts Active  ·  18ms Avg Latency │
│ 0 Halted  ·  Engine: RUNNING ●          │
└─────────────────────────────────────────┘
```
The green `●` pulses with a CSS animation (`opacity: 1 → 0.3, 1.5s infinite`).

---

### 4.4 `<TrustBar />`

**Purpose:** Quick credibility. Appears immediately below the hero.

**Layout:** Full-width strip, `bg-bg-surface border-y border-border-subtle py-4`. Horizontal flex row, centered, `gap-8 md:gap-16`, wraps on mobile.

**Items (5 items):**
```
[ ⬡ Built on ICT Methodology ]
[ 🔒 Azure Key Vault Security ]
[ ⚡ <20ms Execution Latency ]
[ 📊 FTMO / Prop Firm Ready ]
[ 👁 100% Trade Transparency ]
```

Each item: icon (Lucide) + label in `text-xs text-text-secondary uppercase tracking-wide`. Dividers between items (hidden on mobile).

---

### 4.5 `<WhatIsGlassBox />` — Problem → Solution

**Purpose:** Explain the product from first principles for Archetype 1 (complete beginner) while not boring Archetypes 2 & 3. Use plain language with progressive disclosure.

**Layout:** Two columns on desktop. Left = "The Problem" (dark card). Right = "The Glass Box Solution" (slightly elevated card with brand-blue left border).

**The Problem (left card):**
```
LABEL: "THE OLD WAY"  (text-xs uppercase text-text-muted)

H3: "Most trading bots are black boxes."

Body (text-sm text-text-secondary):
  You pay for a bot. It takes trades. You have no idea why.
  When it loses, you can't diagnose it. When it wins, you
  can't trust that it will keep winning. You're flying blind.

Pain points list (icon + text, each on its own line):
  ✗  "AI-powered" often means over-fitted to past data
  ✗  No explanation for entry or exit decisions
  ✗  No way to verify the logic matches the strategy
  ✗  Fails unpredictably in changing market conditions
```

**The Solution (right card):**
```
LABEL: "THE GLASS BOX WAY"  (text-xs uppercase text-brand-blue)

H3: "Every trade is a logical consequence — not a guess."

Body (text-sm text-text-secondary):
  Glass Box executes the Inner Circle Trader (ICT) methodology —
  a set of strict, proven rules about how institutional money moves
  in the market. Every trade follows the exact same checklist.
  Every decision is logged. Every outcome is explainable.

Proof points list (icon + text):
  ✓  Detects Fair Value Gaps (FVGs) using a precise 3-candle pattern
  ✓  Confirms Market Structure Shifts (MSS) with mathematical swing detection
  ✓  Only enters when ALL conditions are met — no exceptions
  ✓  Logs every condition flag for every trade — auditable forever
```

**Glossary tooltips:** Every bolded ICT term (FVG, MSS, ICT, swing low, etc.) should have a `<Tooltip>` from shadcn/ui with a plain-English definition:
- "FVG (Fair Value Gap): A price imbalance left behind when the market moves so fast there was no trading between two levels. Smart money tends to return to fill these gaps."
- "MSS (Market Structure Shift): The moment the market's direction definitively changes — identified by price breaking a specific swing point."
- "Swing Low: The lowest point of a recent price move before it reversed upward."

---

### 4.6 `<HowItWorks />` — 3-Step Visual Process

**Purpose:** Show the entire signal flow from market detection to execution in a way all three archetypes can follow.

**Layout:** Centered section, `py-24`. Title block centered above. Three steps in a horizontal row (or stacked vertically on mobile) connected by animated arrows.

**Section Header:**
```
Eyebrow: "THE PROCESS"
H2: "From Market Condition to Executed Order — in Under a Second"
Subtext: "The engine runs a strict checklist. If any condition fails, no trade is taken. Period."
```

**Step 1 — Market Scan:**
```
Icon:  A stylized candlestick chart icon (Lucide: `BarChart2`) in brand-blue
Title: "1. The Engine Scans"
Body:  "Every minute, Glass Box checks the forex market against
        a precise set of conditions. It identifies liquidity sweeps,
        detects Fair Value Gaps, and confirms Market Structure Shifts.
        This is the same analysis a professional ICT trader does manually —
        done by a machine, 24/5, without fatigue."
```

**Step 2 — The Verdict:**
```
Icon:  A checkmark inside a box (`CheckSquare`) in bull-green
Title: "2. A Verdict Is Reached"
Body:  "When ALL conditions are confirmed — and only then — the engine
        creates a Verdict: a snapshot of the exact entry price, stop loss,
        take profit, and every condition flag that triggered the trade.
        This is your complete audit trail, stored forever."
```

**Step 3 — Simultaneous Execution:**
```
Icon:  A lightning bolt (`Zap`) in amber
Title: "3. Your Accounts Execute"
Body:  "The Verdict is broadcast to your connected broker accounts
        via a millisecond-latency message bus. Each account computes
        its own lot size based on your personal risk settings, then
        places the order simultaneously. Average execution: under 20ms."
```

**Connector arrows:** Between each step, draw a horizontal arrow using an SVG or CSS pseudo-element. Animate the arrow with a moving dot traveling from left to right (`stroke-dashoffset` animation) to suggest live data flow.

---

### 4.7 `<GlassBoxFeature />` — The "Killer Feature" Visual Demo

**Purpose:** This is the highest-impact marketing section. It demonstrates the Visual Debugger / Trade Replay concept for Archetype 2 & 3, and makes Archetype 1 feel the visceral transparency of the product.

**Layout:** Dark full-width section (`bg-bg-surface`). Large section header. Below it: a large browser-chrome mock showing the dashboard's chart with overlays.

**Section Header:**
```
Eyebrow: "THE GLASS BOX FEATURE"
H2: "See Exactly What the Bot Sees"
Subtext: "Click any trade in your history. A panel opens showing
          the exact FVG it entered, the MSS level it confirmed,
          and every raw data point that triggered the Verdict.
          Not a summary. The actual data."
```

**The Mock Visual:**

Render a large (`rounded-2xl border border-border-subtle overflow-hidden`) browser-chrome container. Inside:

1. **Top bar:** Browser URL bar showing `app.glassbox.trade/dashboard` in monospaced text
2. **Chart area** (60% height): A simulated candlestick chart (use SVG or Canvas — do NOT use a real chart library here, it's a static illustration) showing:
   - ~30 candles in a bearish scenario
   - A shaded blue rectangle labeled "FVG Zone" between two price levels
   - A horizontal dashed red line labeled "MSS Level"
   - A downward arrow marker on the entry candle labeled "ENTRY"
   - A small green dot on the MSS candle labeled "MSS Confirmed ✓"
   - A shaded yellow zone near the top labeled "Sweep Point"
3. **Verdict Sidebar** (40% width, right side):
   ```
   VERDICT PANEL — SIGNAL #4821

   Direction:        SELL ▼
   Entry Price:      1.08490
   Stop Loss:        1.08762
   Take Profit:      1.07980
   Risk/Reward:      3.12R
   Scenario:         london_bearish

   ── ICT CONDITIONS ──────────────
   ✓  Swept High         1.08742
   ✓  MSS Swing Low      1.08511
   ✓  MSS Confirmed      Yes
   ✓  FVG Confirmed      Yes
   ✓  FVG Top            1.08561
   ✓  FVG Bottom         1.08490
   ✓  PDH                1.08690
   ✓  PDL                1.07910

   ── EXECUTION ───────────────────
   Accounts Fired:   54
   Avg Latency:      17ms
   Status:           FILLED ●
   ```
   Style each condition row: green check icon + label in `text-text-secondary` + value in `text-text-primary font-mono`.

Below the mock, add a caption:
```
"Every trade. Every condition. Every timestamp. Stored and visible to you — always."
```

---

### 4.8 `<PropFirmSection />`

**Purpose:** Direct conversion section for Archetype 3. This should feel like it was built specifically for them.

**Layout:** Two columns. Left: copy. Right: the Prop Firm Constraints Panel (pulled from the actual dashboard design — see §6.6).

**Copy (left):**
```
Eyebrow: "PROP FIRM READY"
H2: "Built for FTMO. Built for Discipline."
Body:
  "Prop firm challenges have one rule above all others:
   don't blow the account with a bad day.

   Glass Box hard-codes your prop firm's risk rules directly
   into the engine. Your daily drawdown limit is enforced by
   the bot — not by your willpower at 2am.

   If the daily loss threshold is hit, the engine halts
   automatically. No new trades. Your existing positions
   run to their stop loss or take profit naturally.
   Then it resets the next day."

Bullet points:
  ✓ Configurable daily drawdown limit (e.g. 4% for FTMO Phase 1)
  ✓ Automatic halt when limit is reached — no manual intervention needed
  ✓ Per-account risk sizing (risk what you configure, not a fixed global amount)
  ✓ Consistent execution — no emotional over-trading, no revenge trades
  ✓ Full audit trail for prop firm review if ever requested
```

**Right panel:** Render a static/animated version of the Prop Firm Constraints widget (see §6.6 for full spec). This should look like a real widget pulled from the app.

---

### 4.9 `<PricingSection />`

**Layout:** Centered, three cards side by side on desktop, stacked on mobile.

**Plans:**

```
┌──────────────────┐  ┌──────────────────────────┐  ┌──────────────────┐
│    STARTER       │  │       PRO  ← POPULAR      │  │   ENTERPRISE     │
│                  │  │  (border: brand-blue)      │  │                  │
│  $49 / month     │  │       $99 / month          │  │  Contact Us      │
│                  │  │                            │  │                  │
│  1 broker acct   │  │  Up to 10 broker accounts  │  │  50+ accounts    │
│  Live signals    │  │  Live signals              │  │  Custom config   │
│  Glass Box feed  │  │  Glass Box feed            │  │  SLA support     │
│  Basic analytics │  │  Full Visual Debugger      │  │  Dedicated VM    │
│                  │  │  Prop Firm Constraints Panel│  │  Priority exec   │
│  [Get Started]   │  │  Trade Replay              │  │  [Contact Sales] │
│                  │  │  Priority execution         │  │                  │
│                  │  │  [Start Free Trial]        │  │                  │
└──────────────────┘  └──────────────────────────┘  └──────────────────┘
```

The PRO card should have: `border-brand-blue bg-bg-elevated` + a `MOST POPULAR` badge at the top in `bg-brand-blue text-white text-xs px-3 py-1 rounded-full`.

Below the cards:
```
"All plans include a 14-day free trial. No credit card required.
 Cancel anytime. FTMO-ready configuration guide included with every plan."
```

---

### 4.10 `<FAQSection />`

Use shadcn/ui `Accordion` component. Target these specific objections:

```
Q: "I know nothing about trading. Can I still use this?"
A: "Yes. Glass Box handles all the analysis and execution. You don't need to
    know what an FVG or MSS is to benefit from the system. However, the
    transparency features mean you can learn what the bot is doing over
    time — and see exactly why every trade was taken."

Q: "How is this different from AI trading bots?"
A: "AI bots are probabilistic — they guess based on patterns in historical data.
    Glass Box is deterministic — it follows a fixed, auditable ruleset derived
    from the ICT methodology. There's no machine learning involved. The same
    conditions will always produce the same trade decision. You can verify that."

Q: "What if I'm trying to pass an FTMO challenge?"
A: "Glass Box is built with prop firm traders in mind. You set your daily drawdown
    limit, and the engine enforces it. When the limit is hit, it stops taking
    trades for the rest of the day — automatically. This removes the single biggest
    reason prop firm attempts fail: emotional override of risk rules."

Q: "What broker accounts does it support?"
A: "Glass Box connects to MetaTrader 5 (MT5) accounts. Most major forex brokers
    support MT5. You connect your account credentials securely — they are stored
    in Azure Key Vault and never exposed in plaintext to anyone, including our team."

Q: "Can I see the bot's logic before it trades?"
A: "Yes. The Live Logic Feed in the dashboard streams the bot's thought process
    in real-time — before, during, and after each trade. The Visual Debugger
    shows the exact chart conditions (FVG zones, MSS levels, sweep points) that
    triggered each Verdict. Everything is visible."

Q: "What if the bot makes a loss?"
A: "The ICT methodology, like any strategy, has losing trades. Glass Box does not
    guarantee profit. What it guarantees is that every trade follows the exact same
    disciplined rules — and that you have a complete record of every decision. Risk
    management is built in: your stop loss is always calculated before the trade is
    taken, and your daily drawdown limit is enforced automatically."
```

---

### 4.11 `<Footer />`

Three columns: Brand (logo + one-line description + socials), Links (Product, Company, Legal), Contact.

Bottom strip: `© 2025 Glass Box Trading Engine. Not financial advice. Trading forex carries risk.`

---

## 5. Authentication Flow (Clerk)

**Routes:**
- `/sign-in` — Clerk's `<SignIn />` component, centered on page, `bg-bg-base`
- `/sign-up` — Clerk's `<SignUp />` component, same treatment

**Wrapper styling:** Override Clerk's appearance with their `appearance` prop:
```jsx
<SignIn appearance={{
  baseTheme: dark, // import { dark } from '@clerk/themes'
  variables: {
    colorBackground:     '#0D1117',
    colorInputBackground:'#161B22',
    colorText:           '#E6EDF3',
    colorPrimary:        '#388BFD',
    borderRadius:        '8px',
  }
}} />
```

**Post-auth redirect:** `/dashboard`

**Protected routes:** Wrap all `/dashboard/*` routes with Clerk's `<SignedIn>` or middleware. Unauthenticated users hitting `/dashboard` redirect to `/sign-in`.

---

## 6. Dashboard Application

### 6.1 Layout Shell

```
┌────────────────────────────────────────────────────────────────┐
│  <TopBar />  (h-14, sticky, bg-bg-surface, border-b)          │
├──────────────┬─────────────────────────────────────────────────┤
│              │                                                  │
│  <Sidebar /> │  <MainContent />                                │
│  (w-60,      │  (flex-1, overflow-y-auto, p-6)                │
│   fixed,     │                                                  │
│   h-screen)  │                                                  │
│              │                                                  │
└──────────────┴─────────────────────────────────────────────────┘
```

**`<TopBar />`:**
- Left: Hamburger (mobile only) + current page title
- Center: Engine status pill → `● ENGINE RUNNING` in bull-green or `● HALTED` in bear-red or `● PAUSED` in amber — pulse animation on the dot
- Right: Notifications bell + Clerk `<UserButton />`

**`<Sidebar />`:**
```
Logo block (p-4, border-b border-border-subtle):
  ⬡ GLASS BOX

Nav items (mt-2):
  [LayoutDashboard]  Overview          /dashboard
  [Activity]         Live Feed         /dashboard/feed
  [TrendingUp]       Chart Debugger    /dashboard/chart
  [List]             Trade History     /dashboard/trades
  [Shield]           Prop Firm Panel   /dashboard/propfirm
  [Settings]         Account Settings  /dashboard/settings

Bottom of sidebar:
  [HelpCircle] Documentation
  [LogOut]     Sign Out
```

Active nav item: `bg-bg-elevated border-l-2 border-brand-blue text-text-primary`. Inactive: `text-text-secondary hover:text-text-primary hover:bg-bg-elevated`.

---

### 6.2 `/dashboard` — Overview Page

**Purpose:** The command center. Highest-density page. At a glance: engine status, today's performance, active positions, recent signals.

**Layout:** CSS grid, responsive:
```
Desktop (>1280px):
  Row 1: [Engine Status] [Today P&L] [Active Positions] [Win Rate]   — 4 stat cards
  Row 2: [Live Logic Feed — 60%] [Prop Firm Panel — 40%]
  Row 3: [Recent Signals Table — 100%]

Tablet (768–1280px):
  Row 1: 2x2 stat grid
  Row 2: Feed full-width, PropFirm below
  Row 3: Signals table

Mobile:
  Stacked single column
```

---

### 6.3 Stat Cards (Row 1)

Four cards, each:
```
bg-bg-surface border border-border-subtle rounded-lg p-4

┌─────────────────────────┐
│ LABEL (text-xs uppercase│
│ text-text-muted)        │
│                         │
│ VALUE (text-3xl         │
│ font-mono font-bold     │
│ text-text-primary)      │
│                         │
│ CHANGE (text-xs         │
│ text-bull or text-bear) │
│ ↑ +2.3% vs yesterday   │
└─────────────────────────┘
```

**Card 1 — Engine Status:**
- Label: `ENGINE STATUS`
- Value: `RUNNING` / `HALTED` / `SCANNING`
- Large colored badge + pulsing dot
- Sub: `Uptime: 99.7% · 54 workers active`

**Card 2 — Today's P&L:**
- Label: `TODAY'S P&L`
- Value: `+$482.30` in bull-green or `-$120.00` in bear-red
- Sub: `Across 54 accounts · 3 trades`
- Note: This is aggregate P&L across all user accounts

**Card 3 — Active Positions:**
- Label: `OPEN POSITIONS`
- Value: `3`
- Sub-row: `2 in profit · 1 at breakeven`
- Each sub-item has a tiny colored dot (bull / breakeven)

**Card 4 — Monthly Win Rate:**
- Label: `WIN RATE · THIS MONTH`
- Value: `68.4%`
- Sub: `23W / 10L · 33 trades`
- A thin horizontal progress bar below the value: `bg-bull` fill on `bg-bg-elevated` track

**Real-time behavior:** All four cards subscribe to Supabase realtime on the `executions` and `signals` tables. When an event fires, apply the `data-updated` flash animation to the changed card.

---

### 6.4 `<LiveLogicFeed />` — Streaming Component

**Purpose:** Show the bot's internal thought process as it happens. The most unique feature of the product. This component alone differentiates Glass Box from every competitor.

**Data source:** Subscribe to `execution_events` table via `supabase.channel('events').on('postgres_changes', ...)`. Also manually emit structured log lines from the ICT engine (via a dedicated `log_events` table or via the `execution_events.detail` JSONB field with an `event_type: 'engine_log'`).

**Visual Design:**

```
┌─ LIVE LOGIC FEED ───────────────────────── ● LIVE ─────────────────┐
│                                                                      │
│  10:24:31  ⟳  Scanning M15 for liquidity sweep above PDH...        │
│  10:24:32  ◉  PDH captured: 1.08690 · PDL: 1.07910                 │
│  10:24:45  ◉  Price surpassed PDH — swept_high = True at 1.08742   │
│  10:24:51  ⟳  Price reversing below PDH — scanning swing lows...   │
│  10:24:52  ✓  MSS swing low identified: 1.08511                     │
│  10:24:58  ✓  Price broke below swing low — MSS CONFIRMED          │
│  10:24:59  ✓  Bearish FVG detected: bottom=1.08490, top=1.08561    │
│  10:25:00  ⚡  VERDICT: SELL · Entry=1.08490 · SL=1.08762 · TP=... │
│  10:25:00  ⚡  Broadcasting to 54 accounts...                       │
│  10:25:01  ✓  54/54 accounts filled · Avg latency: 17ms            │
│                                                                 [▼] │
└──────────────────────────────────────────────────────────────────────┘
```

Implementation notes:
- Fixed height container (`h-80`), `overflow-y-auto`, auto-scroll to bottom on new messages
- `[▼]` button in bottom-right: pauses auto-scroll so user can read history, reactivates on scroll-to-bottom
- Each line is a `<FeedLine>` component with: `timestamp` (font-mono text-text-muted), `icon` (colored per type), `message` (text-text-secondary with key terms bolded/colored)
- Verdict lines (`type: verdict`): full row gets `bg-brand-glow rounded` background highlight
- Halt lines (`type: drawdown_halt`): full row gets `bg-bear-dim rounded` + icon ⛔ in bear-red
- Breakeven lines (`type: breakeven_moved`): icon ↗ in `text-breakeven` (indigo)
- Messages cap at last 200 lines to avoid memory issues; older lines drop off the top
- Include a `PAUSED` banner overlay when feed is paused, with a `Resume →` button

**Copy guidance for message formats (these come from the backend — the frontend just renders them):**
```
scan:     "Scanning {timeframe} for {condition}..."
detect:   "{condition} {result_description} at {value}"
confirm:  "{condition} CONFIRMED ✓ — {details}"
verdict:  "VERDICT: {direction} · Entry={price} · SL={price} · TP={price} · RR={rr}R · Scenario={tag}"
exec:     "{n}/{total} accounts filled · Avg latency: {ms}ms"
halt:     "DRAWDOWN HALT triggered — Loss: {pct}% ≥ limit {limit}% — Engine halted for today"
breakeven:"BREAKEVEN MOVED · Account {id} · Ticket {ticket} · SL {old} → {new}"
error:    "ERROR: {message} · Account {id}"
```

---

### 6.5 `/dashboard/chart` — Visual Debugger (Glass Box Feature)

**Purpose:** The centerpiece product feature. A TradingView-style chart with ICT logic overlays. Users can click any historical signal and see the exact chart state at the moment of the Verdict.

**Library:** Use `lightweight-charts` (npm: `lightweight-charts`) by TradingView. It is free, MIT-licensed, and renders professional-grade candlestick charts in React.

**Layout:** Full-width main content area.
```
┌── Symbol Selector ── Timeframe ── Date Range ──────── [▶ Live] ──────┐
│                                                                        │
│   CANDLESTICK CHART AREA (h-[500px])                                  │
│   With overlays:                                                       │
│   - FVG rectangles (semi-transparent fills)                            │
│   - MSS level horizontal line                                          │
│   - Sweep point horizontal line                                        │
│   - Entry marker (arrow annotation)                                    │
│   - SL / TP levels (dashed horizontal lines)                           │
│                                                                        │
├─────────────────────────────────────────────────────────────────────── │
│                                                                        │
│   TRADE HISTORY LIST (below chart)                                     │
│   Click a row → opens Verdict Sidebar, chart rewinds to that trade     │
│                                                                        │
└────────────────────────────────────────────────────────────────────────┘
```

**Chart configuration:**
```js
const chart = createChart(containerRef.current, {
  layout: {
    background: { color: '#0D1117' },
    textColor:  '#8B949E',
  },
  grid: {
    vertLines: { color: '#21262D' },
    horzLines: { color: '#21262D' },
  },
  crosshair: { mode: CrosshairMode.Normal },
  rightPriceScale: { borderColor: '#21262D' },
  timeScale: { borderColor: '#21262D', timeVisible: true },
});
```

**ICT Overlays — implementation:**

```js
// FVG Rectangle (bearish)
// Use ISeriesApi<'Line'> trick or custom primitives
// Render as a semi-transparent rectangle between fvg_bottom and fvg_top
// over the time range of detection
chart.addPriceLine({
  price: signal.fvg_top,
  color: '#F8514980',    // bear-red at 50% opacity
  lineWidth: 1,
  lineStyle: LineStyle.Solid,
  title: 'FVG Top',
});
chart.addPriceLine({
  price: signal.fvg_bottom,
  color: '#F8514980',
  lineWidth: 1,
  lineStyle: LineStyle.Dashed,
  title: 'FVG Bottom',
});
// For shaded FVG area: use a custom series or overlay canvas element

// MSS Level
chart.addPriceLine({
  price: signal.mss_level,
  color: '#D29922',
  lineWidth: 1,
  lineStyle: LineStyle.Dotted,
  title: 'MSS Level',
});

// Sweep Point
chart.addPriceLine({
  price: signal.sweep_point,
  color: '#388BFD',
  lineWidth: 1,
  lineStyle: LineStyle.Dotted,
  title: 'Sweep',
});

// SL and TP
chart.addPriceLine({ price: signal.sl_price, color: '#F85149', title: 'SL' });
chart.addPriceLine({ price: signal.tp_price, color: '#3FB950', title: 'TP' });
```

**Trade Replay Slider:**

Below the chart, render a `<input type="range" />` (styled with Tailwind) that controls a `replayTimestamp` state value. As the slider moves:
1. The chart's visible time range shifts to center around the selected timestamp
2. Overlays update to show only the conditions that were known at that moment (based on `created_at` of each signal event)
3. The Verdict Sidebar populates with the signal data for the trade nearest to that timestamp

Style the slider: `accent-color: var(--brand-blue)`, full-width, with tick marks below for each trade in the current date range.

**`<VerdictSidebar />`:**

Slides in from the right (`translate-x-full → translate-x-0`, 300ms ease-out) when a trade is selected. Width: `w-80`. Backdrop: none (it overlays the chart partially).

```
┌─ VERDICT ───────────── #4821 ── [✕] ─┐
│                                       │
│  SELL ▼ london_bearish                │
│  EURUSD · 23 Jan 2025 · 10:25:00 WAT │
│                                       │
│  ─── PRICE LEVELS ─────────────────  │
│  Entry:       1.08490  (font-mono)    │
│  Stop Loss:   1.08762  text-bear      │
│  Take Profit: 1.07980  text-bull      │
│  Risk:        27.2 pips               │
│  Reward:      85.1 pips               │
│  R:R Ratio:   3.12R    text-brand     │
│                                       │
│  ─── ICT CONDITIONS ───────────────  │
│  swept_high    ✓  1.08742            │
│  swept_low     –  –                  │
│  mss_confirmed ✓  Yes                │
│  fvg_confirmed ✓  Yes                │
│  fvg_top       ✓  1.08561            │
│  fvg_bottom    ✓  1.08490            │
│  mss_level     ✓  1.08511            │
│  sweep_point   ✓  1.08742            │
│  pdh           ✓  1.08690            │
│  pdl           ✓  1.07910            │
│                                       │
│  ─── EXECUTION ────────────────────  │
│  Accounts Fired: 54                   │
│  Avg Latency:    17ms                 │
│  Status:         FILLED               │
│  Execute At:     10:25:00.847 WAT     │
│                                       │
│  ─── YOUR ACCOUNT ─────────────────  │
│  Lot Size:   0.23                     │
│  Fill Price: 1.08493                  │
│  Actual SL:  1.08762                  │
│  Actual TP:  1.07980                  │
│  Status:     FILLED ●                 │
│  Latency:    18ms                     │
│                                       │
└───────────────────────────────────────┘
```

For `–` conditions (conditions that were false for this trade): show a muted dash, not a ✗ — it's not an error, it's just not applicable to this scenario.

---

### 6.6 Prop Firm Constraints Panel (`<PropFirmPanel />`)

Used on both the dashboard overview page (as a card) and the `/dashboard/propfirm` dedicated page (expanded).

**Card version (overview page):**

```
┌─ PROP FIRM CONSTRAINTS ─────────────────────────────────────────┐
│                                                                   │
│  DAILY DRAWDOWN                                                   │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━░░░░░░░░  72% remaining        │
│  Used: $280 of $1,000 limit    Resets in: 14h 22m               │
│                                                                   │
│  WIN RATE · THIS MONTH                                            │
│  68.4%  ·  23W / 10L                                             │
│                                                                   │
│  CONSECUTIVE LOSSES                                               │
│  ● 0  (Max allowed: 3)                                            │
│                                                                   │
│  ENGINE STATUS                                                     │
│  ● ACTIVE — No halt conditions met                                │
│                                                                   │
└───────────────────────────────────────────────────────────────────┘
```

**Daily Drawdown Bar:**
- Track: `bg-bg-elevated h-2 rounded-full`
- Fill: dynamic color based on remaining percentage:
  - >60% remaining → `bg-bull` (green)
  - 30–60% remaining → `bg-amber` (yellow)
  - <30% remaining → `bg-bear` (red) with a pulsing animation
- Show the actual dollar amount used and the limit
- Show time until reset (next UTC midnight)

**Consecutive Losses:**
- Render as dots: `●` for each loss, `○` for remaining slots
  - e.g., 1 loss, max 3: `● ○ ○`
  - At max (3/3): all dots in bear-red, add warning badge "CAUTION"
  - When halted: icon changes to ⛔, full row in `bg-bear-dim`

**Dedicated `/dashboard/propfirm` page:**
Expand the card into a full page with:
- Same widgets, larger
- A table of "Today's trades vs limit" — did each trade respect the daily drawdown at the time it was taken?
- A "Simulation" tool: let the user set hypothetical loss values and see how many trades they can take before the halt triggers
- Config settings for their specific prop firm: Daily Loss Limit ($), Max Trailing Drawdown ($), Profit Target ($), Min Trading Days

---

### 6.7 `/dashboard/trades` — Trade History

**Layout:** Full-width data table.

**Filters (top bar):** Date range picker, Direction (All / BUY / SELL), Scenario (All / london_bearish / london_bullish / ny_continuation_bearish / ...), Status (All / Filled / Rejected / Error).

**Table columns:**
```
│ Time (WAT)  │ Symbol │ Direction │ Entry    │ SL       │ TP       │ R:R  │ Status   │ Scenario           │ Actions │
│ Jan 23 10:25│ EURUSD │ SELL ▼    │ 1.08490  │ 1.08762  │ 1.07980  │ 3.1R │ FILLED ● │ london_bearish     │ [View]  │
```

- Direction cell: `SELL ▼` in bear-red / `BUY ▲` in bull-green with shape indicator (not just color)
- Status cell: `FILLED ●` green / `REJECTED ✗` red / `ERROR ⚠` amber / `PENDING ◌` muted
- Scenario cell: render as a badge/chip — `bg-bg-elevated text-xs rounded-full px-2 py-0.5`
- `[View]` button: opens the Verdict Sidebar and navigates to the Chart Debugger with that trade pre-selected

**Pagination:** 25 rows per page. shadcn/ui `<Pagination />`.

**Export:** `[Export CSV]` button in top-right — exports filtered results.

---

### 6.8 `/dashboard/settings` — Account Settings

**Three sub-tabs** (shadcn/ui `<Tabs />`):

**Tab 1: Broker Accounts**
- Table of connected broker accounts
- Columns: Account Number, Broker/Server, Symbol, Status, Last Heartbeat, Risk Amount, Actions
- `[Add Account]` button: opens a modal with fields:
  - Account Number (text input)
  - Server (text input, e.g. `ICMarkets-Demo01`)
  - Symbol (text input, default `EURUSD`)
  - Risk Amount (number input) + Risk Currency (USD/GBP/EUR dropdown)
  - R:R Ratio (number input, default 2.0)
  - Breakeven Buffer Ticks (number input, default 10)
  - Max Daily Drawdown % (number input, default 2.0)
  - Terminal Path (text input — for advanced users)
- Status badges mirror `broker_accounts.status`: `pending` → amber, `ready` → green, `halted` → red, `error` → red with ⚠

**Tab 2: Risk Configuration**
- Global defaults that pre-fill the Add Account form
- Explanation tooltip on each field, in plain English (see §7 for copy)

**Tab 3: Profile & Security**
- Clerk's `<UserProfile />` component for email, password, 2FA
- No custom fields needed here — delegate fully to Clerk

---

## 7. Copy & Tone Guide

### Voice Principles

**Authoritative but not arrogant.** This is a system built on rules and precision. The copy should reflect that — confident, clear, specific. No hyperbole, no promises of returns, no "revolutionary AI."

**Transparent by default.** Every feature description should answer the question "but how does it actually work?" — because that's what the brand promises.

**Plain first, technical second.** Every technical concept is introduced with a plain-English sentence, followed (if needed) by the precise term. Not the other way around.

**Tone by section:**
- Hero & marketing: bold, direct, benefit-led. Short sentences.
- FAQ: empathetic, honest. Acknowledge the real fear before answering it.
- Dashboard UI: functional, minimal. Labels not slogans. Status not adjectives.
- Error states: calm, specific, actionable. "Worker 54 lost connection to Redis — attempting reconnect (attempt 2/5)" not "Something went wrong."

### Jargon Glossary (always use tooltips on first use per page)

| Term | Tooltip copy |
|---|---|
| FVG (Fair Value Gap) | A price gap where the market moved so fast that buyers and sellers never fully traded at those levels. Smart money tends to return to "fill" these gaps. |
| MSS (Market Structure Shift) | The moment the market definitively changes direction — detected when price breaks a specific previous swing point. |
| ICT Methodology | Inner Circle Trader — a set of rules for reading how institutional banks and funds move in the market, and trading alongside them. |
| PDH / PDL | Previous Day High / Low — the highest and lowest prices from the prior trading session. Key reference levels for the engine. |
| Sweep Point | The price level where the market swept past a key high or low, triggering stop orders from retail traders, before reversing. |
| R:R Ratio | Risk to Reward ratio. A 3R trade means for every $1 risked, the target is $3 in profit. |
| Lot Size | The position size in forex — determines how much money you make or lose per pip of price movement. Calculated automatically per account. |
| Verdict | Glass Box's internal name for a completed trade signal — a snapshot of every condition that triggered the trade, stored permanently. |
| Worker | The background process that handles one broker account — connects to MT5, receives signals, computes lot size, places orders. |
| Breakeven | Moving your stop loss to your entry price after the trade moves in your favor — meaning you can no longer lose on that trade. |
| Drawdown Halt | An automatic mechanism that stops the engine from taking new trades when daily losses exceed a configured limit. |

---

## 8. Accessibility Requirements

- **Color + Shape, never color alone:** All status indicators must use both a color and a symbol/icon/shape. Example: FILLED must show `●` in green AND the word "FILLED" — not just a green dot.
- **Contrast ratios:** All text must meet WCAG AA minimum (4.5:1 for normal text, 3:1 for large text). With the specified dark theme and text colors, this is met — do not reduce text opacity below `text-text-secondary`.
- **Focus states:** All interactive elements must have visible focus rings. Use `focus-visible:ring-2 focus-visible:ring-brand-blue focus-visible:ring-offset-2 focus-visible:ring-offset-bg-base`.
- **Keyboard navigation:** Chart controls, sliders, and data tables must be fully keyboard-navigable.
- **ARIA labels:** All icon-only buttons must have `aria-label`. The Live Logic Feed must have `role="log" aria-live="polite" aria-atomic="false"`.
- **Tooltips:** Must be triggerable by keyboard focus, not just hover.
- **Reduced motion:** Wrap all animations in `@media (prefers-reduced-motion: reduce)` — replace transitions with instant state changes.

---

## 9. Real-Time Architecture (Frontend)

### Supabase Realtime Subscriptions

Set up a single `RealtimeProvider` context at the app root that manages all subscriptions:

```js
// subscriptions to set up after Clerk auth is confirmed:

// 1. New signals (Verdict broadcast)
supabase.channel('signals')
  .on('postgres_changes', {
    event: 'INSERT',
    schema: 'public',
    table: 'signals'
  }, (payload) => dispatch({ type: 'NEW_SIGNAL', signal: payload.new }))
  .subscribe();

// 2. Execution status updates (per-account order lifecycle)
supabase.channel('executions')
  .on('postgres_changes', {
    event: 'UPDATE',
    schema: 'public',
    table: 'executions',
    filter: `account_id=in.(${userAccountIds.join(',')})`
  }, (payload) => dispatch({ type: 'EXECUTION_UPDATE', execution: payload.new }))
  .subscribe();

// 3. Execution events (Live Logic Feed)
supabase.channel('execution_events')
  .on('postgres_changes', {
    event: 'INSERT',
    schema: 'public',
    table: 'execution_events'
  }, (payload) => dispatch({ type: 'NEW_EVENT', event: payload.new }))
  .subscribe();

// 4. Broker account status changes (worker health, halt events)
supabase.channel('broker_accounts')
  .on('postgres_changes', {
    event: 'UPDATE',
    schema: 'public',
    table: 'broker_accounts',
    filter: `user_id=eq.${userId}`
  }, (payload) => dispatch({ type: 'ACCOUNT_UPDATE', account: payload.new }))
  .subscribe();
```

### Polling (for non-critical metrics)

Poll every 30 seconds:
- Aggregate P&L across accounts
- Daily drawdown totals (derived from executions table)
- Worker heartbeat timestamps (to show "Last seen: 30s ago" etc.)

### Data Flow to Components

```
RealtimeProvider (context)
  ↓
useSignals()          → <LiveLogicFeed />, <StatCards />
useExecutions()       → <TradeHistory />, <VerdictSidebar />
useAccountStatus()    → <TopBar engine pill>, <PropFirmPanel />
useExecutionEvents()  → <LiveLogicFeed />
```

---

## 10. Responsive Behavior

| Breakpoint | Behavior |
|---|---|
| Mobile (<768px) | Single column. Sidebar collapses to bottom nav bar (5 icons). Chart is full-width, no sidebar panel. Live Feed is accessible via tab. |
| Tablet (768–1280px) | 2-column grids. Sidebar overlays (hamburger). Chart + Verdict in stacked layout. |
| Desktop (>1280px) | Full layout as specified. Fixed sidebar. Chart + Verdict side-by-side. |

Mobile alert optimization: On mobile, push notifications (via browser Push API or Clerk webhooks to email/SMS) for:
- New Verdict broadcast
- Drawdown Halt triggered
- Worker down (heartbeat expired)

---

## 11. Page Routes Summary

```
/                          → Landing page (public)
/sign-in                   → Clerk SignIn (public)
/sign-up                   → Clerk SignUp (public)
/dashboard                 → Overview (protected)
/dashboard/feed            → Live Logic Feed — expanded (protected)
/dashboard/chart           → Visual Debugger + Trade Replay (protected)
/dashboard/trades          → Trade History table (protected)
/dashboard/propfirm        → Prop Firm Panel — full page (protected)
/dashboard/settings        → Account Settings (protected)
/dashboard/settings/accounts → Broker account management
/dashboard/settings/risk   → Risk configuration
```

---

## 12. Component Inventory (Build in This Order)

**Phase 1 — Foundation:**
1. `tailwind.config.js` — full color system and font config
2. `globals.css` — CSS variables, keyframes, base typography
3. `<Layout />` — sidebar + topbar shell with Clerk auth
4. `<StatCard />` — reusable stat card with flash animation
5. `<Badge />` — status badge (extends shadcn Badge) with shape variants

**Phase 2 — Marketing:**
6. `<NavBar />` — scroll-aware, with mobile drawer
7. `<HeroSection />` — copy + `<HeroLiveFeed />` animated terminal
8. `<TrustBar />` — 5-item strip
9. `<WhatIsGlassBox />` — 2-column problem/solution
10. `<HowItWorks />` — 3-step with animated connectors
11. `<GlassBoxFeature />` — browser mock with chart illustration + Verdict panel
12. `<PropFirmSection />` — copy + static prop firm widget
13. `<PricingSection />` — 3 cards
14. `<FAQSection />` — shadcn Accordion
15. `<Footer />`

**Phase 3 — Dashboard Core:**
16. `<LiveLogicFeed />` — Supabase realtime, auto-scroll, pause/resume
17. `<PropFirmPanel />` — drawdown bar, consecutive losses, win rate
18. `<OverviewPage />` — assembles stat cards + feed + prop firm panel

**Phase 4 — Chart & Trade Data:**
19. `<CandlestickChart />` — lightweight-charts wrapper with ICT overlays
20. `<VerdictSidebar />` — slide-in panel with all signal fields
21. `<ReplaySlider />` — time-scrub control
22. `<ChartDebuggerPage />` — assembles chart + sidebar + slider
23. `<TradeHistoryTable />` — full trade log with filters

**Phase 5 — Settings & Polish:**
24. `<AccountSettingsPage />` — three-tab settings with Clerk profile
25. `<AddAccountModal />` — broker account form with all fields
26. Error states, empty states, loading skeletons for all pages
27. Mobile responsive pass — bottom nav, collapsed layouts
28. Accessibility audit — focus rings, ARIA, reduced motion

---

## 13. Empty States & Error States

Every data-dependent component must handle three states:

**Loading:** Use `<Skeleton />` from shadcn/ui — match the skeleton shape to the actual content shape.

**Empty:**
```
[Icon — muted, large]
Title: "No trades yet"
Body:  "The engine will log trades here as signals are detected and executed."
```
Do not show empty table headers with no rows. Show the empty state full-bleed.

**Error:**
```
[AlertCircle icon — bear-red]
Title: "Could not load trade data"
Body:  "Check your connection or try refreshing. If this persists, contact support."
[Retry button]
```

---

## 14. Final Notes for the Agent

1. **Do not hallucinate financial data.** All displayed numbers must come from real Supabase queries or be clearly labeled as mock/demo data during development. No hardcoded P&L or win rates in production code.

2. **The Verdict Sidebar is the product.** More effort should go into making this panel feel precise and authoritative than any other single component. It is the embodiment of the brand promise.

3. **The Live Logic Feed is the hook.** First-time users will spend minutes watching it. Make every message line readable, make the verdict line unmissable, and make the halt line feel appropriately serious.

4. **Every ICT term on the marketing site needs a tooltip.** No exceptions. Archetype 1 should not feel excluded from any section of the landing page.

5. **The prop firm panel is a trust signal for Archetype 3.** When they see the drawdown bar and the consecutive loss counter, they should immediately think "this was built by someone who has actually tried to pass an FTMO challenge."

6. **Dark theme is the default and the only theme.** No light theme toggle is needed in v1.

7. **Never show raw UUIDs to users.** Signal IDs, account IDs, execution IDs — show the last 6 characters prefixed with `#`. e.g., signal_id `a3f92b...4e21` → `#4E21`.

8. **Timestamps always in WAT (UTC+1).** Label them explicitly: `10:25:00 WAT`. Never show raw UTC without conversion.

---

*Glass Box Frontend Design Guide · v1.0 · For AI Agent Execution*
*Stack: React · Tailwind CSS · shadcn/ui · lightweight-charts · Clerk · Supabase Realtime*
