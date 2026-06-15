import type { ReactNode } from "react";

/**
 * Status badge — color + shape, never color alone (design guide §8 accessibility).
 * Each variant pairs a semantic color with a distinct glyph.
 */
type Variant =
  | "filled" | "rejected" | "error" | "pending"
  | "buy" | "sell"
  | "win" | "loss" | "open"
  | "running" | "halted" | "paused"
  | "ready" | "warn";

const MAP: Record<Variant, { glyph: string; cls: string; label?: string }> = {
  filled:   { glyph: "●", cls: "text-bull bg-bull/10 border-bull/30" },
  rejected: { glyph: "✗", cls: "text-bear bg-bear/10 border-bear/30" },
  error:    { glyph: "⚠", cls: "text-amber bg-amber/10 border-amber/30" },
  pending:  { glyph: "◌", cls: "text-text-muted bg-bg-elevated border-border-muted" },
  buy:      { glyph: "▲", cls: "text-bull bg-bull/10 border-bull/30" },
  sell:     { glyph: "▼", cls: "text-bear bg-bear/10 border-bear/30" },
  win:      { glyph: "●", cls: "text-bull bg-bull/10 border-bull/30" },
  loss:     { glyph: "●", cls: "text-bear bg-bear/10 border-bear/30" },
  open:     { glyph: "◌", cls: "text-brand-blue bg-brand-glow border-brand-blue/30" },
  running:  { glyph: "●", cls: "text-bull bg-bull/10 border-bull/30" },
  halted:   { glyph: "⛔", cls: "text-bear bg-bear/10 border-bear/30" },
  paused:   { glyph: "●", cls: "text-amber bg-amber/10 border-amber/30" },
  ready:    { glyph: "●", cls: "text-bull bg-bull/10 border-bull/30" },
  warn:     { glyph: "⚠", cls: "text-amber bg-amber/10 border-amber/30" },
};

export function StatusBadge({
  variant,
  children,
  pulse = false,
}: {
  variant: Variant;
  children?: ReactNode;
  pulse?: boolean;
}) {
  const { glyph, cls } = MAP[variant];
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-xs font-mono font-medium ${cls}`}
    >
      <span className={pulse ? "animate-pulse-dot" : ""} aria-hidden>{glyph}</span>
      {children ?? variant.toUpperCase()}
    </span>
  );
}
