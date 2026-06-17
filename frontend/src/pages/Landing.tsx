import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { HeroLiveFeed } from "../components/Marketing/HeroLiveFeed";

/* ------------------------------------------------------------------ */
/* Small primitives                                                    */
/* ------------------------------------------------------------------ */

function Hex({ className = "" }: { className?: string }) {
  return <span className={`text-brand-blue ${className}`} aria-hidden>⬡</span>;
}

function Logo({ size = "text-base" }: { size?: string }) {
  return (
    <span className={`flex items-center gap-2 font-display font-bold tracking-widest ${size}`}>
      <Hex />
      <span className="text-text-primary">GLASS BOX</span>
    </span>
  );
}

/** Glossary tooltip — keyboard + hover accessible, dotted underline on the term. */
function Term({ children, def }: { children: React.ReactNode; def: string }) {
  return (
    <span className="relative group inline-block">
      <button
        type="button"
        className="border-b border-dotted border-text-secondary text-text-primary cursor-help focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-blue rounded-sm"
        aria-label={typeof children === "string" ? children : undefined}
      >
        {children}
      </button>
      <span
        role="tooltip"
        className="pointer-events-none absolute left-1/2 -translate-x-1/2 bottom-full mb-2 w-64 z-30 opacity-0 group-hover:opacity-100 group-focus-within:opacity-100 transition-opacity duration-150 bg-bg-overlay border border-border-muted rounded-lg p-3 text-xs font-sans font-normal text-text-secondary leading-relaxed shadow-lg"
      >
        {def}
      </span>
    </span>
  );
}

const DEFS = {
  FVG: "Fair Value Gap: a price gap where the market moved so fast that buyers and sellers never fully traded at those levels. Smart money tends to return to fill these gaps.",
  MSS: "Market Structure Shift: the moment the market definitively changes direction — detected when price breaks a specific previous swing point.",
  ICT: "Inner Circle Trader — a set of rules for reading how institutional banks and funds move in the market, and trading alongside them.",
  swingLow: "Swing Low: the lowest point of a recent price move before it reversed upward.",
  PDH: "Previous Day High / Low — the highest and lowest prices from the prior trading session. Key reference levels for the engine.",
};

/* ------------------------------------------------------------------ */
/* NavBar                                                              */
/* ------------------------------------------------------------------ */

function NavBar() {
  const [scrolled, setScrolled] = useState(false);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 80);
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  const links = [
    { label: "How It Works", href: "#how-it-works" },
    { label: "Features", href: "#features" },
    { label: "Prop Firm", href: "#prop-firm" },
    { label: "Pricing", href: "#pricing" },
  ];

  return (
    <nav
      className={`sticky top-0 z-50 transition-all duration-300 ${
        scrolled ? "bg-bg-surface/90 backdrop-blur-md border-b border-border-subtle" : ""
      }`}
    >
      <div className="max-w-screen-2xl mx-auto px-6 md:px-8 h-16 flex items-center justify-between">
        <Link to="/"><Logo /></Link>
        <div className="hidden md:flex gap-8 text-sm text-text-secondary">
          {links.map((l) => (
            <a key={l.href} href={l.href} className="hover:text-text-primary transition-colors">
              {l.label}
            </a>
          ))}
        </div>
        <div className="hidden md:flex items-center gap-3">
          <Link
            to="/sign-in"
            className="text-sm text-text-secondary hover:text-text-primary px-3 py-2 rounded-md transition-colors"
          >
            Sign In
          </Link>
          <Link
            to="/sign-up"
            className="text-sm bg-brand-blue hover:bg-brand-dim text-white px-4 py-2 rounded-md font-medium transition-colors"
          >
            Start Free Trial
          </Link>
        </div>
        <button
          className="md:hidden text-text-primary"
          aria-label="Toggle menu"
          aria-expanded={open}
          onClick={() => setOpen((v) => !v)}
        >
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            {open ? <path d="M6 6l12 12M18 6L6 18" /> : <path d="M3 6h18M3 12h18M3 18h18" />}
          </svg>
        </button>
      </div>

      {open && (
        <div className="md:hidden bg-bg-surface border-b border-border-subtle px-6 py-4 flex flex-col gap-4">
          {links.map((l) => (
            <a key={l.href} href={l.href} onClick={() => setOpen(false)} className="text-sm text-text-secondary">
              {l.label}
            </a>
          ))}
          <Link to="/sign-in" className="text-sm text-text-secondary">Sign In</Link>
          <Link to="/sign-up" className="text-sm bg-brand-blue text-white px-4 py-2 rounded-md text-center font-medium">
            Start Free Trial
          </Link>
        </div>
      )}
    </nav>
  );
}

/* ------------------------------------------------------------------ */
/* Hero                                                                */
/* ------------------------------------------------------------------ */

function Hero() {
  return (
    <section className="relative min-h-screen bg-bg-base overflow-hidden">
      <div className="absolute inset-0 bg-dot-grid opacity-40" aria-hidden />
      <div
        className="absolute inset-0"
        aria-hidden
        style={{
          background:
            "radial-gradient(ellipse 60% 50% at 70% 50%, rgba(56,139,253,0.08), transparent)",
        }}
      />
      <div className="relative max-w-screen-2xl mx-auto px-6 md:px-8 grid lg:grid-cols-5 gap-12 items-center min-h-screen py-24">
        <div className="lg:col-span-3">
          <p className="text-xs uppercase tracking-widest text-brand-blue font-mono">
            ICT-Based · Rule-Driven · Fully Transparent
          </p>
          <h1 className="font-display text-4xl md:text-5xl font-bold tracking-tight text-text-primary leading-tight mt-4">
            Your Trading Rules.<br />Zero Emotion.<br />Every Trade Explained.
          </h1>
          <p className="text-lg text-text-secondary max-w-md mt-4">
            An algorithmic engine that executes proven ICT setups across your broker accounts —
            automatically, consistently, and with complete visibility into every decision it makes.
          </p>
          <p className="text-sm text-text-muted mt-2">
            No AI guesswork. No black boxes. No surprises.
          </p>

          {/* Primary CTAs — full detail lives in the "Choose your path" section */}
          <div className="mt-8 flex flex-wrap gap-3">
            <Link
              to="/sign-up"
              className="inline-block bg-brand-blue hover:bg-brand-dim text-white px-5 py-2.5 rounded-md font-medium text-sm text-center transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-blue focus-visible:ring-offset-2 focus-visible:ring-offset-bg-base"
            >
              Start free &nbsp;→
            </Link>
            <a
              href="#choose-path"
              className="inline-block border border-border-muted hover:border-border-active text-text-primary px-5 py-2.5 rounded-md font-medium text-sm text-center transition-colors"
            >
              Find your path
            </a>
          </div>

          <div className="mt-6 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-text-muted">
            <span>✓ No credit card required</span><span>·</span>
            <span>✓ Cancel anytime</span><span>·</span>
            <span>✓ Every trade explained</span>
          </div>
        </div>
        <div className="lg:col-span-2">
          <HeroLiveFeed />
        </div>
      </div>
    </section>
  );
}

