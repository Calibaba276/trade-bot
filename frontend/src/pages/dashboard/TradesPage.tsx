import { useMemo, useState } from "react";
import { StatusBadge } from "../../components/dashboard/StatusBadge";
import { EmptyState } from "../../components/dashboard/States";
import { VerdictSidebar } from "../../components/dashboard/VerdictSidebar";
import { useTrades, type Trade } from "../../hooks/useTrades";
import { fmtDateTimeWAT, fmtPrice, fmtMoney } from "../../utils/format";
import { buildShareUrl } from "../../utils/share";
import { useTierStore } from "../../store/tierStore";
import { useToastStore } from "../../store/toastStore";

const PAGE_SIZE = 25;

type DirFilter = "All" | "BUY" | "SELL";
type StatusFilter = "All" | "WIN" | "LOSS" | "OPEN";

function toDateInputValue(date: Date) {
  return date.toISOString().slice(0, 10);
}

function exportCsv(rows: Trade[]) {
  const header = ["Time (WAT)", "Symbol", "Direction", "Entry", "SL", "TP", "RR", "PnL", "Status", "Setup"];
  const lines = rows.map((t) =>
    [
      fmtDateTimeWAT(t.time), t.pair, t.direction, t.entry, t.sl, t.tp,
      t.rr, t.pnl ?? "", t.status, t.setup,
    ].join(","),
  );
  const blob = new Blob([[header.join(","), ...lines].join("\n")], { type: "text/csv" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `glassbox-trades-${Date.now()}.csv`;
  a.click();
  URL.revokeObjectURL(url);
}

export function TradesPage() {
  const all = useTrades();
  const tier = useTierStore((s) => s.tier);
  const push = useToastStore((s) => s.push);
  const [dir, setDir] = useState<DirFilter>("All");
  const [status, setStatus] = useState<StatusFilter>("All");
  const [scenario, setScenario] = useState("All");
  const [page, setPage] = useState(0);
  const [selected, setSelected] = useState<Trade | null>(null);
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");

  const scenarios = useMemo(
    () => ["All", ...Array.from(new Set(all.map((t) => t.setup))).filter((s) => s && s !== "—")],
    [all],
  );

  const filtered = useMemo(
    () =>
      all.filter((t) => {
        const tDate = t.time ? t.time.slice(0, 10) : "";
        return (
          (dir === "All" || t.direction === dir) &&
          (status === "All" || t.status === status) &&
          (scenario === "All" || t.setup === scenario) &&
          (!dateFrom || tDate >= dateFrom) &&
          (!dateTo || tDate <= dateTo)
        );
      }),
    [all, dir, status, scenario, dateFrom, dateTo],
  );

  const pageCount = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const rows = filtered.slice(page * PAGE_SIZE, page * PAGE_SIZE + PAGE_SIZE);

  const Select = ({ value, onChange, options }: { value: string; onChange: (v: string) => void; options: string[] }) => (
    <select
      value={value}
      onChange={(e) => { onChange(e.target.value); setPage(0); }}
      className="bg-bg-elevated border border-border-muted rounded-md text-xs text-text-primary px-2.5 py-1.5 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-blue"
    >
      {options.map((o) => <option key={o} value={o}>{o}</option>)}
    </select>
  );

  return (
    <div className="h-full overflow-y-auto p-6">
      {/* filters */}
      <div className="flex flex-wrap items-center gap-3 mb-4">
        <Select value={dir} onChange={(v) => setDir(v as DirFilter)} options={["All", "BUY", "SELL"]} />
        <Select value={status} onChange={(v) => setStatus(v as StatusFilter)} options={["All", "WIN", "LOSS", "OPEN"]} />
        <Select value={scenario} onChange={setScenario} options={scenarios} />
        <div className="flex items-center gap-1.5">
          <input
            type="date"
            value={dateFrom}
            onChange={(e) => { setDateFrom(e.target.value); setPage(0); }}
            max={dateTo || toDateInputValue(new Date())}
            className="bg-bg-elevated border border-border-muted rounded-md text-xs text-text-primary px-2 py-1.5 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-blue"
          />
          <span className="text-text-muted text-xs">–</span>
          <input
            type="date"
            value={dateTo}
            onChange={(e) => { setDateTo(e.target.value); setPage(0); }}
            min={dateFrom}
            max={toDateInputValue(new Date())}
            className="bg-bg-elevated border border-border-muted rounded-md text-xs text-text-primary px-2 py-1.5 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-blue"
          />
        </div>
        <div className="ml-auto flex items-center gap-3">
          <span className="text-xs text-text-muted">{filtered.length} trade{filtered.length === 1 ? "" : "s"}</span>
          {tier === "starter" && (
            <button
              onClick={() => {
                if (!filtered.length) return;
                const url = buildShareUrl(filtered, "Glass Box Audit Trail");
                navigator.clipboard.writeText(url).then(() => {
                  push({ variant: "success", title: "Share link copied", body: "Send this link to your signal provider — no account needed to view.", durationMs: 7000 });
                }).catch(() => {
                  push({ variant: "info", title: "Share link ready", body: url, durationMs: 10000 });
                });
              }}
              disabled={!filtered.length}
              title="Generate a public read-only link to this trade history"
              className="text-xs border border-brand-blue/50 hover:border-brand-blue bg-brand-blue/10 text-brand-blue rounded-md px-3 py-1.5 disabled:opacity-40"
            >
              Share Audit ↗
            </button>
          )}
          <button
            onClick={() => exportCsv(filtered)}
            disabled={!filtered.length}
            className="text-xs border border-border-muted hover:border-border-active text-text-primary rounded-md px-3 py-1.5 disabled:opacity-40"
          >
            Export CSV
          </button>
        </div>
      </div>

      <div className="bg-bg-surface border border-border-subtle rounded-lg overflow-hidden">
        {filtered.length === 0 ? (
          <EmptyState
            title="No trades match these filters"
            body="Adjust the filters above, or wait for the engine to log new signals."
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
                {rows.map((t) => (
                  <tr key={t.id} className="border-b border-border-subtle/50 hover:bg-bg-elevated">
                    <td className="px-4 py-2.5 text-text-muted whitespace-nowrap">{fmtDateTimeWAT(t.time)}</td>
                    <td className="px-4 py-2.5 text-text-primary">{t.pair}</td>
                    <td className="px-4 py-2.5"><StatusBadge variant={t.direction === "BUY" ? "buy" : "sell"}>{t.direction}</StatusBadge></td>
                    <td className="px-4 py-2.5 text-text-primary">{fmtPrice(t.entry, t.pair)}</td>
                    <td className="px-4 py-2.5 text-bear">{t.sl ? fmtPrice(t.sl, t.pair) : "—"}</td>
                    <td className="px-4 py-2.5 text-bull">{t.tp ? fmtPrice(t.tp, t.pair) : "—"}</td>
                    <td className="px-4 py-2.5 text-text-secondary">{t.rr.toFixed(1)}R</td>
                    <td className={`px-4 py-2.5 ${t.pnl === null ? "text-text-muted" : t.pnl >= 0 ? "text-bull" : "text-bear"}`}>
                      {t.pnl === null ? "—" : fmtMoney(t.pnl)}
                    </td>
                    <td className="px-4 py-2.5"><StatusBadge variant={t.status === "OPEN" ? "open" : t.status === "WIN" ? "win" : "loss"}>{t.status}</StatusBadge></td>
                    <td className="px-4 py-2.5">
                      <span className="bg-bg-elevated text-text-secondary rounded-full px-2 py-0.5 text-[11px]">{t.setup}</span>
                    </td>
                    <td className="px-4 py-2.5">
                      <button
                        onClick={() => setSelected(t)}
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

      {/* pagination */}
      {pageCount > 1 && (
        <div className="flex items-center justify-center gap-2 mt-4 text-xs">
          <button
            onClick={() => setPage((p) => Math.max(0, p - 1))}
            disabled={page === 0}
            className="px-3 py-1.5 rounded-md border border-border-muted disabled:opacity-40 hover:border-border-active"
          >
            ← Prev
          </button>
          <span className="text-text-secondary font-mono">Page {page + 1} of {pageCount}</span>
          <button
            onClick={() => setPage((p) => Math.min(pageCount - 1, p + 1))}
            disabled={page >= pageCount - 1}
            className="px-3 py-1.5 rounded-md border border-border-muted disabled:opacity-40 hover:border-border-active"
          >
            Next →
          </button>
        </div>
      )}

      <VerdictSidebar trade={selected} onClose={() => setSelected(null)} />
    </div>
  );
}
