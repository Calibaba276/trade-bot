# Glass Box — Product Overview

> *"Your Trading Rules. Zero Emotion. Every Trade Explained."*

---

## What Is Glass Box?

Glass Box is a fully automated algorithmic forex trading engine paired with a real-time transparency dashboard. It connects to your MetaTrader 5 (MT5) broker account, scans the market continuously, and executes trades — all based on a strict, verifiable set of rules drawn from the ICT (Inner Circle Trader) institutional trading methodology.

The name says it all: where most automated trading systems are a "black box" that you have to trust blindly, Glass Box shows you everything. Every pattern it detected. Every reason it entered. Every condition it waited for before pulling the trigger.

You don't have to take our word for it. You can watch it happen in real-time, or scrub back through any past session and audit every single decision, candle by candle.

---

## The Problem We Solve

Most retail traders face one of three problems:

1. **They trade manually and lose to emotion.** They know the rules but can't follow them consistently under pressure.
2. **They buy an automated bot and have no idea what it's doing.** When it loses, they can't tell if the strategy broke or if it's just a natural drawdown.
3. **They're attempting prop firm challenges (FTMO, etc.) and can't afford an emotional mistake.** One bad trade that violates a drawdown rule can fail the whole challenge.

Glass Box addresses all three. The bot handles execution so emotion is removed entirely. The dashboard gives you full visibility so you're never guessing. And the built-in risk engine is designed from the ground up to respect prop firm rules automatically.

---

## How It Works

### Step 1 — Scan
Every minute during the London and New York trading sessions, the Glass Box strategy engine scans price action across your selected forex pairs. It looks for a specific sequence of institutional patterns:

- **FVG (Fair Value Gap):** A three-candle price imbalance indicating where smart money entered the market
- **MSS (Market Structure Shift):** A breakout of a prior swing point, signaling a change in directional intent
- **OB (Order Block):** A price zone where large institutional orders were previously placed
- **BOS (Break of Structure):** Confirmation that the prior swing high or low has been decisively broken

These aren't arbitrary indicators. They're the same concepts that institutional traders use to identify high-probability entry zones.

### Step 2 — Verdict
When all required conditions align, the engine issues a **Verdict** — a complete trade signal that includes:

- Entry price
- Stop loss level (based on the structural swing point)
- Take profit target (3× risk by default, configurable)
- Risk-reward ratio
- Scenario tag (e.g., `london_bearish`, `ny_continuation_bullish`)
- A full checklist of every ICT condition that was satisfied

Nothing is hidden. Every verdict is stored and accessible on your dashboard.

### Step 3 — Execute
The verdict is broadcast in under 20 milliseconds to your connected MT5 broker account(s). Position size is calculated automatically based on your configured risk amount. Once in a trade, the engine monitors it in the background — moving your stop loss to breakeven when the position reaches a defined profit threshold, and halting new trades entirely if your daily drawdown limit is hit.

---

## The Dashboard

The Glass Box dashboard is where you interact with everything the bot is doing.

### Live Mode
Watch the market in real-time. As new candles form and the strategy detects patterns, they appear on the chart immediately — FVG zones, MSS lines, order blocks, entry and exit markers. The event log on the right updates live with every new detection. You are watching the bot's thought process as it happens.

### Replay Mode
Missed a session? Want to understand why a trade was taken? Open Replay Mode and scrub backward through any past session using a timeline slider. The chart rewinds to that moment in time and shows you exactly what the bot was seeing: which patterns were active, what the candles looked like, and what conditions triggered the verdict. This is the core learning tool. Whether you're a beginner trying to understand ICT concepts or an experienced trader auditing the strategy, Replay Mode gives you a session-by-session record of every decision.

### Trade History Table
A full log of every trade ever taken on your account. Filter by date, direction (BUY/SELL), scenario, or status. Click any row to open the **Verdict Sidebar**, which shows the complete ICT conditions checklist, the exact prices and risk levels, and the execution details (fill price, latency, account status).

### Prop Firm Panel
If you're running a prop firm challenge, this panel tracks your progress against the firm's rules in real-time: daily drawdown remaining, consecutive loss count, profit target progress, and halt status. The engine will automatically stop trading if a limit is about to be breached.

---

## What Makes Glass Box Different

| Feature | Glass Box | Typical Trading Bot |
|---|---|---|
| See every pattern detected | Yes — on the chart in real-time | No |
| Replay any past session | Yes — candle by candle | No |
| Understand why each trade was taken | Yes — full ICT checklist per trade | No |
| Prop firm risk controls built in | Yes — automatic halt on drawdown | Rarely |
| Multi-account execution | Yes — 50+ accounts from one signal | Varies |
| Execution latency | <20ms average | 200ms–2s typical |
| Strategy logic | Transparent, rule-based ICT | Often proprietary or AI black-box |

---

## The Strategy: ICT, Not AI

Glass Box is **not** powered by machine learning or AI. This is a deliberate choice.

