import { useEffect, useMemo, useRef, useState } from "react";
import { useReplayStore } from "../../store/replayStore";
import { useMarketStatus } from "../../hooks/useMarketStatus";
import type { TradeEvent } from "../../types";
import { fmtTimeWAT, fmtPrice } from "../../utils/format";
import { Term, ICT_DEFS } from "../Term";

type LineKind = "scan" | "detect" | "confirm" | "verdict" | "exec" | "halt" | "breakeven" | "error";

const ICON: Record<LineKind, { glyph: string; cls: string }> = {
  scan:      { glyph: "⟳", cls: "text-text-muted" },
  detect:    { glyph: "◉", cls: "text-amber" },
  confirm:   { glyph: "✓", cls: "text-bull" },
  verdict:   { glyph: "⚡", cls: "text-brand-blue" },
  exec:      { glyph: "⚡", cls: "text-brand-blue" },
  halt:      { glyph: "⛔", cls: "text-bear" },
  breakeven: { glyph: "↗", cls: "text-breakeven" },
  error:     { glyph: "⚠", cls: "text-amber" },
};

/** Translate a raw trade_event into a human-readable feed line. */
function describe(e: TradeEvent): { kind: LineKind; text: string } {
  const m = e.metadata ?? {};
  switch (e.type) {
    case "entry": {
      const dir = ((m.direction as string) ?? "").toUpperCase() || "ENTRY";
      const rr = typeof m.rr === "number" ? ` · RR=${(m.rr as number).toFixed(1)}R` : "";
      return {
        kind: "verdict",
        text: `VERDICT: ${dir} · Entry=${fmtPrice(e.price ?? 0, e.pair)}${
          typeof m.sl === "number" ? ` · SL=${fmtPrice(m.sl as number, e.pair)}` : ""
        }${typeof m.tp === "number" ? ` · TP=${fmtPrice(m.tp as number, e.pair)}` : ""}${rr}`,
      };
    }
    case "exit": {
      const pnl = m.pnl as number | undefined;
      if (typeof pnl === "number")
        return {
          kind: pnl >= 0 ? "confirm" : "error",
          text: `Position closed on ${e.pair} · P/L ${pnl >= 0 ? "+" : "-"}$${Math.abs(pnl).toFixed(0)}`,
        };
      return { kind: "exec", text: `Position closed on ${e.pair}` };
    }
    case "invalidated":
      return { kind: "error", text: `Setup invalidated on ${e.pair} (${e.pattern ?? "—"})` };
    case "pattern_detected":
    default: {
      if (e.pattern === "MSS") return { kind: "confirm", text: `MSS confirmed on ${e.pair} at ${fmtPrice(e.price ?? 0, e.pair)}` };
      if (e.pattern === "FVG") return { kind: "detect", text: `Fair Value Gap detected on ${e.pair} at ${fmtPrice(e.price ?? 0, e.pair)}` };
      if (e.pattern) return { kind: "detect", text: `${e.pattern} detected on ${e.pair} at ${fmtPrice(e.price ?? 0, e.pair)}` };
      return { kind: "scan", text: `Scanning ${e.timeframe} on ${e.pair} for setup conditions...` };
    }
  }
}

type Chunk = { k: "text"; v: string } | { k: "term"; v: string; def: string };
// Ordered longest-phrase-first so multi-word terms are matched before their
// abbreviations (e.g. "Fair Value Gap" before "FVG").
const FEED_TERMS: [string, string][] = [
  ["Market Structure Shift", ICT_DEFS.MSS],
  ["Break of Structure", ICT_DEFS.BOS],
  ["Fair Value Gap", ICT_DEFS.FVG],
  ["Order Block", ICT_DEFS.OB],
  ["MSS", ICT_DEFS.MSS],
  ["FVG", ICT_DEFS.FVG],
  ["BOS", ICT_DEFS.BOS],
  ["OB", ICT_DEFS.OB],
];

/** Split a feed line string into text + glossary-term chunks for inline tooltips. */
function parseLine(text: string): React.ReactNode {
  let chunks: Chunk[] = [{ k: "text", v: text }];
  for (const [term, def] of FEED_TERMS) {
    const next: Chunk[] = [];
    for (const c of chunks) {
      if (c.k !== "text") { next.push(c); continue; }
      const parts = c.v.split(term);
      parts.forEach((part, i) => {
        if (part) next.push({ k: "text", v: part });
        if (i < parts.length - 1) next.push({ k: "term", v: term, def });
      });
    }
    chunks = next;
  }
  return (
    <>
      {chunks.map((c, i) =>
        c.k === "text" ? (
          <span key={i}>{c.v}</span>
        ) : (
          <Term key={i} def={c.def}>{c.v}</Term>
        ),
      )}
    </>
  );
}

/** Markets the engine tracks — each has its own logic feed. */
const FEED_MARKETS = [
  "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD",
  "XAUUSD", "NAS100", "US30",
];

