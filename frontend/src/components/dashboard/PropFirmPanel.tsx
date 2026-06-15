import { useMemo } from "react";
import { useTrades } from "../../hooks/useTrades";
import { useMarketStatus } from "../../hooks/useMarketStatus";

export interface PropFirmConfig {
  dailyLossLimit: number;       // dollars
  consecutiveLossLimit: number;
}

const DEFAULT_CONFIG: PropFirmConfig = {
  dailyLossLimit: 1000,
  consecutiveLossLimit: 3,
};

function msUntilUtcMidnight(): string {
  const now = new Date();
  const next = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate() + 1));
  const diff = next.getTime() - now.getTime();
  const h = Math.floor(diff / 3_600_000);
  const m = Math.floor((diff % 3_600_000) / 60_000);
  return `${h}h ${m}m`;
}

/** Prop Firm Constraints panel — derived from the user's closed trades today. */
export function PropFirmPanel({
  config = DEFAULT_CONFIG,
  expanded = false,
}: {
  config?: PropFirmConfig;
  expanded?: boolean;
}) {
  const trades = useTrades();
  const marketOpen = useMarketStatus();

  const stats = useMemo(() => {
    const startOfDay = new Date();
    startOfDay.setUTCHours(0, 0, 0, 0);
    const todayClosed = trades.filter(
      (t) => t.pnl !== null && t.time >= startOfDay.getTime(),
    );
    const dailyLoss = todayClosed
      .filter((t) => (t.pnl ?? 0) < 0)
      .reduce((sum, t) => sum + Math.abs(t.pnl ?? 0), 0);

    // consecutive losses from most-recent closed trades backward
    let consec = 0;
    for (const t of todayClosed.slice().sort((a, b) => b.time - a.time)) {
      if ((t.pnl ?? 0) < 0) consec++;
      else break;
    }

    const wins = todayClosed.filter((t) => (t.pnl ?? 0) >= 0).length;
    const losses = todayClosed.length - wins;
    const winRate = todayClosed.length ? (wins / todayClosed.length) * 100 : 0;

    return { dailyLoss, consec, wins, losses, winRate, count: todayClosed.length };
  }, [trades]);

  const remainingPct = Math.max(
    0,
    ((config.dailyLossLimit - stats.dailyLoss) / config.dailyLossLimit) * 100,
  );
  const barColor =
    remainingPct > 60 ? "bg-bull" : remainingPct >= 30 ? "bg-amber" : "bg-bear animate-pulse-dot";
  const atMaxLosses = stats.consec >= config.consecutiveLossLimit;
  const halted = stats.dailyLoss >= config.dailyLossLimit;

  return (
    <div className="bg-bg-surface border border-border-subtle rounded-lg p-4">
      <div className="flex items-center justify-between">
        <p className="text-xs uppercase tracking-wide text-text-secondary font-mono">
          Prop Firm Constraints
        </p>
      </div>

      {/* Daily drawdown */}
      <div className={`mt-4 ${halted ? "bg-bear-dim -mx-4 px-4 py-3 rounded" : ""}`}>
        <p className="text-xs uppercase tracking-wide text-text-secondary">Daily Drawdown</p>
        <div className="mt-2 h-2 rounded-full bg-bg-elevated overflow-hidden">
          <div className={`h-full rounded-full ${barColor}`} style={{ width: `${remainingPct}%` }} />
        </div>
        <div className="flex justify-between mt-1.5 text-xs text-text-secondary font-mono">
          <span>
            Used: ${stats.dailyLoss.toFixed(0)} of ${config.dailyLossLimit.toFixed(0)}
          </span>
          <span>{remainingPct.toFixed(0)}% remaining</span>
        </div>
        <p className="text-[11px] text-text-muted font-mono mt-1">Resets in {msUntilUtcMidnight()}</p>
      </div>

      {/* Win rate today */}
      <div className="mt-4">
        <p className="text-xs uppercase tracking-wide text-text-secondary">Win Rate · Today</p>
        <p className="font-mono text-text-primary mt-1 text-sm">
          {stats.count ? `${stats.winRate.toFixed(1)}% · ${stats.wins}W / ${stats.losses}L` : "— No closed trades yet"}
        </p>
      </div>

      {/* Consecutive losses */}
      <div className="mt-4">
        <p className="text-xs uppercase tracking-wide text-text-secondary">Consecutive Losses</p>
        <p className="mt-1.5 text-sm flex items-center gap-1.5 font-mono">
          {Array.from({ length: config.consecutiveLossLimit }).map((_, i) => (
            <span key={i} className={i < stats.consec ? "text-bear" : "text-text-muted"}>
              {i < stats.consec ? "●" : "○"}
            </span>
          ))}
          <span className="text-text-secondary ml-1">
            {stats.consec} (Max allowed: {config.consecutiveLossLimit})
          </span>
          {atMaxLosses && (
            <span className="ml-1 text-[10px] uppercase rounded-full bg-bear/15 text-bear border border-bear/30 px-2 py-0.5">
              Caution
            </span>
          )}
        </p>
      </div>

      {/* Engine status */}
      <div className="mt-4">
        <p className="text-xs uppercase tracking-wide text-text-secondary">Engine Status</p>
        {halted ? (
          <p className="mt-1 text-sm flex items-center gap-2 text-bear font-mono">
            ⛔ HALTED — Daily loss limit reached
          </p>
        ) : !marketOpen ? (
          <p className="mt-1 text-sm flex items-center gap-2 text-bear font-mono">
            ● MARKET CLOSED — Engine paused until Sunday 22:00 UTC
          </p>
        ) : (
          <p className="mt-1 text-sm flex items-center gap-2 text-bull font-mono">
            <span className="h-2 w-2 rounded-full bg-bull animate-pulse-dot" /> ACTIVE — No halt conditions met
          </p>
        )}
      </div>

      {expanded && (
        <p className="mt-4 text-xs text-text-muted">
          Limits are enforced by the engine automatically — when the daily loss threshold is reached,
          no new trades are taken until the next UTC day.
        </p>
      )}
    </div>
  );
}
