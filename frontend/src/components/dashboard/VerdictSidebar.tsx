import { useEffect } from "react";
import type { Trade } from "../../hooks/useTrades";
import { StatusBadge } from "./StatusBadge";
import { shortId, fmtDateTimeWAT, fmtPrice } from "../../utils/format";

/** A single ICT condition row — `–` (muted) when not applicable, `✓` when present. */
function CondRow({ label, value }: { label: string; value: string | number | null | undefined }) {
  const present = value !== null && value !== undefined && value !== "" && value !== 0;
  return (
    <div className="flex items-center justify-between gap-2 text-xs py-1 border-b border-border-subtle/40 last:border-0">
      <span className="flex items-center gap-1.5">
        <span className={present ? "text-bull" : "text-text-muted"} aria-hidden>{present ? "✓" : "–"}</span>
        <span className="text-text-secondary font-mono">{label}</span>
      </span>
      <span className="font-mono text-text-primary">{present ? value : "–"}</span>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="mt-5">
      <p className="text-[10px] uppercase tracking-wider text-text-muted border-b border-border-subtle pb-1.5">{title}</p>
      <div className="mt-2">{children}</div>
    </div>
  );
}

/**
 * Verdict Sidebar (design guide §6.5 / §14.2 — "the Verdict Sidebar is the product").
 * Slides in from the right when a trade is selected.
 */
export function VerdictSidebar({ trade, onClose }: { trade: Trade | null; onClose: () => void }) {
  // Close on Escape.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const open = trade !== null;
  const m = trade?.entryEvent.metadata ?? {};
  const pip = (a?: number, b?: number) =>
    a != null && b != null && trade ? Math.abs(a - b) * (trade.pair.includes("JPY") ? 100 : 10000) : null;
  const riskPips = pip(trade?.entry, trade?.sl);
  const rewardPips = pip(trade?.entry, trade?.tp);
  const num = (v: unknown) => (typeof v === "number" ? v : undefined);

  return (
    <div
      className={`fixed top-0 right-0 h-full w-80 max-w-[90vw] z-50 bg-bg-overlay border-l border-border-muted overflow-y-auto transition-transform duration-300 ease-out ${
        open ? "translate-x-0" : "translate-x-full"
      }`}
      role="dialog"
      aria-label="Trade verdict details"
      aria-hidden={!open}
    >
      {trade && (
        <div className="p-5 font-sans">
          {/* header */}
          <div className="flex items-center justify-between">
            <p className="text-xs uppercase tracking-wide text-text-muted font-mono">
              Verdict · {shortId(trade.signalId ?? trade.id)}
            </p>
            <button
              onClick={onClose}
              aria-label="Close verdict panel"
              className="text-text-muted hover:text-text-primary text-lg leading-none"
            >
              ✕
            </button>
          </div>

          <div className="mt-3 flex items-center gap-2">
            <StatusBadge variant={trade.direction === "BUY" ? "buy" : "sell"}>{trade.direction}</StatusBadge>
            <span className="text-sm text-text-secondary">{trade.setup}</span>
          </div>
          <p className="text-xs text-text-muted font-mono mt-1">
            {trade.pair} · {fmtDateTimeWAT(trade.time)} WAT
          </p>

          <Section title="Price Levels">
            <div className="space-y-1 text-xs font-mono">
              <div className="flex justify-between"><span className="text-text-secondary">Entry</span><span className="text-text-primary">{fmtPrice(trade.entry, trade.pair)}</span></div>
              <div className="flex justify-between"><span className="text-text-secondary">Stop Loss</span><span className="text-bear">{trade.sl ? fmtPrice(trade.sl, trade.pair) : "–"}</span></div>
              <div className="flex justify-between"><span className="text-text-secondary">Take Profit</span><span className="text-bull">{trade.tp ? fmtPrice(trade.tp, trade.pair) : "–"}</span></div>
              {riskPips != null && <div className="flex justify-between"><span className="text-text-secondary">Risk</span><span className="text-text-primary">{riskPips.toFixed(1)} pips</span></div>}
              {rewardPips != null && <div className="flex justify-between"><span className="text-text-secondary">Reward</span><span className="text-text-primary">{rewardPips.toFixed(1)} pips</span></div>}
              <div className="flex justify-between"><span className="text-text-secondary">R:R Ratio</span><span className="text-brand-blue">{trade.rr.toFixed(2)}R</span></div>
            </div>
          </Section>

          <Section title="ICT Conditions">
            <CondRow label="swept_high" value={num(m.swept_high) ? fmtPrice(num(m.swept_high)!, trade.pair) : null} />
            <CondRow label="swept_low" value={num(m.swept_low) ? fmtPrice(num(m.swept_low)!, trade.pair) : null} />
            <CondRow label="mss_confirmed" value={m.mss_confirmed ? "Yes" : null} />
            <CondRow label="fvg_confirmed" value={m.fvg_confirmed ? "Yes" : null} />
            <CondRow label="fvg_top" value={num(m.fvg_top) ? fmtPrice(num(m.fvg_top)!, trade.pair) : null} />
            <CondRow label="fvg_bottom" value={num(m.fvg_bottom) ? fmtPrice(num(m.fvg_bottom)!, trade.pair) : null} />
            <CondRow label="mss_level" value={num(m.mss_level) ? fmtPrice(num(m.mss_level)!, trade.pair) : null} />
            <CondRow label="sweep_point" value={num(m.sweep_point) ? fmtPrice(num(m.sweep_point)!, trade.pair) : null} />
            <CondRow label="pdh" value={num(m.pdh) ? fmtPrice(num(m.pdh)!, trade.pair) : null} />
            <CondRow label="pdl" value={num(m.pdl) ? fmtPrice(num(m.pdl)!, trade.pair) : null} />
          </Section>

          <Section title="Execution">
            <div className="space-y-1 text-xs font-mono">
              <div className="flex justify-between"><span className="text-text-secondary">Accounts Fired</span><span className="text-text-primary">{num(m.accounts_fired) ?? "–"}</span></div>
              <div className="flex justify-between"><span className="text-text-secondary">Avg Latency</span><span className="text-text-primary">{num(m.latency_ms) != null ? `${num(m.latency_ms)}ms` : "–"}</span></div>
              <div className="flex justify-between items-center">
                <span className="text-text-secondary">Status</span>
                <StatusBadge variant={trade.status === "OPEN" ? "open" : "filled"}>
                  {trade.status === "OPEN" ? "OPEN" : "FILLED"}
                </StatusBadge>
              </div>
            </div>
          </Section>

          {trade.pnl !== null && (
            <Section title="Outcome">
              <div className="flex justify-between text-xs font-mono">
                <span className="text-text-secondary">Realized P/L</span>
                <span className={trade.pnl >= 0 ? "text-bull" : "text-bear"}>
                  {trade.pnl >= 0 ? "+" : "-"}${Math.abs(trade.pnl).toFixed(0)}
                </span>
              </div>
            </Section>
          )}
        </div>
      )}
    </div>
  );
}