The strategy is based on the Inner Circle Trader (ICT) methodology — a publicly documented framework describing how institutional order flow shapes price action in liquid forex markets. The rules are fixed and deterministic: the same market conditions always produce the same decision. There is no overfitting to historical data, no model drift, and no "the AI changed its mind."

This matters because it means the strategy is **verifiable**. You can watch what it does, compare it to the written rules, and confirm for yourself that it's executing correctly. That's the entire premise of Glass Box: trust through transparency, not through promises.

---

## Risk Management

Risk is managed at the account level, not the strategy level. For each connected broker account, you configure:

- **Risk amount per trade** (e.g., $50 per trade)
- **Risk-reward ratio** (default 3:1)
- **Breakeven buffer** (ticks of profit before SL moves to entry)
- **Max daily drawdown %** (engine halts if this is breached)

Position sizes are calculated automatically. If you're running multiple accounts (e.g., different prop firm accounts at different challenge phases), each has its own independent risk configuration.

---

## Who Is Glass Box For?

**The Trader Who Knows ICT But Can't Execute Consistently**
You've studied the concepts. You know what an FVG is. But you miss entries, override your own rules, or hesitate at key moments. Glass Box removes your hands from the execution entirely while showing you every trade so you can keep learning.

**The Prop Firm Candidate**
You're running an FTMO Phase 1 or similar challenge. A single emotional trade can end it. Glass Box respects the daily loss limit automatically, sizes positions to your challenge rules, and gives you a complete audit trail if you ever need to demonstrate strategy consistency.

**The Passive Investor Interested in Forex**
You don't want to learn how to trade. You want a system that's running rules you can verify — not a black box algorithm you have to take on faith. Glass Box is the only automated forex product that shows you everything it does and why.

---

## Pricing

| Plan | Price | Accounts | Features |
|---|---|---|---|
| **Starter** | $20/mo | 1 broker account | Live signals, Glass Box feed, basic analytics |
| **Pro** | COMING SOON | Up to 10 accounts | Full visual debugger, trade replay, prop firm panel, priority execution |
| **Enterprise** | Custom | 50+ accounts | Dedicated VM, custom risk configuration, SLA support, priority execution |

All plans include a **30-day free trial**. No credit card required to start.

---

## Technical Foundation

Glass Box is built on a production-grade technology stack designed for reliability and low latency:

- **Frontend:** React 19 + TypeScript, TradingView Lightweight Charts v5, Tailwind CSS
- **Backend:** Python with MetaTrader 5 integration; Lumibot strategy engine
- **Database:** Supabase (PostgreSQL) with row-level security — your data is isolated from all other users
- **Real-time:** Supabase WebSocket subscriptions — events appear on your dashboard within milliseconds of occurring
- **Signal broadcast:** Upstash Redis — sub-20ms latency from verdict to order submission
- **Secrets management:** Azure Key Vault — your MT5 credentials are never stored in plaintext
- **Deployment:** Windows VM (required for MetaTrader 5 compatibility)

---

## Frequently Asked Questions

**Is this real trading or paper trading?**
Glass Box executes real orders on your live MetaTrader 5 broker account. Paper trading / simulation mode is on the roadmap but not yet available. You can review the strategy in full using Replay Mode on historical sessions before going live.

**Do I need to understand ICT to use Glass Box?**
No. The bot handles everything. The dashboard is designed to be readable even if you've never heard of a Fair Value Gap — pattern names are color-coded and labeled, and hovering over any event shows a plain-English explanation. That said, if you want to understand what the bot is doing more deeply, the Replay Mode is an excellent learning tool.

**Can I run it on multiple prop firm accounts at once?**
Yes. Pro and Enterprise plans support multiple simultaneous MT5 accounts, each with independent risk settings. A single verdict from the strategy engine is broadcast to all connected accounts in parallel.

**What happens if the market moves against me sharply?**
The stop loss is set at entry and protected by your per-account drawdown limit. If daily losses hit your configured maximum, the engine stops trading for the rest of that calendar day. No new positions are opened until the next session.

**Can I turn it off?**
Yes. You can pause or disconnect your broker account from the dashboard at any time. Open positions are not automatically closed — those remain in your MT5 account under your control.

**Is my broker account information secure?**
Your MT5 credentials are stored in Azure Key Vault and are never written to any database or log file in plaintext. The backend retrieves them only at the moment of order submission.

**What pairs does it trade?**
Currently focused on major forex pairs. The specific list is configurable per account. The strategy is session-aware (London and New York only) and does not trade during low-liquidity periods.

**What is my expected return?**
We don't make return projections. Past performance on backtests does not guarantee live results. What we can tell you is that the strategy is deterministic — the same rules, applied consistently, every session. You can verify this yourself using Replay Mode.

---

## Current Status

Glass Box is in active development. The core trading engine, multi-account execution system, and dashboard (Live Mode + Replay Mode + Trade History) are built and operational. The landing page, settings page, and subscription billing integration are currently in progress.

If you're interested in early access or have questions about a specific use case, reach out directly.

---

*Glass Box — See everything. Trust what you see.*