export function LiveLogicFeed({
  heightClass = "h-80",
  showMarketTabs = false,
}: {
  heightClass?: string;
  showMarketTabs?: boolean;
}) {
  const events = useReplayStore((s) => s.events);
  const currentTime = useReplayStore((s) => s.currentTime);
  const selectedPair = useReplayStore((s) => s.selectedPair);
  const setSelectedPair = useReplayStore((s) => s.setSelectedPair);
  const marketOpen = useMarketStatus();
  const scrollRef = useRef<HTMLDivElement>(null);
  const [paused, setPaused] = useState(false);

  const lines = useMemo(
    () =>
      events
        .filter((e) => e.timestamp <= (currentTime || Date.now()))
        .sort((a, b) => a.timestamp - b.timestamp)
        .slice(-200)
        .map((e) => ({ id: e.id, ts: e.timestamp, ...describe(e) })),
    [events, currentTime],
  );

  useEffect(() => {
    if (paused) return;
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight });
  }, [lines, paused]);

  // Re-enable auto-scroll when the user scrolls back to the bottom.
  const onScroll = () => {
    const el = scrollRef.current;
    if (!el) return;
    const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 8;
    if (atBottom && paused) setPaused(false);
  };

  return (
    <div className="bg-bg-surface border border-border-subtle rounded-lg flex flex-col">
      {/* header */}
      <div className="flex items-center justify-between px-4 h-10 border-b border-border-subtle">
        <span className="text-xs uppercase tracking-wide text-text-secondary font-mono">Live Feed</span>
        {marketOpen ? (
          <span className="flex items-center gap-1.5 text-xs text-bull font-mono">
            <span className="h-2 w-2 rounded-full bg-bull animate-pulse-dot" /> LIVE
          </span>
        ) : (
          <span className="flex items-center gap-1.5 text-xs text-bear font-mono">
            ● MARKET CLOSED
          </span>
        )}
      </div>

      {/* Per-market selector — each market streams its own logic feed */}
      {showMarketTabs && (
        <div
          className="flex items-center gap-1.5 overflow-x-auto px-3 py-2 border-b border-border-subtle"
          role="tablist"
          aria-label="Select market feed"
        >
          {FEED_MARKETS.map((m) => {
            const active = m === selectedPair;
            return (
              <button
                key={m}
                role="tab"
                aria-selected={active}
                onClick={() => setSelectedPair(m)}
                className={`shrink-0 rounded-md px-2.5 py-1 text-xs font-mono border transition-colors ${
                  active
                    ? "bg-brand-glow border-brand-blue text-brand-blue"
                    : "border-border-subtle text-text-secondary hover:text-text-primary hover:border-border-muted"
                }`}
              >
                {m}
              </button>
            );
          })}
        </div>
      )}

      <div className="relative">
        <div
          ref={scrollRef}
          onScroll={onScroll}
          className={`${heightClass} overflow-y-auto p-3 font-mono text-xs`}
          role="log"
          aria-live="polite"
          aria-atomic="false"
        >
          {lines.length === 0 ? (
            <p className="text-text-muted px-1 py-2">
              Waiting for engine activity — log lines appear here as the bot scans and trades.
            </p>
          ) : (
            lines.map((l) => {
              const icon = ICON[l.kind];
              const rowBg =
                l.kind === "verdict" ? "bg-brand-glow" : l.kind === "halt" ? "bg-bear-dim" : "";
              return (
                <div key={l.id} className={`flex items-start gap-2 py-1 px-1.5 rounded ${rowBg}`}>
                  <span className="text-text-muted shrink-0">{fmtTimeWAT(l.ts)}</span>
                  <span className={`${icon.cls} shrink-0`} aria-hidden>{icon.glyph}</span>
                  <span
                    className={
                      l.kind === "verdict"
                        ? "text-brand-blue font-semibold"
                        : l.kind === "halt"
                          ? "text-bear font-semibold"
                          : "text-text-secondary"
                    }
                  >
                    {parseLine(l.text)}
                  </span>
                </div>
              );
            })
          )}
        </div>

        {paused && (
          <div className="absolute bottom-2 right-2 flex items-center gap-2 bg-bg-overlay border border-border-muted rounded-md px-3 py-1.5 text-xs">
            <span className="text-amber font-mono">PAUSED</span>
            <button
              onClick={() => {
                setPaused(false);
                scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight });
              }}
              className="text-brand-blue hover:underline"
            >
              Resume →
            </button>
          </div>
        )}
        {!paused && lines.length > 0 && (
          <button
            onClick={() => setPaused(true)}
            aria-label="Pause auto-scroll"
            className="absolute bottom-2 right-2 h-6 w-6 flex items-center justify-center rounded-md bg-bg-overlay border border-border-muted text-text-secondary hover:text-text-primary text-xs"
          >
            ▼
          </button>
        )}
      </div>
    </div>
  );
}
