import { LiveLogicFeed } from "../../components/dashboard/LiveLogicFeed";
import { useSessionSummaries } from "../../hooks/useSessionSummaries";

export function FeedPage() {
  const sessions = useSessionSummaries(1);
  const latest = sessions[0] ?? null;

  return (
    <div className="h-full overflow-y-auto p-6">
      <p className="text-sm text-text-secondary mb-4 max-w-2xl">
        Every pattern scanned, every condition verified, every order logged — timestamped in West Africa Time. This is the full audit trail.
      </p>

      {/* Pinned: most recent completed session summary */}
      {latest && (
        <div
          className={`mb-4 flex items-center justify-between gap-4 rounded-lg border px-4 py-2.5 text-xs font-mono ${
            latest.halted
              ? "border-bear/40 bg-bear-dim text-bear"
              : "border-border-subtle bg-bg-surface text-text-secondary"
          }`}
        >
          <span>
            <span className="text-text-primary font-semibold mr-2">{latest.session} Session · {latest.date}</span>
            {latest.scans} scans · {latest.verdicts} verdict{latest.verdicts !== 1 ? "s" : ""} · {latest.executedTrades} trade{latest.executedTrades !== 1 ? "s" : ""} executed
            {latest.executedTrades > 0 && (
              <span className={latest.pnl >= 0 ? " text-bull" : " text-bear"}>
                {" "}{latest.pnl >= 0 ? "+" : "-"}${Math.abs(latest.pnl).toFixed(0)}
              </span>
            )}
            {latest.halted
              ? <span className="text-bear"> · ⛔ Engine halted</span>
              : <span className="text-text-muted"> · No halt conditions triggered</span>}
          </span>
          <span className="shrink-0 text-[10px] uppercase tracking-wide text-text-muted">Last session</span>
        </div>
      )}

      <LiveLogicFeed heightClass="h-[calc(100vh-300px)]" showMarketTabs />
    </div>
  );
}
