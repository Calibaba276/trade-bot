import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { StatCard } from "../../components/dashboard/StatCard";
import { StatusBadge } from "../../components/dashboard/StatusBadge";
import { LiveLogicFeed } from "../../components/dashboard/LiveLogicFeed";
import { PropFirmPanel } from "../../components/dashboard/PropFirmPanel";
import { VerdictSidebar } from "../../components/dashboard/VerdictSidebar";
import { EmptyState, Skeleton } from "../../components/dashboard/States";
import { useTrades, type Trade } from "../../hooks/useTrades";
import { useSessionSummaries } from "../../hooks/useSessionSummaries";
import { useMarketStatus } from "../../hooks/useMarketStatus";
import { useAuth } from "../../hooks/useAuth";
import { useTierStore, TIER_FEATURES } from "../../store/tierStore";
import { supabase } from "../../lib/supaclient";
import { fmtMoney, fmtDateTimeWAT, fmtPrice } from "../../utils/format";

export function Overview() {
  const trades = useTrades();
  const marketOpen = useMarketStatus();
  const { user } = useAuth();
  const tier = useTierStore((s) => s.tier);
  const [selected, setSelected] = useState<Trade | null>(null);

  // How many broker accounts the user has connected — drives the onboarding state.
  const [accountCount, setAccountCount] = useState<number | null>(null);
  useEffect(() => {
    if (!user) return;
    let active = true;
    supabase
      .from("broker_accounts")
      .select("id", { count: "exact", head: true })
      .eq("user_id", user.id)
      .then(({ count, error }) => {
        if (active) setAccountCount(error ? 0 : count ?? 0);
      });
    return () => { active = false; };
  }, [user]);

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
  const showPropFirm = TIER_FEATURES[tier].propFirmPanel;
  const sessions = useSessionSummaries(3);

  // First-login onboarding: no broker account connected yet. Give a clear next action.
  if (accountCount === 0) {
    return (
      <div className="h-full overflow-y-auto p-6">
        <div className="bg-bg-surface border border-border-subtle rounded-lg">
          <EmptyState
            icon="🔌"
            title="Connect your first MT5 account"
            body="Glass Box scans your account for ICT setups and logs every decision in real time. Add an MT5 account to get started — the engine begins scanning during the next London session (09:00 NGT)."
            action={
              <Link
                to="/dashboard/settings"
                className="inline-block text-sm bg-brand-blue hover:bg-brand-dim text-white rounded-md px-4 py-2"
              >
                Connect MT5 account →
              </Link>
            }
          />
        </div>
      </div>
    );
  }

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
                ? "Realtime stream connected"
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

      {/* Row 2 — feed + (Pro) prop firm / (Starter) upgrade nudge */}
      <div className="grid grid-cols-1 xl:grid-cols-5 gap-4">
        <div className={showPropFirm ? "xl:col-span-3" : "xl:col-span-5"}>
          <LiveLogicFeed />
        </div>
        {showPropFirm ? (
          <div className="xl:col-span-2">
            <PropFirmPanel />
          </div>
        ) : null}
      </div>

      {/* Starter tier — surface the Pro prop-firm tooling as an upgrade path */}
      {!showPropFirm && (
        <div className="bg-bg-surface border border-brand-blue/30 rounded-lg p-4 flex flex-col sm:flex-row sm:items-center gap-3 justify-between">
          <div>
            <p className="text-sm font-semibold text-text-primary flex items-center gap-2">
              <span className="text-brand-blue" aria-hidden>★</span> Running a prop firm challenge?
            </p>
            <p className="text-xs text-text-secondary mt-1 max-w-xl">
              Pro adds the Prop Firm Panel — live daily-drawdown tracking, consecutive-loss limits,
              halt simulation and profit-target progress — plus up to {TIER_FEATURES.pro.maxAccounts} accounts.
            </p>
          </div>
          <Link
            to="/dashboard/settings"
            className="shrink-0 text-sm bg-brand-blue hover:bg-brand-dim text-white rounded-md px-4 py-2 text-center"
          >
            Upgrade to Pro
          </Link>
        </div>
      )}

      {/* Row 3 — session summary cards (auto-generated after each session closes) */}
      {sessions.length > 0 && (
        <div>
          <p className="text-[10px] uppercase tracking-wider text-text-muted font-mono mb-2">Session Summaries</p>
          <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-3">
            {sessions.map((s) => (
              <div
                key={s.key}
                className={`bg-bg-surface border rounded-lg px-4 py-3 text-xs font-mono ${
                  s.halted ? "border-bear/40 bg-bear-dim" : "border-border-subtle"
                }`}
              >
                <div className="flex items-center justify-between mb-1.5">
                  <span className="text-text-primary font-semibold">{s.session} Session</span>
                  <span className="text-text-muted">{s.date}</span>
                </div>
                <p className="text-text-secondary leading-relaxed">
                  {s.scans} scan{s.scans !== 1 ? "s" : ""} · {s.verdicts} verdict{s.verdicts !== 1 ? "s" : ""} · {s.executedTrades} trade{s.executedTrades !== 1 ? "s" : ""} executed
                  {s.executedTrades > 0 && (
                    <span className={s.pnl >= 0 ? " text-bull" : " text-bear"}>
                      {" "}{s.pnl >= 0 ? "+" : "-"}${Math.abs(s.pnl).toFixed(0)}
                    </span>
                  )}
                  {s.halted ? (
                    <span className="text-bear"> · Engine halted</span>
                  ) : (
                    <span className="text-text-muted"> · No halt conditions triggered</span>
                  )}
                </p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Row 4 — recent signals */}
      <div className="bg-bg-surface border border-border-subtle rounded-lg">
        <div className="flex items-center justify-between px-4 h-11 border-b border-border-subtle">
          <span className="text-xs uppercase tracking-wide text-text-secondary font-mono">Recent Signals</span>
          <Link to="/dashboard/trades" className="text-xs text-brand-blue hover:underline">View all →</Link>
        </div>
        {accountCount === null ? (
          <div className="p-4 space-y-2">
            <Skeleton className="h-8" /><Skeleton className="h-8" /><Skeleton className="h-8" />
          </div>
        ) : recent.length === 0 ? (
          <EmptyState
            title="No trades yet"
            body="The engine will log trades here as signals are detected and executed."
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="text-text-muted">
                  {["Time (WAT)", "Symbol", "Direction", "Entry", "R:R", "Status", "Setup", ""].map((h) => (
                    <th key={h} className="text-left font-normal font-mono px-4 py-2 border-b border-border-subtle whitespace-nowrap">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="font-mono">
                {recent.map((t) => (
                  <tr
                    key={t.id}
                    onClick={() => setSelected(t)}
                    className="border-b border-border-subtle/50 hover:bg-bg-elevated cursor-pointer"
                  >
                    <td className="px-4 py-2 text-text-muted whitespace-nowrap">{fmtDateTimeWAT(t.time)}</td>
                    <td className="px-4 py-2 text-text-primary">{t.pair}</td>
                    <td className="px-4 py-2"><StatusBadge variant={t.direction === "BUY" ? "buy" : "sell"}>{t.direction}</StatusBadge></td>
                    <td className="px-4 py-2 text-text-primary">{fmtPrice(t.entry, t.pair)}</td>
                    <td className="px-4 py-2 text-text-secondary">{t.rr.toFixed(1)}R</td>
                    <td className="px-4 py-2"><StatusBadge variant={t.status === "OPEN" ? "open" : t.status === "WIN" ? "win" : "loss"}>{t.status}</StatusBadge></td>
                    <td className="px-4 py-2 text-text-secondary">{t.setup}</td>
                    <td className="px-4 py-2 text-right">
                      <span className="text-brand-blue hover:underline text-[11px]">Verdict →</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <VerdictSidebar trade={selected} onClose={() => setSelected(null)} />
    </div>
  );
}
