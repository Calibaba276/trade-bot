import { useCallback, useEffect, useState } from "react";
import { supabase } from "../../lib/supaclient";
import { useAuth } from "../../hooks/useAuth";
import { StatusBadge } from "../../components/dashboard/StatusBadge";
import { EmptyState, Skeleton } from "../../components/dashboard/States";
import { AddAccountModal } from "../../components/dashboard/AddAccountModal";
import { shortId } from "../../utils/format";

type Tab = "accounts" | "risk" | "profile";

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
    </div>
  );
}

function AccountsTab() {
  const { user } = useAuth();
  const [rows, setRows] = useState<BrokerAccountRow[] | null>(null);
  const [error, setError] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);

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

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-sm font-semibold text-text-primary">Connected Broker Accounts</h2>
        <button
          onClick={() => setModalOpen(true)}
          className="text-xs bg-brand-blue hover:bg-brand-dim text-white rounded-md px-3 py-1.5"
        >
          + Add Account
        </button>
      </div>

      <AddAccountModal open={modalOpen} onClose={() => setModalOpen(false)} onSaved={load} />

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
                  {["Account", "Server", "Symbol", "Status", "Risk"].map((h) => (
                    <th key={h} className="text-left font-normal font-mono px-4 py-2.5 border-b border-border-subtle">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="font-mono">
                {rows.map((r) => (
                  <tr key={r.id} className="border-b border-border-subtle/50 hover:bg-bg-elevated">
                    <td className="px-4 py-2.5 text-text-primary">{r.account_number ?? shortId(r.id)}</td>
                    <td className="px-4 py-2.5 text-text-secondary">{r.server ?? "—"}</td>
                    <td className="px-4 py-2.5 text-text-secondary">{r.symbol ?? "EURUSD"}</td>
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

function RiskTab() {
  const fields = [
    { label: "Risk Amount", def: "500", help: "Dollar risk per trade. Position size is computed from this and the stop distance." },
    { label: "R:R Ratio", def: "3.0", help: "Reward-to-risk target. A 3.0 ratio targets $3 profit per $1 risked." },
    { label: "Breakeven Buffer (ticks)", def: "10", help: "Once in profit, the stop moves to entry plus this many ticks." },
    { label: "Max Daily Drawdown %", def: "2.0", help: "The engine halts for the day once this loss threshold is hit." },
  ];
  return (
    <div className="bg-bg-surface border border-border-subtle rounded-lg p-5 max-w-xl">
      <h2 className="text-sm font-semibold text-text-primary mb-1">Global Risk Defaults</h2>
      <p className="text-xs text-text-muted mb-5">These values pre-fill the Add Account form.</p>
      <div className="space-y-4">
        {fields.map((f) => (
          <div key={f.label}>
            <label className="text-xs uppercase tracking-wide text-text-secondary">{f.label}</label>
            <input
              defaultValue={f.def}
              className="mt-1.5 w-full bg-bg-elevated border border-border-muted rounded-md px-3 py-2 text-sm font-mono text-text-primary focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-blue"
            />
            <p className="text-xs text-text-muted mt-1">{f.help}</p>
          </div>
        ))}
      </div>
      <button className="mt-5 text-sm bg-brand-blue hover:bg-brand-dim text-white rounded-md px-4 py-2">Save Defaults</button>
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
