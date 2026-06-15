import { useMemo } from "react";
import { Link } from "react-router-dom";
import { StatCard } from "../../components/dashboard/StatCard";
import { StatusBadge } from "../../components/dashboard/StatusBadge";
import { LiveLogicFeed } from "../../components/dashboard/LiveLogicFeed";
import { PropFirmPanel } from "../../components/dashboard/PropFirmPanel";
import { EmptyState } from "../../components/dashboard/States";
import { useTrades } from "../../hooks/useTrades";
import { useMarketStatus } from "../../hooks/useMarketStatus";
import { fmtMoney, fmtDateTimeWAT, fmtPrice } from "../../utils/format";

export function Overview() {
  const trades = useTrades();
  const marketOpen = useMarketStatus();

  const stats = useMemo(() => {
    const startOfDay = new Date();
    startOfDay.setUTCHours(0, 0, 0, 0);
    const closed = trades.filter((t) => t.pnl !== null);
    const open = trades.filter((t) => t.pnl === null);
    const todayClosed = closed.filter((t) => t.time >= startOfDay.getTime());
    const todayPnl = todayClosed.reduce((s, t) => s + (t.pnl ?? 0), 0);

    const monthAgo = Date.now() - 30 * 86_400_000;
    const monthClosed = closed.filter((t) => t.time >= monthAgo);
    const wins = monthClosed.filter((t) => (t.pnl ?? 0) >= 0).length;
    const winRate = monthClosed.length ? (wins / monthClosed.length) * 100 : 0;

    return {
      todayPnl,
      todayCount: todayClosed.length,
      openCount: open.length,
      winRate,
      wins,
      losses: monthClosed.length - wins,
      monthCount: monthClosed.length,
    };
  }, [trades]);

  const recent = trades.slice(0, 6);

  return (
    <div className="h-full overflow-y-auto p-6 space-y-6">
      {/* Row 1 — stat cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
        <StatCard
          label="Engine Status"
          value={
            marketOpen ? (
              <span className="text-bull">RUNNING</span>
            ) : (
              <span className="text-bear">MARKET CLOSED</span>
            )
          }
          sub={
            <span>
              {marketOpen
                ? "Uptime 99.7% · realtime stream connected"
                : "Forex market is offline — engine paused"}
            </span>
          }
        />
        <StatCard
          label="Today's P&L"
          value={stats.todayCount ? fmtMoney(stats.todayPnl) : "—"}
          valueClass={stats.todayPnl >= 0 ? "text-bull" : "text-bear"}
          sub={<span>{stats.todayCount} closed trade{stats.todayCount === 1 ? "" : "s"} today</span>}
        />
        <StatCard
          label="Open Positions"
          value={String(stats.openCount)}
          sub={<span>{stats.openCount === 0 ? "No active positions" : "Live in market"}</span>}
        />
        <StatCard
          label="Win Rate · 30d"
          value={stats.monthCount ? `${stats.winRate.toFixed(1)}%` : "—"}
          sub={<span>{stats.wins}W / {stats.losses}L · {stats.monthCount} trades</span>}
        >
          <div className="mt-3 h-1.5 rounded-full bg-bg-elevated overflow-hidden">
            <div className="h-full bg-bull rounded-full" style={{ width: `${stats.winRate}%` }} />
          </div>
        </StatCard>
      </div>

      {/* Row 2 — feed + prop firm */}
      <div className="grid grid-cols-1 xl:grid-cols-5 gap-4">
        <div className="xl:col-span-3">
          <LiveLogicFeed />
        </div>
        <div className="xl:col-span-2">
          <PropFirmPanel />
        </div>
      </div>

      {/* Row 3 — recent signals */}
      <div className="bg-bg-surface border border-border-subtle rounded-lg">
        <div className="flex items-center justify-between px-4 h-11 border-b border-border-subtle">
          <span className="text-xs uppercase tracking-wide text-text-secondary font-mono">Recent Signals</span>
          <Link to="/dashboard/trades" className="text-xs text-brand-blue hover:underline">View all →</Link>
        </div>
        {recent.length === 0 ? (
          <EmptyState
            title="No trades yet"
            body="The engine will log trades here as signals are detected and executed."
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="text-text-muted">
                  {["Time (WAT)", "Symbol", "Direction", "Entry", "R:R", "Status", "Setup"].map((h) => (
                    <th key={h} className="text-left font-normal font-mono px-4 py-2 border-b border-border-subtle whitespace-nowrap">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="font-mono">
                {recent.map((t) => (
                  <tr key={t.id} className="border-b border-border-subtle/50 hover:bg-bg-elevated">
                    <td className="px-4 py-2 text-text-muted whitespace-nowrap">{fmtDateTimeWAT(t.time)}</td>
                    <td className="px-4 py-2 text-text-primary">{t.pair}</td>
                    <td className="px-4 py-2"><StatusBadge variant={t.direction === "BUY" ? "buy" : "sell"}>{t.direction}</StatusBadge></td>
                    <td className="px-4 py-2 text-text-primary">{fmtPrice(t.entry, t.pair)}</td>
                    <td className="px-4 py-2 text-text-secondary">{t.rr.toFixed(1)}R</td>
                    <td className="px-4 py-2"><StatusBadge variant={t.status === "OPEN" ? "open" : t.status === "WIN" ? "win" : "loss"}>{t.status}</StatusBadge></td>
                    <td className="px-4 py-2 text-text-secondary">{t.setup}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
