import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { resolveShare, type SharePayload } from "../utils/share";
import { StatusBadge } from "../components/dashboard/StatusBadge";
import { VerdictSidebar } from "../components/dashboard/VerdictSidebar";
import { EmptyState } from "../components/dashboard/States";
import { fmtDateTimeWAT, fmtPrice, fmtMoney } from "../utils/format";
import type { Trade } from "../hooks/useTrades";

export function SharePage() {
  const { token } = useParams<{ token: string }>();
  const [selected, setSelected] = useState<Trade | null>(null);
  const [result, setResult] = useState<{ payload: SharePayload; trades: Trade[] } | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    setLoading(true);
    if (!token) {
      setResult(null);
      setLoading(false);
      return;
    }
    resolveShare(token)
      .then((r) => active && setResult(r))
      .finally(() => active && setLoading(false));
    return () => {
      active = false;
    };
  }, [token]);

  if (loading) {
    return (
      <div className="min-h-screen bg-bg-base flex items-center justify-center p-6">
        <div className="text-center">
          <p className="text-4xl mb-4 text-brand-blue animate-pulse-dot" aria-hidden>⬡</p>
          <p className="text-sm text-text-secondary font-mono">Loading audit trail…</p>
        </div>
      </div>
    );
  }

  if (!result) {
    return (
      <div className="min-h-screen bg-bg-base flex items-center justify-center p-6">
        <div className="text-center">
          <p className="text-4xl mb-4 text-brand-blue" aria-hidden>⬡</p>
          <h1 className="text-lg font-semibold text-text-primary mb-2">Audit link not found</h1>
          <p className="text-sm text-text-secondary">This link may have expired or been modified.</p>
          <Link to="/" className="mt-4 inline-block text-sm text-brand-blue hover:underline">
            Go to Glass Box →
          </Link>
        </div>
      </div>
    );
  }

  const { payload, trades } = result;
  const wins = trades.filter((t) => t.status === "WIN").length;
  const losses = trades.filter((t) => t.status === "LOSS").length;
  const totalPnl = trades.filter((t) => t.pnl !== null).reduce((s, t) => s + (t.pnl ?? 0), 0);
  const winRate = wins + losses > 0 ? (wins / (wins + losses)) * 100 : 0;
  const hasPnl = wins + losses > 0;
  const createdDate = new Date(payload.createdAt).toLocaleDateString("en-GB", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });

  const stats = [
    { label: "Trades", value: String(trades.length), cls: "" },
    { label: "Win Rate", value: hasPnl ? `${winRate.toFixed(1)}%` : "—", cls: "" },
    { label: "Wins / Losses", value: `${wins}W / ${losses}L`, cls: "" },
    {
      label: "Net P/L",
      value: hasPnl ? fmtMoney(totalPnl) : "—",
      cls: !hasPnl ? "" : totalPnl >= 0 ? "text-bull" : "text-bear",
    },
  ];

  return (
    <div className="min-h-screen bg-bg-base text-text-primary">
      {/* Header */}
      <header className="bg-bg-surface border-b border-border-subtle px-4 md:px-8 h-14 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span className="text-brand-blue font-bold text-lg" aria-hidden>⬡</span>
          <span className="font-display font-bold tracking-widest text-sm">GLASS BOX</span>
          <span className="text-border-subtle mx-1" aria-hidden>·</span>
          <span className="text-xs font-mono text-text-muted uppercase tracking-wide">Shared Audit Trail</span>
        </div>
        <Link
          to="/sign-up"
          className="text-xs bg-brand-blue hover:bg-brand-dim text-white rounded-md px-3 py-1.5"
        >
          Check Out Glass Box
        </Link>
      </header>

      <div className="max-w-5xl mx-auto px-4 md:px-8 py-8">
        {/* Title + meta */}
        <div className="mb-6">
          <h1 className="text-xl font-semibold text-text-primary">{payload.title}</h1>
          <p className="text-xs text-text-muted font-mono mt-1">
            Shared on {createdDate} · Read-only audit view · All times in WAT (UTC+1)
          </p>
        </div>

        {/* Summary stat strip */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-6">
          {stats.map((s) => (
            <div key={s.label} className="bg-bg-surface border border-border-subtle rounded-lg p-4">
              <p className="text-[10px] uppercase tracking-wide text-text-muted font-mono">{s.label}</p>
              <p className={`text-xl font-mono font-semibold mt-1 ${s.cls || "text-text-primary"}`}>{s.value}</p>
            </div>
          ))}
        </div>

        {/* Trade table */}
        <div className="bg-bg-surface border border-border-subtle rounded-lg overflow-hidden">
          {trades.length === 0 ? (
            <EmptyState
              title="No trades in this audit"
              body="The shared session contains no trade records."
            />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="text-text-muted">
                    {["Time (WAT)", "Symbol", "Direction", "Entry", "Stop Loss", "TP", "R:R", "P/L", "Status", "Scenario", ""].map((h) => (
                      <th key={h} className="text-left font-normal font-mono px-4 py-2.5 border-b border-border-subtle whitespace-nowrap">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody className="font-mono">
                  {trades.map((t) => (
                    <tr
                      key={t.id}
                      onClick={() => setSelected(t)}
                      className="border-b border-border-subtle/50 hover:bg-bg-elevated cursor-pointer"
                    >
                      <td className="px-4 py-2.5 text-text-muted whitespace-nowrap">{fmtDateTimeWAT(t.time)}</td>
                      <td className="px-4 py-2.5 text-text-primary">{t.pair}</td>
                      <td className="px-4 py-2.5">
                        <StatusBadge variant={t.direction === "BUY" ? "buy" : "sell"}>{t.direction}</StatusBadge>
                      </td>
                      <td className="px-4 py-2.5 text-text-primary">{fmtPrice(t.entry, t.pair)}</td>
                      <td className="px-4 py-2.5 text-bear">{t.sl ? fmtPrice(t.sl, t.pair) : "—"}</td>
                      <td className="px-4 py-2.5 text-bull">{t.tp ? fmtPrice(t.tp, t.pair) : "—"}</td>
                      <td className="px-4 py-2.5 text-text-secondary">{t.rr.toFixed(1)}R</td>
                      <td className={`px-4 py-2.5 ${t.pnl === null ? "text-text-muted" : t.pnl >= 0 ? "text-bull" : "text-bear"}`}>
                        {t.pnl === null ? "—" : fmtMoney(t.pnl)}
                      </td>
                      <td className="px-4 py-2.5">
                        <StatusBadge variant={t.status === "OPEN" ? "open" : t.status === "WIN" ? "win" : "loss"}>
                          {t.status}
                        </StatusBadge>
                      </td>
                      <td className="px-4 py-2.5">
                        <span className="bg-bg-elevated text-text-secondary rounded-full px-2 py-0.5 text-[11px]">{t.setup}</span>
                      </td>
                      <td className="px-4 py-2.5">
                        <button
                          onClick={(e) => { e.stopPropagation(); setSelected(t); }}
                          className="text-brand-blue hover:underline text-[11px]"
                        >
                          Verdict →
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Footer CTA */}
        <div className="mt-10 text-center py-8 border-t border-border-subtle">
          <p className="text-xs text-text-muted font-mono tracking-widest mb-3">
            GLASS BOX · SEE EVERYTHING. TRUST WHAT YOU SEE.
          </p>
          <p className="text-sm text-text-secondary mb-5 max-w-md mx-auto">
            Glass Box logs every ICT pattern scanned, every condition verified, every order placed — so you always know exactly what the bot did and why.
          </p>
          <Link
            to="/sign-up"
            className="inline-block text-sm bg-brand-blue hover:bg-brand-dim text-white rounded-md px-5 py-2.5"
          >
            Start your Glass Box →
          </Link>
        </div>
      </div>

      <VerdictSidebar trade={selected} onClose={() => setSelected(null)} />
    </div>
  );
}
