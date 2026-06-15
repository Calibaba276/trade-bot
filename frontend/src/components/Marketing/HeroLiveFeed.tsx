import { useEffect, useRef, useState } from "react";

type FeedType = "scan" | "detect" | "confirm" | "verdict" | "exec";

interface FeedMessage {
  type: FeedType;
  text: string;
}

// Simulated stream of the bot's thought process — auto-cycles with a typewriter feel.
const FEED_MESSAGES: FeedMessage[] = [
  { type: "scan", text: "Scanning M15 for liquidity sweep above PDH..." },
  { type: "detect", text: "Swept high confirmed at 1.08742 — highest sweep point locked" },
  { type: "scan", text: "Price reversing below PDH — scanning for swing low..." },
  { type: "detect", text: "MSS swing low identified at 1.08511" },
  { type: "confirm", text: "Price broke below swing low — MSS CONFIRMED ✓" },
  { type: "detect", text: "Bearish FVG detected: 1.08490 → 1.08561" },
  { type: "verdict", text: "⚡ VERDICT REACHED — SELL at 1.08490 · SL: 1.08762 · TP: 1.07980" },
  { type: "exec", text: "Broadcasting to 54 accounts via Redis..." },
  { type: "exec", text: "54/54 orders filled · Avg latency: 18ms" },
];

const ICON: Record<FeedType, { glyph: string; cls: string }> = {
  scan: { glyph: "⟳", cls: "text-text-muted" },
  detect: { glyph: "◉", cls: "text-amber" },
  confirm: { glyph: "✓", cls: "text-bull" },
  verdict: { glyph: "⚡", cls: "text-brand-blue" },
  exec: { glyph: "⚡", cls: "text-brand-blue" },
};

export function HeroLiveFeed() {
  const [visibleCount, setVisibleCount] = useState(1);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const id = setInterval(() => {
      setVisibleCount((c) => (c >= FEED_MESSAGES.length ? 1 : c + 1));
    }, 2500);
    return () => clearInterval(id);
  }, []);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [visibleCount]);

  const visible = FEED_MESSAGES.slice(0, visibleCount);

  return (
    <div className="font-mono">
      {/* Feed panel */}
      <div
        className="bg-bg-surface border border-border-subtle rounded-xl p-4 text-xs"
        role="log"
        aria-live="polite"
        aria-atomic="false"
      >
        {/* macOS terminal header */}
        <div className="flex items-center gap-2 mb-3">
          <span className="h-2.5 w-2.5 rounded-full" style={{ background: "#FF5F57" }} />
          <span className="h-2.5 w-2.5 rounded-full" style={{ background: "#FEBC2E" }} />
          <span className="h-2.5 w-2.5 rounded-full" style={{ background: "#28C840" }} />
          <span className="ml-2 text-[10px] uppercase tracking-widest text-text-muted">
            live logic feed
          </span>
        </div>

        <div ref={scrollRef} className="h-64 overflow-hidden flex flex-col justify-end">
          {visible.map((msg, i) => {
            const isLast = i === visible.length - 1;
            const icon = ICON[msg.type];
            const verdict = msg.type === "verdict";
            return (
              <div
                key={`${visibleCount}-${i}`}
                className={`flex items-start gap-2 py-1 rounded ${
                  verdict ? "bg-brand-glow px-1.5 -mx-1.5" : ""
                }`}
              >
                <span className={`${icon.cls} shrink-0`}>{icon.glyph}</span>
                <span
                  className={
                    verdict
                      ? "text-brand-blue font-semibold"
                      : "text-text-secondary"
                  }
                >
                  {msg.text}
                  {isLast && <span className="text-brand-blue animate-blink ml-0.5">|</span>}
                </span>
              </div>
            );
          })}
        </div>
      </div>

      {/* Mini stat row */}
      <div className="mt-3 bg-bg-surface border border-border-subtle rounded-xl px-4 py-3 text-xs text-text-secondary flex flex-wrap items-center gap-x-4 gap-y-1">
        <span><span className="text-text-primary font-semibold">54</span> Accounts Active</span>
        <span className="text-text-muted">·</span>
        <span><span className="text-text-primary font-semibold">18ms</span> Avg Latency</span>
        <span className="text-text-muted">·</span>
        <span><span className="text-text-primary font-semibold">0</span> Halted</span>
        <span className="text-text-muted">·</span>
        <span className="flex items-center gap-1.5">
          Engine: <span className="text-bull font-semibold">RUNNING</span>
          <span className="h-2 w-2 rounded-full bg-bull animate-pulse-dot" />
        </span>
      </div>
    </div>
  );
}
