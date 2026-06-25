import { useCallback, useEffect, useState } from "react";
import { supabase } from "../../lib/supaclient";
import { useAuth } from "../../hooks/useAuth";
import { StatusBadge } from "../../components/dashboard/StatusBadge";
import { EmptyState, Skeleton } from "../../components/dashboard/States";
import { AddAccountModal } from "../../components/dashboard/AddAccountModal";
import { shortId } from "../../utils/format";
import { useTierStore, TIER_FEATURES } from "../../store/tierStore";

type Tab = "accounts" | "risk" | "profile" | "billing";

interface BrokerAccountRow {
  id: string;
  account_number?: string | number;
  server?: string;
  symbol?: string;
  status?: string;
  risk_amount?: number;
  last_heartbeat?: string;
}

const STATUS_VARIANT: Record<string, "ready" | "warn" | "halted" | "pending"> = {
  ready: "ready",
  pending: "pending",
  halted: "halted",
  error: "warn",
};

export function SettingsPage() {
  const [tab, setTab] = useState<Tab>("accounts");

  const tabs: { id: Tab; label: string }[] = [
    { id: "accounts", label: "Broker Accounts" },
    { id: "risk", label: "Risk Configuration" },
    { id: "profile", label: "Profile & Security" },
    { id: "billing", label: "Subscription & Billing" },
  ];

  return (
    <div className="h-full overflow-y-auto p-6 max-w-4xl">
      <div className="flex gap-1 border-b border-border-subtle mb-6">
        {tabs.map((t) => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={`px-4 py-2.5 text-sm border-b-2 -mb-px transition-colors ${
              tab === t.id
                ? "border-brand-blue text-text-primary"
                : "border-transparent text-text-secondary hover:text-text-primary"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === "accounts" && <AccountsTab />}
      {tab === "risk" && <RiskTab />}
      {tab === "profile" && <ProfileTab />}
      {tab === "billing" && <BillingTab />}
    </div>
  );
}

function UpgradeInterceptModal({ onClose }: { onClose: () => void }) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4" onClick={onClose}>
      <div
        className="w-full max-w-sm bg-bg-overlay border border-border-muted rounded-lg p-6"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-label="Upgrade to Pro"
      >
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <span className="text-brand-blue text-lg" aria-hidden>★</span>
            <h2 className="text-base font-semibold text-text-primary">Upgrade to Pro</h2>
          </div>
          <button onClick={onClose} aria-label="Close" className="text-text-muted hover:text-text-primary text-lg">✕</button>
        </div>
        <p className="text-sm text-text-secondary mb-4">
          Your Starter plan supports 1 broker account. Pro supports up to 10 — run Glass Box across multiple MT5 accounts simultaneously.
        </p>
        <ul className="text-xs text-text-secondary space-y-1.5 mb-5">
          {[
            "Up to 10 MT5 accounts",
            "Prop Firm Panel with halt simulation and profit target tracker",
            "Priority signal delivery",
          ].map((f) => (
            <li key={f} className="flex gap-2">
              <span className="text-bull shrink-0">✓</span>
              {f}
            </li>
          ))}
        </ul>
        <button
          className="w-full text-sm bg-brand-blue text-white rounded-md px-4 py-2.5 opacity-60 cursor-not-allowed"
          disabled
          title="Billing coming soon"
        >
          Upgrade to Pro — $49/mo (Coming Soon)
        </button>
        <button
          onClick={onClose}
          className="w-full mt-2 text-xs text-text-muted hover:text-text-secondary text-center py-1"
        >
          Continue with Starter plan
        </button>
      </div>
    </div>
  );
}

function AccountsTab() {
  const { user } = useAuth();
  const { tier } = useTierStore();
  const maxAccounts = TIER_FEATURES[tier].maxAccounts;

  const [rows, setRows] = useState<BrokerAccountRow[] | null>(null);
  const [error, setError] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [upgradeOpen, setUpgradeOpen] = useState(false);
  const [addedBanner, setAddedBanner] = useState(false);

  const load = useCallback(() => {
    if (!user) return;
    setRows(null);
    setError(false);
    supabase
      .from("broker_accounts")
      .select("*")
      .eq("user_id", user.id)
      .then(({ data, error }) => {
        if (error) { setError(true); return; }
        setRows((data ?? []) as BrokerAccountRow[]);
      });
  }, [user]);

  useEffect(() => { load(); }, [load]);

  const handleSaved = useCallback(() => {
    load();
    setAddedBanner(true);
    setTimeout(() => setAddedBanner(false), 8000);
  }, [load]);

  const atLimit = rows !== null && rows.length >= maxAccounts;
  const starterAtLimit = atLimit && tier === "starter";

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-sm font-semibold text-text-primary">Connected Broker Accounts</h2>
        <button
          onClick={() => {
            if (starterAtLimit) { setUpgradeOpen(true); return; }
            if (atLimit) return;
            setModalOpen(true);
          }}
          disabled={atLimit && !starterAtLimit}
          title={atLimit && !starterAtLimit ? `Your ${TIER_FEATURES[tier].label} plan allows up to ${maxAccounts} accounts.` : undefined}
          className="text-xs bg-brand-blue hover:bg-brand-dim text-white rounded-md px-3 py-1.5 disabled:opacity-40 disabled:cursor-not-allowed"
        >
          + Add Account
        </button>
      </div>

      {atLimit && !starterAtLimit && (
        <div className="mb-4 text-xs text-text-secondary bg-bg-surface border border-border-subtle rounded-md px-3 py-2">
          You've reached the {maxAccounts}-account limit for the{" "}
          <span className="text-text-primary font-medium">{TIER_FEATURES[tier].label}</span> plan.
        </div>
      )}

      {addedBanner && (
        <div className="mb-4 text-xs text-bull bg-bg-surface border border-bull/30 rounded-md px-3 py-2">
          Account added. The engine will begin scanning your account by the next session.
        </div>
      )}

      {upgradeOpen && <UpgradeInterceptModal onClose={() => setUpgradeOpen(false)} />}
      <AddAccountModal open={modalOpen} onClose={() => setModalOpen(false)} onSaved={handleSaved} />

      <div className="bg-bg-surface border border-border-subtle rounded-lg overflow-hidden">
        {error ? (
          <EmptyState icon="⚠" title="Could not load accounts" body="Check your connection and refresh." />
        ) : rows === null ? (
          <div className="p-4 space-y-2">
            <Skeleton className="h-8" /><Skeleton className="h-8" /><Skeleton className="h-8" />
          </div>
        ) : rows.length === 0 ? (
          <EmptyState
            icon="🔌"
            title="No broker accounts connected"
            body="Add your first MT5 account to start executing signals. Credentials are stored securely in Azure Key Vault."
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="text-text-muted">
                  {["Account", "Server", "Status", "Risk"].map((h) => (
                    <th key={h} className="text-left font-normal font-mono px-4 py-2.5 border-b border-border-subtle">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="font-mono">
                {rows.map((r) => (
                  <tr key={r.id} className="border-b border-border-subtle/50 hover:bg-bg-elevated">
                    <td className="px-4 py-2.5 text-text-primary">{r.account_number ?? shortId(r.id)}</td>
                    <td className="px-4 py-2.5 text-text-secondary">{r.server ?? "—"}</td>
                    <td className="px-4 py-2.5">
                      <StatusBadge variant={STATUS_VARIANT[r.status ?? "pending"] ?? "pending"}>
                        {(r.status ?? "pending").toUpperCase()}
                      </StatusBadge>
                    </td>
                    <td className="px-4 py-2.5 text-text-secondary">{r.risk_amount != null ? `$${r.risk_amount}` : "—"}</td>
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

const RISK_STORAGE_KEY = "glassbox.riskDefaults";

export const RISK_FIELDS = [
  { key: "risk_amount", label: "Risk Amount", def: "500", help: "Dollar risk per trade. Position size is computed from this and the stop distance." },
  { key: "rr_ratio", label: "R:R Ratio", def: "3.0", help: "Reward-to-risk target. A 3.0 ratio targets $3 profit per $1 risked." },
  { key: "breakeven_buffer_ticks", label: "Breakeven Buffer (ticks)", def: "10", help: "Once in profit, the stop moves to entry plus this many ticks." },
  { key: "max_daily_drawdown_pct", label: "Max Daily Drawdown %", def: "2.0", help: "The engine halts for the day once this loss threshold is hit." },
] as const;

export function loadRiskDefaults(): Record<string, string> {
  try {
    const saved = localStorage.getItem(RISK_STORAGE_KEY);
    if (saved) return JSON.parse(saved);
  } catch { /* ignore */ }
  return Object.fromEntries(RISK_FIELDS.map((f) => [f.key, f.def]));
}

function RiskTab() {
  const [values, setValues] = useState<Record<string, string>>(loadRiskDefaults);
  const [saved, setSaved] = useState(false);

  const handleSave = () => {
    localStorage.setItem(RISK_STORAGE_KEY, JSON.stringify(values));
    setSaved(true);
    setTimeout(() => setSaved(false), 3000);
  };

  return (
    <div className="bg-bg-surface border border-border-subtle rounded-lg p-5 max-w-xl">
      <h2 className="text-sm font-semibold text-text-primary mb-1">Global Risk Defaults</h2>
      <p className="text-xs text-text-muted mb-5">These values pre-fill the Add Account form.</p>
      <div className="space-y-4">
        {RISK_FIELDS.map((f) => (
          <div key={f.key}>
            <label className="text-xs uppercase tracking-wide text-text-secondary">{f.label}</label>
            <input
              value={values[f.key]}
              onChange={(e) => setValues((s) => ({ ...s, [f.key]: e.target.value }))}
              className="mt-1.5 w-full bg-bg-elevated border border-border-muted rounded-md px-3 py-2 text-sm font-mono text-text-primary focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-blue"
            />
            <p className="text-xs text-text-muted mt-1">{f.help}</p>
          </div>
        ))}
      </div>
      <div className="mt-5 flex items-center gap-3">
        <button
          onClick={handleSave}
          className="text-sm bg-brand-blue hover:bg-brand-dim text-white rounded-md px-4 py-2"
        >
          Save Defaults
        </button>
        {saved && <span className="text-xs text-bull">Saved.</span>}
      </div>
    </div>
  );
}

function BillingTab() {
  const { tier, setTier } = useTierStore();
  const features = TIER_FEATURES[tier];

  return (
    <div className="max-w-xl space-y-4">
      <div className="bg-bg-surface border border-border-subtle rounded-lg p-5">
        <h2 className="text-sm font-semibold text-text-primary mb-1">Current Plan</h2>
        <p className="text-xs text-text-muted mb-4">Your active subscription.</p>
        <div className="flex items-center justify-between">
          <div>
            <p className="text-base font-semibold text-text-primary">{features.label}</p>
            <p className="text-xs text-text-muted mt-0.5">
              Up to {features.maxAccounts} broker account{features.maxAccounts === 1 ? "" : "s"}
            </p>
          </div>
          <span className={`text-xs font-mono px-2 py-1 rounded-full border ${
            tier === "pro"
              ? "text-bull border-bull/40 bg-bull/10"
              : "text-text-secondary border-border-subtle bg-bg-elevated"
          }`}>
            {features.label.toUpperCase()}
          </span>
        </div>
      </div>

      {tier === "starter" && (
        <div className="bg-bg-surface border border-brand-blue/30 rounded-lg p-5">
          <h3 className="text-sm font-semibold text-text-primary mb-1">Upgrade to Pro</h3>
          <p className="text-xs text-text-muted mb-3">
            Unlock up to 10 broker accounts, the Prop Firm panel, and priority signal delivery.
          </p>
          <button
            className="text-sm bg-brand-blue hover:bg-brand-dim text-white rounded-md px-4 py-2 opacity-60 cursor-not-allowed"
            disabled
            title="Billing coming soon"
          >
            Upgrade — Coming Soon
          </button>
        </div>
      )}

      <p className="text-xs text-text-muted px-1">
        Billing integration is in progress. Plan changes are not yet available.
        {" "}
        <span
          className="underline cursor-pointer text-text-secondary hover:text-text-primary"
          onClick={() => setTier(tier === "pro" ? "starter" : "pro")}
        >
          Preview as {tier === "pro" ? "Starter" : "Pro"}
        </span>
      </p>
    </div>
  );
}

function ProfileTab() {
  const { user } = useAuth();
  const [pw, setPw] = useState("");
  const [msg, setMsg] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const updatePassword = async () => {
    if (pw.length < 6) { setMsg("Password must be at least 6 characters."); return; }
    setBusy(true);
    const { error } = await supabase.auth.updateUser({ password: pw });
    setBusy(false);
    setMsg(error ? error.message : "Password updated.");
    if (!error) setPw("");
  };

  return (
    <div className="bg-bg-surface border border-border-subtle rounded-lg p-5 max-w-xl">
      <h2 className="text-sm font-semibold text-text-primary mb-4">Profile & Security</h2>
      <div className="mb-5">
        <label className="text-xs uppercase tracking-wide text-text-secondary">Email</label>
        <p className="mt-1.5 font-mono text-sm text-text-primary bg-bg-elevated border border-border-muted rounded-md px-3 py-2">
          {user?.email ?? "—"}
        </p>
      </div>
      <div>
        <label className="text-xs uppercase tracking-wide text-text-secondary">New Password</label>
        <input
          type="password"
          value={pw}
          onChange={(e) => setPw(e.target.value)}
          placeholder="••••••••"
          className="mt-1.5 w-full bg-bg-elevated border border-border-muted rounded-md px-3 py-2 text-sm font-mono text-text-primary focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-blue"
        />
      </div>
      {msg && <p className="text-xs text-text-secondary mt-2">{msg}</p>}
      <button
        onClick={updatePassword}
        disabled={busy}
        className="mt-4 text-sm bg-brand-blue hover:bg-brand-dim text-white rounded-md px-4 py-2 disabled:opacity-40"
      >
        {busy ? "Updating…" : "Update Password"}
      </button>
    </div>
  );
}