/* ------------------------------------------------------------------ */
/* TrustBar                                                            */
/* ------------------------------------------------------------------ */

function TrustBar() {
  const items = [
    "⬡ Built on ICT Methodology",
    "🔒 Azure Key Vault Security",
    "⚡ <20ms Execution Latency",
    "📊 FTMO / Prop Firm Ready",
    "👁 100% Trade Transparency",
  ];
  return (
    <div className="bg-bg-surface border-y border-border-subtle py-4">
      <div className="max-w-screen-2xl mx-auto px-6 md:px-8 flex flex-wrap justify-center items-center gap-6 md:gap-12">
        {items.map((it, i) => (
          <span
            key={i}
            className="text-xs text-text-secondary uppercase tracking-wide flex items-center gap-2"
          >
            {it}
          </span>
        ))}
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* What is Glass Box — problem / solution                              */
/* ------------------------------------------------------------------ */

function WhatIsGlassBox() {
  const Pain = ({ children }: { children: React.ReactNode }) => (
    <li className="flex items-start gap-2 text-sm text-text-secondary">
      <span className="text-bear shrink-0 mt-0.5">✗</span>
      <span>{children}</span>
    </li>
  );
  const Proof = ({ children }: { children: React.ReactNode }) => (
    <li className="flex items-start gap-2 text-sm text-text-secondary">
      <span className="text-bull shrink-0 mt-0.5">✓</span>
      <span>{children}</span>
    </li>
  );
  return (
    <section className="bg-bg-base py-24">
      <div className="max-w-screen-2xl mx-auto px-6 md:px-8 grid md:grid-cols-2 gap-6">
        <div className="bg-bg-surface border border-border-subtle rounded-lg p-6">
          <p className="text-xs uppercase tracking-wide text-text-muted">The Old Way</p>
          <h3 className="font-sans text-xl font-semibold text-text-primary mt-2">
            Most trading bots are black boxes.
          </h3>
          <p className="text-sm text-text-secondary mt-3">
            You pay for a bot. It takes trades. You have no idea why. When it loses, you can't
            diagnose it. When it wins, you can't trust that it will keep winning. You're flying blind.
          </p>
          <ul className="mt-5 space-y-2">
            <Pain>"AI-powered" often means over-fitted to past data</Pain>
            <Pain>No explanation for entry or exit decisions</Pain>
            <Pain>No way to verify the logic matches the strategy</Pain>
            <Pain>Fails unpredictably in changing market conditions</Pain>
          </ul>
        </div>

        <div className="bg-bg-elevated border border-border-subtle border-l-2 border-l-brand-blue rounded-lg p-6">
          <p className="text-xs uppercase tracking-wide text-brand-blue">The Glass Box Way</p>
          <h3 className="font-sans text-xl font-semibold text-text-primary mt-2">
            Every trade is a logical consequence — not a guess.
          </h3>
          <p className="text-sm text-text-secondary mt-3">
            Glass Box executes the{" "}
            <Term def={DEFS.ICT}>Inner Circle Trader (ICT)</Term> methodology — a set of strict,
            proven rules about how institutional money moves in the market. Every trade follows the
            exact same checklist. Every decision is logged. Every outcome is explainable.
          </p>
          <ul className="mt-5 space-y-2">
            <Proof>
              Detects <Term def={DEFS.FVG}>Fair Value Gaps (FVGs)</Term> using a precise 3-candle pattern
            </Proof>
            <Proof>
              Confirms <Term def={DEFS.MSS}>Market Structure Shifts (MSS)</Term> with mathematical{" "}
              <Term def={DEFS.swingLow}>swing</Term> detection
            </Proof>
            <Proof>Only enters when ALL conditions are met — no exceptions</Proof>
            <Proof>Logs every condition flag for every trade — auditable forever</Proof>
          </ul>
        </div>
      </div>
    </section>
  );
}

/* ------------------------------------------------------------------ */
/* Choose your path — two acquisition tracks                           */
/* ------------------------------------------------------------------ */

function ChoosePath() {
  return (
    <section id="choose-path" className="scroll-mt-20 bg-bg-base py-24 border-t border-border-subtle">
      <div className="max-w-screen-2xl mx-auto px-6 md:px-8">
        <div className="text-center">
          <p className="text-xs uppercase tracking-widest text-brand-blue font-mono">Choose Your Path</p>
          <h2 className="font-display text-2xl md:text-3xl font-bold text-text-primary mt-3">
            Two ways traders use Glass Box
          </h2>
          <p className="text-text-secondary mt-3 max-w-2xl mx-auto">
            Whether you follow a signal channel or you're chasing a funded account, the engine
            adapts to how you trade.
          </p>
        </div>

        <div className="mt-12 grid md:grid-cols-2 gap-6">
          {/* Track 1 — Signal follower (Starter) */}
          <div className="bg-bg-surface border border-border-subtle rounded-xl p-8 flex flex-col">
            <p className="text-xs uppercase tracking-widest text-text-muted font-mono">
              I follow signals
            </p>
            <h3 className="font-display text-xl font-bold text-text-primary mt-3">
              Auto-execute the trades you already follow
            </h3>
            <p className="text-sm text-text-secondary mt-3 flex-1 leading-relaxed">
              Stop watching Telegram for entries. Glass Box places every signal on your account
              the instant it fires — and shows you exactly why each trade was taken.
            </p>
            <ul className="mt-5 space-y-2 text-sm text-text-secondary">
              <li className="flex items-start gap-2"><span className="text-bull mt-0.5">✓</span>Instant signal-to-execution on your MT5 account</li>
              <li className="flex items-start gap-2"><span className="text-bull mt-0.5">✓</span>Full audit log you can show your provider</li>
              <li className="flex items-start gap-2"><span className="text-bull mt-0.5">✓</span>Never miss an entry while you're at work</li>
            </ul>
            <Link
              to="/sign-up"
              className="mt-6 inline-block bg-brand-blue hover:bg-brand-dim text-white px-5 py-2.5 rounded-md font-medium text-sm text-center transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-blue focus-visible:ring-offset-2 focus-visible:ring-offset-bg-base"
            >
              Auto-execute my signals &nbsp;→
            </Link>
            <p className="text-xs text-text-muted mt-3">Starter · from $15/mo</p>
          </div>

          {/* Track 2 — Prop firm challenger (Pro) */}
          <div className="bg-bg-elevated border border-border-subtle border-l-2 border-l-brand-blue rounded-xl p-8 flex flex-col">
            <p className="text-xs uppercase tracking-widest text-brand-blue font-mono">
              I run a prop challenge
            </p>
            <h3 className="font-display text-xl font-bold text-text-primary mt-3">
              Pass your challenge without breaking the rules
            </h3>
            <p className="text-sm text-text-secondary mt-3 flex-1 leading-relaxed">
              Hard-coded daily loss limits, drawdown guards, and a full audit trail of every
              decision. Built FTMO-ready, so the rules are kept for you — automatically.
            </p>
            <ul className="mt-5 space-y-2 text-sm text-text-secondary">
              <li className="flex items-start gap-2"><span className="text-bull mt-0.5">✓</span>Daily drawdown enforced by the engine</li>
              <li className="flex items-start gap-2"><span className="text-bull mt-0.5">✓</span>Consecutive-loss halt stops revenge trading</li>
              <li className="flex items-start gap-2"><span className="text-bull mt-0.5">✓</span>Complete Verdict trail for every position</li>
            </ul>
            <Link
              to="/sign-up"
              className="mt-6 inline-block border border-border-muted hover:border-border-active text-text-primary px-5 py-2.5 rounded-md font-medium text-sm text-center transition-colors"
            >
              Protect my challenge &nbsp;→
            </Link>
            <p className="text-xs text-text-muted mt-3">Pro · from $49/mo</p>
          </div>
        </div>
      </div>
    </section>
  );
}

/* ------------------------------------------------------------------ */
/* How it works                                                        */
/* ------------------------------------------------------------------ */

function HowItWorks() {
  const steps = [
    {
      icon: "📊",
      color: "text-brand-blue",
      title: "1. The Engine Scans",
      body: "Every minute, Glass Box checks the forex market against a precise set of conditions. It identifies liquidity sweeps, detects Fair Value Gaps, and confirms Market Structure Shifts — the same analysis a professional ICT trader does manually, done by a machine, 24/5, without fatigue.",
    },
    {
      icon: "☑",
      color: "text-bull",
      title: "2. A Verdict Is Reached",
      body: "When ALL conditions are confirmed — and only then — the engine creates a Verdict: a snapshot of the exact entry price, stop loss, take profit, and every condition flag that triggered the trade. This is your complete audit trail, stored forever.",
    },
    {
      icon: "⚡",
      color: "text-amber",
      title: "3. Your Accounts Execute",
      body: "The Verdict is broadcast to your connected broker accounts via a millisecond-latency message bus. Each account computes its own lot size based on your personal risk settings, then places the order simultaneously. Average execution: under 20ms.",
    },
  ];
  return (
    <section id="how-it-works" className="scroll-mt-20 bg-bg-surface py-24 border-y border-border-subtle">
      <div className="max-w-screen-2xl mx-auto px-6 md:px-8 text-center">
        <p className="text-xs uppercase tracking-widest text-brand-blue font-mono">The Process</p>
        <h2 className="font-display text-2xl md:text-3xl font-bold text-text-primary mt-3 max-w-3xl mx-auto">
          From Market Condition to Executed Order — in Under a Second
        </h2>
        <p className="text-text-secondary mt-3 max-w-2xl mx-auto">
          The engine runs a strict checklist. If any condition fails, no trade is taken. Period.
        </p>
        <div className="mt-12 grid md:grid-cols-3 gap-6">
          {steps.map((s, i) => (
            <div key={i} className="relative bg-bg-base border border-border-subtle rounded-lg p-6 text-left">
              <div className={`text-3xl ${s.color}`}>{s.icon}</div>
              <h3 className="font-sans text-base font-semibold text-text-primary mt-4">{s.title}</h3>
              <p className="text-sm text-text-secondary mt-2">{s.body}</p>
              {i < steps.length - 1 && (
                <span className="hidden md:block absolute top-1/2 -right-3 text-brand-blue text-xl" aria-hidden>
                  →
                </span>
              )}
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

/* ------------------------------------------------------------------ */
/* Glass Box feature — chart + verdict mock                            */
/* ------------------------------------------------------------------ */

function VerdictMockRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-2 text-xs py-0.5">
      <span className="flex items-center gap-1.5 text-text-secondary">
        <span className="text-bull">✓</span>
        {label}
      </span>
      <span className="font-mono text-text-primary">{value}</span>
    </div>
  );
}

function GlassBoxFeature() {
  // Static SVG candlestick illustration of a bearish ICT setup (not a real
  // chart lib, per spec). Smaller y = higher price.
  const PLOT = { top: 44, bottom: 580 };
  const P_HIGH = 1.089, P_LOW = 1.0778;
  const yToPrice = (y: number) =>
    P_HIGH - ((y - PLOT.top) / (PLOT.bottom - PLOT.top)) * (P_HIGH - P_LOW);

  const candles = Array.from({ length: 44 }, (_, i) => {
    const x = 24 + i * 14;
    const rising = i < 26;
    const base = rising ? 520 - i * 16 : 120 + (i - 26) * 22;
    const wob = ((i % 3) - 1) * 5 + (i % 2 ? 4 : -4);
    let o = base + (rising ? 8 : -8) + wob * 0.4;
    let c = base + (rising ? -9 : 9) + wob * 0.35;
    let hiPad = 6 + (i % 3) * 4;
    let loPad = 6 + (i % 4) * 3;
    // Liquidity-sweep candle: long upper wick, rejected back down (bearish).
    if (i === 25) { o = 150; c = 172; hiPad = 66; loPad = 6; }
    const top = Math.min(o, c);
    const bot = Math.max(o, c);
    return { x, o, c, hi: top - hiPad, lo: bot + loPad, up: c <= o };
  });

  const gridY = [44, 178, 312, 446, 580];
  const gridX = [24, 150, 290, 430, 570, 626];
  const times = ["07:00", "08:00", "09:00", "10:00", "11:00", "12:00"];

  return (
    <section id="features" className="scroll-mt-20 bg-bg-surface py-24">
      <div className="max-w-screen-2xl mx-auto px-6 md:px-8">
        <div className="text-center">
          <p className="text-xs uppercase tracking-widest text-brand-blue font-mono">The Glass Box Feature</p>
          <h2 className="font-display text-2xl md:text-3xl font-bold text-text-primary mt-3">
            See Exactly What the Bot Sees
          </h2>
          <p className="text-text-secondary mt-3 max-w-2xl mx-auto">
            Click any trade in your history. A panel opens showing the exact FVG it entered, the MSS
            level it confirmed, and every raw data point that triggered the Verdict. Not a summary.
            The actual data.
          </p>
        </div>

        <div className="mt-12 rounded-2xl border border-border-subtle overflow-hidden bg-bg-base">
          {/* browser chrome */}
          <div className="flex items-center gap-2 px-4 py-2.5 bg-bg-elevated border-b border-border-subtle">
            <span className="h-3 w-3 rounded-full" style={{ background: "#FF5F57" }} />
            <span className="h-3 w-3 rounded-full" style={{ background: "#FEBC2E" }} />
            <span className="h-3 w-3 rounded-full" style={{ background: "#28C840" }} />
            <span className="ml-3 font-mono text-xs text-text-muted bg-bg-base border border-border-subtle rounded px-3 py-1">
              app.glassbox.trade/dashboard
            </span>
          </div>

          <div className="grid lg:grid-cols-5">
            {/* chart */}
            <div className="lg:col-span-3 flex flex-col p-4 border-b lg:border-b-0 lg:border-r border-border-subtle">
              <svg
                viewBox="0 0 720 624"
                preserveAspectRatio="xMidYMid meet"
                className="w-full flex-1 min-h-[340px]"
                role="img"
                aria-label="Illustrative candlestick chart of a bearish ICT setup with sweep, MSS and FVG overlays"
              >
                {/* horizontal gridlines + price axis */}
                {gridY.map((y) => (
                  <g key={`gy${y}`}>
                    <line x1="24" y1={y} x2="648" y2={y} stroke="#1B2129" strokeWidth="1" />
                    <text x="654" y={y + 4} fill="#484F58" fontSize="12" fontFamily="monospace">
                      {yToPrice(y).toFixed(4)}
                    </text>
                  </g>
                ))}
                {/* vertical gridlines + time axis */}
                {gridX.map((x, i) => (
                  <g key={`gx${x}`}>
                    <line x1={x} y1="44" x2={x} y2="580" stroke="#161B22" strokeWidth="1" />
                    <text x={x} y="600" fill="#484F58" fontSize="12" fontFamily="monospace" textAnchor="middle">
                      {times[i]}
                    </text>
                  </g>
                ))}

                {/* liquidity sweep zone */}
                <rect x="24" y="74" width="624" height="30" fill="#D2992218" />
                <line x1="24" y1="89" x2="648" y2="89" stroke="#D29922" strokeWidth="1" strokeDasharray="2 3" opacity="0.6" />
                <text x="30" y="94" fill="#D29922" fontSize="13" fontFamily="monospace">Liquidity Sweep — PDH</text>

                {/* FVG zone */}
                <rect x="24" y="330" width="624" height="50" fill="#388BFD1A" />
                <text x="30" y="350" fill="#388BFD" fontSize="13" fontFamily="monospace">Fair Value Gap (FVG)</text>

                {/* MSS level */}
                <line x1="24" y1="215" x2="648" y2="215" stroke="#F85149" strokeWidth="1.5" strokeDasharray="5 4" />
                <text x="470" y="208" fill="#F85149" fontSize="13" fontFamily="monospace">MSS — Structure Broken</text>

                {/* candles */}
                {candles.map((c, i) => (
                  <g key={i}>
                    <line x1={c.x} y1={c.hi} x2={c.x} y2={c.lo} stroke={c.up ? "#3FB950" : "#F85149"} strokeWidth="1.6" />
                    <rect
                      x={c.x - 4.5}
                      y={Math.min(c.o, c.c)}
                      width="9"
                      height={Math.max(2, Math.abs(c.c - c.o))}
                      fill={c.up ? "#3FB950" : "#F85149"}
                    />
                  </g>
                ))}

                {/* MSS confirmed marker at the break */}
                <circle cx="444" cy="215" r="5" fill="#3FB950" stroke="#080C10" strokeWidth="1.5" />
                <text x="300" y="238" fill="#3FB950" fontSize="13" fontFamily="monospace">MSS Confirmed ✓</text>

                {/* entry into the FVG */}
                <circle cx="514" cy="355" r="5" fill="#F85149" stroke="#080C10" strokeWidth="1.5" />
                <text x="526" y="360" fill="#F85149" fontSize="14" fontFamily="monospace">▼ SELL ENTRY</text>
              </svg>
            </div>

            {/* verdict sidebar */}
            <div className="lg:col-span-2 p-5 font-mono">
              <p className="text-xs uppercase tracking-wide text-text-muted">Verdict Panel — Signal #4821</p>
              <div className="mt-3 space-y-1 text-xs">
                <div className="flex justify-between"><span className="text-text-secondary">Direction</span><span className="text-bear font-semibold">SELL ▼</span></div>
                <div className="flex justify-between"><span className="text-text-secondary">Entry Price</span><span className="text-text-primary">1.08490</span></div>
                <div className="flex justify-between"><span className="text-text-secondary">Stop Loss</span><span className="text-bear">1.08762</span></div>
                <div className="flex justify-between"><span className="text-text-secondary">Take Profit</span><span className="text-bull">1.07980</span></div>
                <div className="flex justify-between"><span className="text-text-secondary">Risk/Reward</span><span className="text-brand-blue">3.12R</span></div>
                <div className="flex justify-between"><span className="text-text-secondary">Scenario</span><span className="text-text-primary">london_bearish</span></div>
              </div>

              <p className="mt-4 text-[10px] uppercase tracking-wider text-text-muted border-t border-border-subtle pt-3">ICT Conditions</p>
              <div className="mt-2">
                <VerdictMockRow label="Swept High" value="1.08742" />
                <VerdictMockRow label="MSS Swing Low" value="1.08511" />
                <VerdictMockRow label="MSS Confirmed" value="Yes" />
                <VerdictMockRow label="FVG Confirmed" value="Yes" />
                <VerdictMockRow label="FVG Top" value="1.08561" />
                <VerdictMockRow label="FVG Bottom" value="1.08490" />
                <VerdictMockRow label="PDH" value="1.08690" />
                <VerdictMockRow label="PDL" value="1.07910" />
              </div>

              <p className="mt-4 text-[10px] uppercase tracking-wider text-text-muted border-t border-border-subtle pt-3">Execution</p>
              <div className="mt-2 space-y-1 text-xs">
                <div className="flex justify-between"><span className="text-text-secondary">Accounts Fired</span><span className="text-text-primary">54</span></div>
                <div className="flex justify-between"><span className="text-text-secondary">Avg Latency</span><span className="text-text-primary">17ms</span></div>
                <div className="flex justify-between"><span className="text-text-secondary">Status</span><span className="text-bull">FILLED ●</span></div>
              </div>
            </div>
          </div>
        </div>
        <p className="text-center text-sm text-text-muted mt-6">
          Every trade. Every condition. Every timestamp. Stored and visible to you — always.
        </p>

        {/* Shareable audit trail — B2B2C feature callout */}
        <div className="mt-10 rounded-lg border border-border-subtle bg-bg-elevated p-6 flex flex-col md:flex-row items-start md:items-center gap-6">
          <div className="shrink-0 flex items-center justify-center h-12 w-12 rounded-lg bg-bg-base border border-border-subtle text-2xl">
            ⬡
          </div>
          <div className="flex-1">
            <p className="text-xs uppercase tracking-widest text-brand-blue font-mono">Starter Feature</p>
            <h3 className="font-sans text-base font-semibold text-text-primary mt-1">
              Share your audit trail — let your signal provider see exactly what happened
            </h3>
            <p className="text-sm text-text-secondary mt-1.5 leading-relaxed">
              One click generates a public read-only link to your session. Your signal provider opens
              it without an account and sees the same Verdict panel you see — every condition flag,
              every timestamp, every execution. No more "the bot took a different trade" disputes.
              Full transparency, both directions.
            </p>
          </div>
          <div className="shrink-0">
            <div className="font-mono text-xs bg-bg-base border border-border-subtle rounded px-3 py-2 text-text-muted whitespace-nowrap">
              glassbox.trade/audit/<span className="text-brand-blue">a8f2c</span>
            </div>
            <p className="text-[10px] text-text-muted mt-1.5 text-center">Read-only · No login required</p>
          </div>
        </div>
      </div>
    </section>
  );
}

/* ------------------------------------------------------------------ */
/* Prop firm section                                                   */
/* ------------------------------------------------------------------ */

function PropFirmWidget() {
  return (
    <div className="bg-bg-surface border border-border-subtle rounded-lg p-6 font-sans">
      <p className="text-xs uppercase tracking-wide text-text-muted">Prop Firm Constraints</p>

      <div className="mt-5">
        <p className="text-xs uppercase tracking-wide text-text-secondary">Daily Drawdown</p>
        <div className="mt-2 h-2 rounded-full bg-bg-elevated overflow-hidden">
          <div className="h-full bg-bull rounded-full" style={{ width: "72%" }} />
        </div>
        <div className="flex justify-between mt-1.5 text-xs text-text-secondary font-mono">
          <span>Used: $280 of $1,000</span>
          <span>Resets in 14h 22m</span>
        </div>
      </div>

      <div className="mt-5">
        <p className="text-xs uppercase tracking-wide text-text-secondary">Win Rate · This Month</p>
        <p className="font-mono text-text-primary mt-1">68.4% · 23W / 10L</p>
      </div>

      <div className="mt-5">
        <p className="text-xs uppercase tracking-wide text-text-secondary">Consecutive Losses</p>
        <p className="mt-1 text-sm">
          <span className="text-bull">●</span>{" "}
          <span className="text-text-muted">○ ○</span>{" "}
          <span className="text-text-secondary font-mono">0 (Max allowed: 3)</span>
        </p>
      </div>

      <div className="mt-5">
        <p className="text-xs uppercase tracking-wide text-text-secondary">Engine Status</p>
        <p className="mt-1 text-sm flex items-center gap-2 text-bull">
          <span className="h-2 w-2 rounded-full bg-bull animate-pulse-dot" /> ACTIVE — No halt conditions met
        </p>
      </div>
    </div>
  );
}

function PropFirmSection() {
  return (
    <section id="prop-firm" className="scroll-mt-20 bg-bg-base py-24">
      <div className="max-w-screen-2xl mx-auto px-6 md:px-8 grid md:grid-cols-2 gap-12 items-center">
        <div>
          <p className="text-xs uppercase tracking-widest text-brand-blue font-mono">Prop Firm Ready</p>
          <h2 className="font-display text-2xl md:text-3xl font-bold text-text-primary mt-3">
            Built for FTMO. Built for Discipline.
          </h2>
          <p className="text-sm text-text-secondary mt-4 leading-relaxed">
            Prop firm challenges have one rule above all others: don't blow the account with a bad
            day. Glass Box hard-codes your prop firm's risk rules directly into the engine. Your
            daily <Term def={DEFS.PDH}>drawdown</Term> limit is enforced by the bot — not by your
            willpower at 2am.
          </p>
          <p className="text-sm text-text-secondary mt-3 leading-relaxed">
            If the daily loss threshold is hit, the engine halts automatically. No new trades. Your
            existing positions run to their stop loss or take profit naturally. Then it resets the
            next day.
          </p>
          <ul className="mt-6 space-y-2 text-sm text-text-secondary">
            {[
              "Configurable daily drawdown limit (e.g. 4% for FTMO Phase 1)",
              "Automatic halt when limit is reached — no manual intervention needed",
              "Per-account risk sizing — risk what you configure, not a fixed global amount",
              "Consistent execution — no emotional over-trading, no revenge trades",
              "Full audit trail for prop firm review if ever requested",
            ].map((t, i) => (
              <li key={i} className="flex items-start gap-2">
                <span className="text-bull shrink-0 mt-0.5">✓</span>{t}
              </li>
            ))}
          </ul>
        </div>
        <PropFirmWidget />
      </div>
    </section>
  );
}

/* ------------------------------------------------------------------ */
/* Social Proof                                                        */
/* ------------------------------------------------------------------ */

const TESTIMONIALS = [
  {
    quote:
      "I failed two FTMO Phase 1 attempts by breaking the daily drawdown rule on a bad day. With Glass Box the engine just stops. I passed Phase 2 clean.",
    handle: "@tunde_fx",
    context: "FTMO Phase 2 — $50k account",
    tier: "Pro",
  },
  {
    quote:
      "I follow a signal channel on Telegram. I used to miss entries because I was at work. Now every signal lands on my account the second it fires, with a full audit log I can show my provider.",
    handle: "@chiamaka_trades",
    context: "Starter — 1 MT5 account",
    tier: "Starter",
  },
  {
    quote:
      "The Verdict panel is the only reason I trust this more than any other bot I've tried. I can see the exact FVG it entered, the MSS level, the timestamp. No other bot shows you this.",
    handle: "@adekunle_ict",
    context: "MyForexFunds challenge community",
    tier: "Pro",
  },
  {
    quote:
      "Running a prop challenge, I need to know the bot won't revenge-trade after a loss. The consecutive loss halt gave me that confidence immediately.",
    handle: "@zara_fx_ng",
    context: "E8 Funding — Phase 1",
    tier: "Pro",
  },
];

const COMMUNITY_STATS = [
  { value: "340+", label: "Traders in FTMO challenge communities" },
  { value: "12,000+", label: "Trades executed with full audit trail" },
  { value: "0", label: "Surprise rule violations on prop challenges" },
  { value: "68%", label: "Average win rate across active accounts" },
];

/* ------------------------------------------------------------------ */
/* Testimonial marquee                                                 */
/* ------------------------------------------------------------------ */

function TestimonialCard({ t }: { t: (typeof TESTIMONIALS)[number] }) {
  const initials = t.handle
    .replace(/^@/, "")
    .split(/[_\s]/)
    .slice(0, 2)
    .map((w) => w[0]?.toUpperCase() ?? "")
    .join("");
  return (
    <figure className="w-[340px] shrink-0 bg-bg-surface border border-border-subtle rounded-xl p-6 flex flex-col gap-4 transition-colors hover:border-brand-blue/50">
      <div className="flex items-center gap-3">
        <span className="grid place-items-center h-10 w-10 rounded-full bg-brand-blue/15 text-brand-blue font-mono text-sm font-semibold border border-brand-blue/30 shrink-0">
          {initials}
        </span>
        <div className="min-w-0">
          <figcaption className="text-sm font-medium text-text-primary font-mono truncate">
            {t.handle}
          </figcaption>
          <p className="text-xs text-text-muted truncate">{t.context}</p>
        </div>
        <span
          className={`ml-auto text-[10px] px-2 py-0.5 rounded-full font-mono border shrink-0 ${
            t.tier === "Pro"
              ? "border-brand-blue text-brand-blue"
              : "border-border-muted text-text-muted"
          }`}
        >
          {t.tier}
        </span>
      </div>
      <blockquote className="text-sm text-text-secondary leading-relaxed">
        <span className="text-brand-blue mr-0.5">"</span>
        {t.quote}
        <span className="text-brand-blue ml-0.5">"</span>
      </blockquote>
    </figure>
  );
}

function MarqueeRow({
  items,
  reverse = false,
}: {
  items: typeof TESTIMONIALS;
  reverse?: boolean;
}) {
  // Duplicate the track so the translateX loop appears seamless.
  const track = [...items, ...items];
  return (
    <div className="group flex overflow-hidden" aria-hidden={reverse}>
      <div
        className="flex gap-6 pr-6 shrink-0 will-change-transform group-hover:[animation-play-state:paused] motion-reduce:animate-none"
        style={{
          animation: `${reverse ? "marquee-rtl" : "marquee-ltr"} 40s linear infinite`,
        }}
      >
        {track.map((t, i) => (
          <TestimonialCard key={i} t={t} />
        ))}
      </div>
    </div>
  );
}

function TestimonialMarquee() {
  const half = Math.ceil(TESTIMONIALS.length / 2);
  const rowA = TESTIMONIALS;
  const rowB = [...TESTIMONIALS.slice(half), ...TESTIMONIALS.slice(0, half)];
  return (
    <div className="relative mt-12 -mx-6 md:-mx-8">
      <style>{`
        @keyframes marquee-ltr { from { transform: translateX(0); } to { transform: translateX(-50%); } }
        @keyframes marquee-rtl { from { transform: translateX(-50%); } to { transform: translateX(0); } }
      `}</style>
      {/* edge fade masks in app background colour */}
      <div className="pointer-events-none absolute inset-y-0 left-0 w-16 md:w-32 z-10 bg-gradient-to-r from-bg-base to-transparent" />
      <div className="pointer-events-none absolute inset-y-0 right-0 w-16 md:w-32 z-10 bg-gradient-to-l from-bg-base to-transparent" />
      <div className="flex flex-col gap-6 px-6 md:px-8">
        <MarqueeRow items={rowA} />
        <MarqueeRow items={rowB} reverse />
      </div>
    </div>
  );
}

/**
 * Animates a number counting up from 0 to the target parsed out of `value`
 * (e.g. "12,000+", "68%", "340+"). Surrounding prefix/suffix text is
 * preserved and the count starts when the element scrolls into view.
 */
function CountUp({ value, className = "" }: { value: string; className?: string }) {
  const ref = useRef<HTMLParagraphElement>(null);
  const [display, setDisplay] = useState(value);

  useEffect(() => {
    const match = value.match(/([^\d]*)([\d,]+)(.*)/);
    if (!match) {
      setDisplay(value);
      return;
    }
    const [, prefix, numStr, suffix] = match;
    const target = parseInt(numStr.replace(/,/g, ""), 10);
    const hasComma = numStr.includes(",");
    const format = (n: number) =>
      `${prefix}${hasComma ? n.toLocaleString("en-US") : n}${suffix}`;

    setDisplay(format(0));

    const el = ref.current;
    if (!el) return;

    let raf = 0;
    let started = false;
    const duration = 1600;

    const run = () => {
      const start = performance.now();
      const tick = (now: number) => {
        const t = Math.min((now - start) / duration, 1);
        // easeOutCubic
        const eased = 1 - Math.pow(1 - t, 3);
        setDisplay(format(Math.round(eased * target)));
        if (t < 1) raf = requestAnimationFrame(tick);
      };
      raf = requestAnimationFrame(tick);
    };

    if (window.matchMedia?.("(prefers-reduced-motion: reduce)").matches) {
      setDisplay(format(target));
      return;
    }

    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting && !started) {
          started = true;
          run();
          observer.disconnect();
        }
      },
      { threshold: 0.4 }
    );
    observer.observe(el);

    return () => {
      observer.disconnect();
      cancelAnimationFrame(raf);
    };
  }, [value]);

  return (
    <p ref={ref} className={className}>
      {display}
    </p>
  );
}

function SocialProof() {
  return (
    <section className="bg-bg-base py-24 border-t border-border-subtle">
      <div className="max-w-screen-2xl mx-auto px-6 md:px-8">
        <div className="text-center">
          <p className="text-xs uppercase tracking-widest text-brand-blue font-mono">From the Community</p>
          <h2 className="font-display text-2xl md:text-3xl font-bold text-text-primary mt-3">
            Prop firm traders are the hardest group to convince.
          </h2>
          <p className="text-text-secondary mt-3 max-w-2xl mx-auto">
            They've been burned by black-box bots before. Here's what they say after seeing the audit trail.
          </p>
        </div>

        {/* Stats row */}
        <div className="mt-12 grid grid-cols-2 md:grid-cols-4 gap-px bg-border-subtle rounded-lg overflow-hidden border border-border-subtle">
          {COMMUNITY_STATS.map((s, i) => (
            <div key={i} className="bg-bg-surface p-6 text-center">
              <CountUp
                value={s.value}
                className="font-display text-3xl font-bold text-text-primary"
              />
              <p className="text-xs text-text-muted mt-1 leading-snug">{s.label}</p>
            </div>
          ))}
        </div>

        {/* Testimonial marquee */}
        <TestimonialMarquee />

        <p className="text-center text-xs text-text-muted mt-8">
          Early access community · Nigeria, UK, Canada, South Africa
        </p>
      </div>
    </section>
  );
}

/* ------------------------------------------------------------------ */
/* Pricing                                                             */
/* ------------------------------------------------------------------ */

function PricingSection() {
  const plans = [
    {
      name: "Starter", price: "$15", per: "/ month", popular: false,
      features: ["1 broker account", "Live signals", "Glass Box feed", "Basic analytics"],
      cta: "Get Started", to: "/sign-up",
    },
    {
      name: "Pro", price: "$49", per: "/ month", popular: true,
      features: ["Up to 10 broker accounts", "Live signals", "Glass Box feed", "Full Visual Debugger", "Prop Firm Constraints Panel", "Trade Replay", "Priority execution"],
      cta: "Start Free Trial", to: "/sign-up",
    },
    {
      name: "Enterprise", price: "Contact Us", per: "", popular: false,
      features: ["50+ accounts", "Custom config", "SLA support", "Dedicated VM", "Priority execution"],
      cta: "Contact Sales", to: "/sign-up",
    },
  ];
  return (
    <section id="pricing" className="scroll-mt-20 bg-bg-surface py-24 border-y border-border-subtle">
      <div className="max-w-screen-2xl mx-auto px-6 md:px-8">
        <div className="text-center">
          <p className="text-xs uppercase tracking-widest text-brand-blue font-mono">Pricing</p>
          <h2 className="font-display text-2xl md:text-3xl font-bold text-text-primary mt-3">
            Simple Plans. Total Transparency.
          </h2>
        </div>
        <div className="mt-12 grid md:grid-cols-3 gap-6 items-start max-w-5xl mx-auto">
          {plans.map((p) => (
            <div
              key={p.name}
              className={`rounded-lg p-6 border ${
                p.popular ? "border-brand-blue bg-bg-elevated relative" : "border-border-subtle bg-bg-base"
              }`}
            >
              {p.popular && (
                <span className="absolute -top-3 left-1/2 -translate-x-1/2 bg-brand-blue text-white text-xs px-3 py-1 rounded-full">
                  MOST POPULAR
                </span>
              )}
              <p className="text-xs uppercase tracking-widest text-text-secondary">{p.name}</p>
              <p className="mt-3">
                <span className="font-display text-3xl font-bold text-text-primary">{p.price}</span>
                <span className="text-sm text-text-muted"> {p.per}</span>
              </p>
              <ul className="mt-5 space-y-2 text-sm text-text-secondary">
                {p.features.map((f) => (
                  <li key={f} className="flex items-start gap-2"><span className="text-bull">✓</span>{f}</li>
                ))}
              </ul>
              <Link
                to={p.to}
                className={`block text-center mt-6 px-4 py-2.5 rounded-md font-medium text-sm transition-colors ${
                  p.popular ? "bg-brand-blue hover:bg-brand-dim text-white" : "border border-border-muted text-text-primary hover:border-border-active"
                }`}
              >
                {p.cta}
              </Link>
            </div>
          ))}
        </div>
        <p className="text-center text-sm text-text-muted mt-8 max-w-xl mx-auto">
          All plans include a 30-day free trial. No credit card required. Cancel anytime. FTMO-ready
          configuration guide included with every plan.
        </p>
      </div>
    </section>
  );
}

/* ------------------------------------------------------------------ */
/* FAQ                                                                 */
/* ------------------------------------------------------------------ */

function FAQSection() {
  const faqs = [
    { q: "I know nothing about trading. Can I still use this?", a: "Yes. Glass Box handles all the analysis and execution. You don't need to know what an FVG or MSS is to benefit from the system. However, the transparency features mean you can learn what the bot is doing over time — and see exactly why every trade was taken." },
    { q: "How is this different from AI trading bots?", a: "AI bots are probabilistic — they guess based on patterns in historical data. Glass Box is deterministic — it follows a fixed, auditable ruleset derived from the ICT methodology. There's no machine learning involved. The same conditions will always produce the same trade decision. You can verify that." },
    { q: "What if I'm trying to pass an FTMO challenge?", a: "Glass Box is built with prop firm traders in mind. You set your daily drawdown limit, and the engine enforces it. When the limit is hit, it stops taking trades for the rest of the day — automatically. This removes the single biggest reason prop firm attempts fail: emotional override of risk rules." },
    { q: "What broker accounts does it support?", a: "Glass Box connects to MetaTrader 5 (MT5) accounts. Most major forex brokers support MT5. You connect your account credentials securely — they are stored in Azure Key Vault and never exposed in plaintext to anyone, including our team." },
    { q: "Can I see the bot's logic before it trades?", a: "Yes. The Live Feed in the dashboard streams the bot's thought process in real-time — before, during, and after each trade. The Visual Debugger shows the exact chart conditions (FVG zones, MSS levels, sweep points) that triggered each Verdict. Everything is visible." },
    { q: "What if the bot makes a loss?", a: "The ICT methodology, like any strategy, has losing trades. Glass Box does not guarantee profit. What it guarantees is that every trade follows the exact same disciplined rules — and that you have a complete record of every decision. Risk management is built in: your stop loss is always calculated before the trade is taken, and your daily drawdown limit is enforced automatically." },
  ];
  const [open, setOpen] = useState<number | null>(0);
  return (
    <section className="bg-bg-base py-24">
      <div className="max-w-3xl mx-auto px-6 md:px-8">
        <div className="text-center">
          <p className="text-xs uppercase tracking-widest text-brand-blue font-mono">FAQ</p>
          <h2 className="font-display text-2xl md:text-3xl font-bold text-text-primary mt-3">
            Questions, Answered Honestly
          </h2>
        </div>
        <div className="mt-10 divide-y divide-border-subtle border border-border-subtle rounded-lg overflow-hidden">
          {faqs.map((f, i) => (
            <div key={i} className="bg-bg-surface">
              <button
                className="w-full flex items-center justify-between gap-4 text-left px-5 py-4 hover:bg-bg-elevated transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-blue"
                onClick={() => setOpen(open === i ? null : i)}
                aria-expanded={open === i}
              >
                <span className="text-sm font-medium text-text-primary">{f.q}</span>
                <span className="text-text-muted shrink-0">{open === i ? "−" : "+"}</span>
              </button>
              {open === i && (
                <p className="px-5 pb-4 text-sm text-text-secondary leading-relaxed">{f.a}</p>
              )}
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

/* ------------------------------------------------------------------ */
/* Footer                                                              */
/* ------------------------------------------------------------------ */

function Footer() {
  const cols = [
    { title: "Product", links: ["How It Works", "Features", "Prop Firm", "Pricing"] },
    { title: "Company", links: ["About", "Blog", "Careers", "Contact"] },
    { title: "Legal", links: ["Terms", "Privacy", "Risk Disclosure"] },
  ];
  return (
    <footer className="bg-bg-surface border-t border-border-subtle">
      <div className="max-w-screen-2xl mx-auto px-6 md:px-8 py-12 grid md:grid-cols-4 gap-8">
        <div>
          <Logo />
          <p className="text-sm text-text-secondary mt-3 max-w-xs">
            The transparent, rule-driven trading engine. See everything the bot sees.
          </p>
        </div>
        {cols.map((c) => (
          <div key={c.title}>
            <p className="text-xs uppercase tracking-wide text-text-muted">{c.title}</p>
            <ul className="mt-3 space-y-2">
              {c.links.map((l) => (
                <li key={l}>
                  <a href="#" className="text-sm text-text-secondary hover:text-text-primary transition-colors">{l}</a>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
      <div className="border-t border-border-subtle">
        <div className="max-w-screen-2xl mx-auto px-6 md:px-8 py-5 text-xs text-text-muted">
          © 2026 Glass Box Trading Engine. Not financial advice. Trading forex carries risk.
        </div>
      </div>
    </footer>
  );
}

/* ------------------------------------------------------------------ */
/* Page                                                                */
/* ------------------------------------------------------------------ */

export function Landing() {
  return (
    <div className="bg-bg-base text-text-primary overflow-x-hidden">
      <NavBar />
      <Hero />
      <TrustBar />
      <WhatIsGlassBox />
      <ChoosePath />
      <HowItWorks />
      <GlassBoxFeature />
      <PropFirmSection />
      <SocialProof />
      <PricingSection />
      <FAQSection />
      <Footer />
    </div>
  );
}
