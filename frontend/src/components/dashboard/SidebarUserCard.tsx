import { useEffect, useRef, useState } from "react";
import { NavLink } from "react-router-dom";
import { useAuth } from "../../hooks/useAuth";
import { signOut } from "../../lib/supaclient";
import { useTierStore, TIER_FEATURES } from "../../store/tierStore";

interface Props {
  /** When the sidebar is collapsed we show only the avatar. */
  collapsed?: boolean;
}

/**
 * Account component pinned to the sidebar footer.
 *
 * Shows the signed-in user (avatar + name + plan) and opens an upward popover
 * that holds Documentation, Account Settings, plan management and Sign Out.
 * Pro users get a distinct, elevated treatment (gradient ring, glow, gold
 * "PRO" badge) so the plan feels premium.
 */
export function SidebarUserCard({ collapsed = false }: Props) {
  const { user } = useAuth();
  const tier = useTierStore((s) => s.tier);
  const isPro = tier === "pro";
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);

  const name = user?.email?.split("@")[0] ?? "Trader";
  const displayName = name.charAt(0).toUpperCase() + name.slice(1);
  const initials = (user?.email?.[0] ?? "T").toUpperCase();

  // Close on outside click / Escape.
  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  return (
    <div ref={rootRef} className="relative border-t border-border-subtle p-2">
      {/* Popover menu — opens upward */}
      {open && (
        <div
          role="menu"
          className="absolute bottom-full left-2 right-2 mb-2 bg-bg-overlay border border-border-muted rounded-xl p-1.5 shadow-2xl text-sm animate-slide-in"
          style={{ minWidth: collapsed ? "13rem" : undefined }}
        >
          <p className="px-3 pt-2 pb-2 text-xs text-text-muted truncate font-mono">
            {user?.email}
          </p>

          <MenuLink to="/dashboard/settings" icon="⚙" onClick={() => setOpen(false)}>
            Account Settings
          </MenuLink>
          <MenuAnchor href="#" icon="?">
            Documentation
          </MenuAnchor>
          <MenuLink to="/dashboard/settings" icon="≣" onClick={() => setOpen(false)}>
            View all plans
          </MenuLink>

          <div className="my-1.5 h-px bg-border-subtle" />

          {!isPro && (
            <NavLink
              to="/dashboard/settings"
              onClick={() => setOpen(false)}
              role="menuitem"
              className="flex items-center gap-2.5 px-3 py-2 rounded-md text-brand-blue hover:bg-brand-blue/10 transition-colors"
            >
              <span className="w-4 text-center shrink-0" aria-hidden>★</span>
              <span className="font-medium">Upgrade to Pro</span>
            </NavLink>
          )}

          <button
            role="menuitem"
            onClick={() => signOut()}
            className="w-full flex items-center gap-2.5 px-3 py-2 rounded-md text-text-secondary hover:text-bear hover:bg-bear/10 transition-colors"
          >
            <span className="w-4 text-center shrink-0" aria-hidden>↪</span>
            <span>Sign Out</span>
          </button>
        </div>
      )}

      {/* Trigger — the account card */}
      <button
        onClick={() => setOpen((v) => !v)}
        aria-haspopup="menu"
        aria-expanded={open}
        title={collapsed ? `${displayName} · ${TIER_FEATURES[tier].label} plan` : undefined}
        className={`w-full flex items-center gap-2.5 rounded-xl transition-colors ${
          collapsed ? "md:justify-center md:px-0 px-2 py-1.5" : "px-2 py-1.5"
        } ${open ? "bg-bg-elevated" : "hover:bg-bg-elevated"}`}
      >
        {/* Avatar — gradient ring + glow for Pro */}
        <span
          className="relative shrink-0 grid place-items-center h-8 w-8 rounded-full text-xs font-mono font-semibold text-text-primary"
          style={
            isPro
              ? {
                  background:
                    "linear-gradient(135deg, var(--brand-blue), var(--neutral-amber))",
                  boxShadow: "0 0 0 1px var(--bg-surface), 0 0 12px var(--brand-glow)",
                }
              : { background: "var(--bg-elevated)", boxShadow: "0 0 0 1px var(--border-muted)" }
          }
        >
          <span
            className="grid place-items-center h-7 w-7 rounded-full"
            style={{ background: "var(--bg-surface)" }}
          >
            {initials}
          </span>
          {isPro && (
            <span
              className="absolute -bottom-0.5 -right-0.5 grid place-items-center h-3.5 w-3.5 rounded-full text-[8px]"
              style={{ background: "var(--neutral-amber)", color: "var(--text-inverse)" }}
              aria-hidden
            >
              ★
            </span>
          )}
        </span>

        {!collapsed && (
          <span className="min-w-0 flex-1 text-left leading-tight">
            <span className="block truncate text-sm font-medium text-text-primary">
              {displayName}
            </span>
            {isPro ? (
              <span
                className="block text-[11px] font-semibold tracking-wide"
                style={{
                  backgroundImage:
                    "linear-gradient(90deg, var(--brand-blue), var(--neutral-amber))",
                  WebkitBackgroundClip: "text",
                  backgroundClip: "text",
                  color: "transparent",
                }}
              >
                Pro plan
              </span>
            ) : (
              <span className="block text-[11px] text-text-muted">Starter plan</span>
            )}
          </span>
        )}

        {!collapsed && (
          <span className="shrink-0 text-text-muted text-xs" aria-hidden>
            {open ? "⌄" : "⌃"}
          </span>
        )}
      </button>
    </div>
  );
}

function MenuLink({
  to,
  icon,
  onClick,
  children,
}: {
  to: string;
  icon: string;
  onClick?: () => void;
  children: React.ReactNode;
}) {
  return (
    <NavLink
      to={to}
      onClick={onClick}
      role="menuitem"
      className="flex items-center gap-2.5 px-3 py-2 rounded-md text-text-secondary hover:text-text-primary hover:bg-bg-elevated transition-colors"
    >
      <span className="w-4 text-center shrink-0" aria-hidden>{icon}</span>
      <span>{children}</span>
    </NavLink>
  );
}

function MenuAnchor({
  href,
  icon,
  children,
}: {
  href: string;
  icon: string;
  children: React.ReactNode;
}) {
  return (
    <a
      href={href}
      role="menuitem"
      className="flex items-center gap-2.5 px-3 py-2 rounded-md text-text-secondary hover:text-text-primary hover:bg-bg-elevated transition-colors"
    >
      <span className="w-4 text-center shrink-0" aria-hidden>{icon}</span>
      <span>{children}</span>
    </a>
  );
}
