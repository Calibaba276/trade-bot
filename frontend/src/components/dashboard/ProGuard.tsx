import { Link } from "react-router-dom";
import { useTierStore, TIER_FEATURES, type Tier } from "../../store/tierStore";

type Feature = {
  [K in keyof (typeof TIER_FEATURES)[Tier]]: (typeof TIER_FEATURES)[Tier][K] extends boolean
    ? K
    : never;
}[keyof (typeof TIER_FEATURES)[Tier]];

interface Props {
  /** Capability flag from TIER_FEATURES that this route requires. */
  feature: Feature;
  /** Short name of the gated area, e.g. "Replay Mode". */
  title: string;
  /** One-line pitch shown on the upsell screen. */
  blurb: string;
  children: React.ReactNode;
}

/**
 * Route-level Pro gate. If the current tier lacks `feature`, the page content
 * is never mounted — instead we render an upgrade screen. This keeps Starter
 * users from viewing Pro-only tooling even by typing the URL directly.
 */
export function ProGuard({ feature, title, blurb, children }: Props) {
  const tier = useTierStore((s) => s.tier);
  const allowed = TIER_FEATURES[tier][feature] as boolean;

  if (allowed) return <>{children}</>;

  return (
    <div className="h-full overflow-y-auto flex items-center justify-center p-6">
      <div className="relative max-w-md w-full text-center bg-bg-surface border border-brand-blue/30 rounded-2xl p-8 overflow-hidden">
        {/* Soft brand glow */}
        <div
          aria-hidden
          className="pointer-events-none absolute -top-16 left-1/2 -translate-x-1/2 h-40 w-40 rounded-full blur-3xl"
          style={{ background: "var(--brand-glow)" }}
        />
        <div className="relative">
          <div className="mx-auto mb-4 h-12 w-12 rounded-xl bg-brand-blue/15 border border-brand-blue/40 flex items-center justify-center text-brand-blue text-xl">
            🔒
          </div>
          <p className="text-[10px] font-mono uppercase tracking-[0.2em] text-brand-blue mb-2">
            Pro feature
          </p>
          <h2 className="text-lg font-semibold text-text-primary">{title}</h2>
          <p className="text-sm text-text-secondary mt-2">{blurb}</p>
          <Link
            to="/dashboard/settings"
            className="inline-flex items-center gap-2 mt-6 text-sm bg-brand-blue hover:bg-brand-dim text-white rounded-md px-5 py-2.5 transition-colors"
          >
            <span aria-hidden>★</span> Upgrade to Pro
          </Link>
          <p className="text-xs text-text-muted mt-3">
            Already on Pro? Switch your plan from the topbar.
          </p>
        </div>
      </div>
    </div>
  );
}
