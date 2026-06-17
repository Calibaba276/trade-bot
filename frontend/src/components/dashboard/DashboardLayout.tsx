import { useEffect, useMemo, useRef, useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import { useAuth } from "../../hooks/useAuth";
import { signOut } from "../../lib/supaclient";
import { useReplayStore } from "../../store/replayStore";
import { useLiveTradeEvents } from "../../hooks/useLiveTradeEvents";
import { useTrades } from "../../hooks/useTrades";
import { StatusBadge } from "./StatusBadge";
import { ToastContainer } from "./ToastContainer";
import { useMarketStatus } from "../../hooks/useMarketStatus";
import { useTierStore, TIER_FEATURES } from "../../store/tierStore";
import { useToastStore } from "../../store/toastStore";

/* --- sidebar nav config (design guide §6.1) --- */
const NAV = [
  { to: "/dashboard", label: "Overview", icon: "▦", end: true },
  { to: "/dashboard/feed", label: "Live Feed", icon: "≋" },
  { to: "/dashboard/chart", label: "Replay Mode", icon: "▷" },
  { to: "/dashboard/trades", label: "Trade History", icon: "≡" },
  { to: "/dashboard/propfirm", label: "Prop Firm Panel", icon: "◈" },
  { to: "/dashboard/settings", label: "Account Settings", icon: "⚙" },
];

const PAGE_TITLES: Record<string, string> = {
  "/dashboard": "Overview",
  "/dashboard/feed": "Live Feed",
  "/dashboard/chart": "Replay Mode",
  "/dashboard/trades": "Trade History",
  "/dashboard/propfirm": "Prop Firm Panel",
  "/dashboard/settings": "Account Settings",
};

const PROPFIRM_CONFIG_KEY = "propfirm_config_v1";

function readDailyLimit(): number {
  try {
    const raw = localStorage.getItem(PROPFIRM_CONFIG_KEY);
    if (raw) return JSON.parse(raw)?.dailyLimit ?? 1000;
  } catch { /* ignore */ }
  return 1000;
}

export function DashboardLayout() {
  const { user } = useAuth();
  const location = useLocation();
  const [menuOpen, setMenuOpen] = useState(false);
  const [mobileNav, setMobileNav] = useState(false);
  const [collapsed, setCollapsed] = useState(false);
  const marketOpen = useMarketStatus();
  const push = useToastStore((s) => s.push);
  const prevMarketOpen = useRef<boolean | null>(null);
  const tier = useTierStore((s) => s.tier);
  const toggleTier = useTierStore((s) => s.toggleTier);

  // Compute engine halt state from today's trades vs the configured daily loss limit.
  const trades = useTrades();
  const engineHalted = useMemo(() => {
    const limit = readDailyLimit();
    const startOfDay = new Date();
    startOfDay.setUTCHours(0, 0, 0, 0);
    const dailyLoss = trades
      .filter((t) => t.pnl !== null && (t.pnl ?? 0) < 0 && t.time >= startOfDay.getTime())
      .reduce((sum, t) => sum + Math.abs(t.pnl ?? 0), 0);
    return dailyLoss >= limit;
  }, [trades]);

  const selectedPair = useReplayStore((s) => s.selectedPair);
  const dateRange = useReplayStore((s) => s.dateRange);
  const loadEventsForDateRange = useReplayStore((s) => s.loadEventsForDateRange);

  // Shared data load — all dashboard pages read from the same store.
  useEffect(() => {
    if (!user) return;
    loadEventsForDateRange(dateRange.start, dateRange.end, selectedPair).catch((err) =>
      console.error("[DashboardLayout] loadEvents:", err),
    );
  }, [user, selectedPair, dateRange, loadEventsForDateRange]);

  // Live realtime subscription for the selected pair.
  useLiveTradeEvents(selectedPair, true);

  // Notify when market open/close state transitions (skip initial mount).
  useEffect(() => {
    if (prevMarketOpen.current === null) {
      prevMarketOpen.current = marketOpen;
      return;
    }
    if (prevMarketOpen.current === marketOpen) return;
    prevMarketOpen.current = marketOpen;
    if (marketOpen) {
      push({ variant: "success", title: "Engine running", body: "Forex market is now open.", durationMs: 6000 });
    } else {
      push({ variant: "critical", title: "Engine halted", body: "Forex market is now closed.", durationMs: 8000 });
    }
  }, [marketOpen, push]);

  const title = PAGE_TITLES[location.pathname] ?? "Dashboard";
  const initial = (user?.email?.[0] ?? "T").toUpperCase();

  return (
    <div className="h-screen flex bg-bg-base text-text-primary overflow-hidden">
      {/* Sidebar */}
      <aside
        className={`fixed md:static z-40 h-screen shrink-0 bg-bg-surface border-r border-border-subtle flex flex-col transition-all duration-300 w-60 ${
          collapsed ? "md:w-16" : "md:w-60"
        } ${mobileNav ? "translate-x-0" : "-translate-x-full md:translate-x-0"}`}
      >
        <div
          className={`h-14 flex items-center border-b border-border-subtle ${
            collapsed ? "md:justify-center md:px-0 px-4" : "px-4"
          }`}
        >
          <span className="flex items-center gap-2 font-display font-bold tracking-widest text-sm overflow-hidden">
            <span className="text-brand-blue">⬡</span>
            <span className={collapsed ? "md:hidden" : ""}>GLASS BOX</span>
          </span>
          {/* Collapse toggle — desktop only */}
          <button
            onClick={() => setCollapsed((c) => !c)}
            className={`hidden md:flex items-center justify-center h-6 w-6 rounded text-text-muted hover:text-text-primary hover:bg-bg-elevated transition-colors ${
              collapsed ? "md:hidden" : "ml-auto"
            }`}
            aria-label="Collapse sidebar"
            title="Collapse sidebar"
          >
            «
          </button>
        </div>

        {/* Expand button shown when collapsed */}
        {collapsed && (
          <button
            onClick={() => setCollapsed(false)}
            className="hidden md:flex items-center justify-center h-9 mx-2 mt-2 rounded text-text-muted hover:text-text-primary hover:bg-bg-elevated transition-colors"
            aria-label="Expand sidebar"
            title="Expand sidebar"
          >
            »
          </button>
        )}

        <nav className="flex-1 py-2 overflow-y-auto">
          {NAV.map((n) => (
            <NavLink
              key={n.to}
              to={n.to}
              end={n.end}
              onClick={() => setMobileNav(false)}
              title={collapsed ? n.label : undefined}
              className={({ isActive }) =>
                `flex items-center gap-3 px-4 py-2.5 text-sm border-l-2 transition-colors ${
                  collapsed ? "md:justify-center md:px-0 md:gap-0" : ""
                } ${
                  isActive
                    ? "bg-bg-elevated border-brand-blue text-text-primary"
                    : "border-transparent text-text-secondary hover:text-text-primary hover:bg-bg-elevated"
                }`
              }
            >
              <span className="w-4 text-center shrink-0" aria-hidden>{n.icon}</span>
              <span className={collapsed ? "md:hidden" : ""}>{n.label}</span>
            </NavLink>
          ))}
        </nav>
        <div className="border-t border-border-subtle py-2">
          <a
            href="#"
            title={collapsed ? "Documentation" : undefined}
            className={`flex items-center gap-3 px-4 py-2.5 text-sm text-text-secondary hover:text-text-primary ${
              collapsed ? "md:justify-center md:px-0 md:gap-0" : ""
            }`}
          >
            <span className="w-4 text-center shrink-0" aria-hidden>?</span>
            <span className={collapsed ? "md:hidden" : ""}>Documentation</span>
          </a>
          <button
            onClick={() => signOut()}
            title={collapsed ? "Sign Out" : undefined}
            className={`w-full flex items-center gap-3 px-4 py-2.5 text-sm text-text-secondary hover:text-text-primary ${
              collapsed ? "md:justify-center md:px-0 md:gap-0" : ""
            }`}
          >
            <span className="w-4 text-center shrink-0" aria-hidden>↪</span>
            <span className={collapsed ? "md:hidden" : ""}>Sign Out</span>
          </button>
        </div>
      </aside>

      {mobileNav && (
        <div className="fixed inset-0 z-30 bg-black/50 md:hidden" onClick={() => setMobileNav(false)} />
      )}

      {/* Main column */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Topbar */}
        <header className="h-14 shrink-0 flex items-center justify-between px-4 md:px-6 bg-bg-surface border-b border-border-subtle">
          <div className="flex items-center gap-3">
            <button
              className="md:hidden text-text-secondary"
              aria-label="Open navigation"
              onClick={() => setMobileNav(true)}
            >
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M3 6h18M3 12h18M3 18h18" />
              </svg>
            </button>
            <h1 className="text-sm font-semibold">{title}</h1>
          </div>

          <div className="flex items-center gap-3">
            <div className="hidden sm:block">
              {marketOpen ? (
                <StatusBadge variant="running" pulse>ENGINE RUNNING</StatusBadge>
              ) : (
                <StatusBadge variant="halted">MARKET CLOSED</StatusBadge>
              )}
            </div>

            {/* Tier switcher — preview the dashboard as either plan (billing pending) */}
            <button
              onClick={toggleTier}
              title={`Viewing as ${TIER_FEATURES[tier].label} plan — click to switch`}
              aria-label={`Subscription tier: ${TIER_FEATURES[tier].label}. Click to switch plan.`}
              className={`flex items-center gap-1.5 h-8 px-3 rounded-full border text-xs font-mono uppercase tracking-wide transition-colors ${
                tier === "pro"
                  ? "border-brand-blue/50 bg-brand-blue/10 text-brand-blue hover:bg-brand-blue/20"
                  : "border-border-muted bg-bg-elevated text-text-secondary hover:text-text-primary hover:border-border-active"
              }`}
            >
              <span aria-hidden>{tier === "pro" ? "★" : "○"}</span>
              <span>{TIER_FEATURES[tier].label}</span>
              <span className="text-text-muted" aria-hidden>⇄</span>
            </button>

            <div className="relative">
            <button
              onClick={() => setMenuOpen((v) => !v)}
              className="h-8 w-8 rounded-full bg-bg-elevated border border-border-muted text-sm font-mono text-text-primary flex items-center justify-center hover:border-border-active"
              aria-label="Account menu"
              aria-expanded={menuOpen}
            >
              {initial}
            </button>
            {menuOpen && (
              <div className="absolute right-0 mt-2 w-56 bg-bg-overlay border border-border-muted rounded-lg p-2 z-50 text-sm">
                <p className="px-3 py-2 text-xs text-text-muted truncate font-mono">{user?.email}</p>
                <NavLink
                  to="/dashboard/settings"
                  onClick={() => setMenuOpen(false)}
                  className="block px-3 py-2 rounded-md text-text-secondary hover:text-text-primary hover:bg-bg-elevated"
                >
                  Account Settings
                </NavLink>
                <button
                  onClick={() => signOut()}
                  className="w-full text-left px-3 py-2 rounded-md text-text-secondary hover:text-text-primary hover:bg-bg-elevated"
                >
                  Sign Out
                </button>
              </div>
            )}
            </div>
          </div>
        </header>

        {/* Engine halt banner — shown across the full dashboard when daily loss limit is reached */}
        {engineHalted && (
          <div
            role="alert"
            className="flex items-center justify-between gap-4 bg-bear text-white text-xs font-mono px-4 py-2.5 border-b border-bear/80"
          >
            <span className="flex items-center gap-2">
              <span aria-hidden>⛔</span>
              <strong>ENGINE HALTED</strong>
              <span className="font-normal opacity-90">— Daily loss limit reached. No new trades until midnight UTC (1:00 AM NGT).</span>
            </span>
            <NavLink
              to="/dashboard/propfirm"
              className="shrink-0 underline opacity-80 hover:opacity-100"
            >
              Prop Firm Panel →
            </NavLink>
          </div>
        )}

        {/* Routed content */}
        <main className="flex-1 min-h-0 overflow-hidden">
          <Outlet />
        </main>
      </div>

      <ToastContainer />
    </div>
  );
}
