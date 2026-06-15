import { useEffect, useState } from "react";
import { supabase } from "../../lib/supaclient";
import { useAuth } from "../../hooks/useAuth";

interface Props {
  open: boolean;
  onClose: () => void;
  onSaved: () => void;
}

const FIELDS = [
  { key: "account_number", label: "Account Number", type: "text", placeholder: "12345678", def: "" },
  { key: "server", label: "Server", type: "text", placeholder: "ICMarkets-Demo01", def: "" },
  { key: "symbol", label: "Symbol", type: "text", placeholder: "EURUSD", def: "EURUSD" },
  { key: "risk_amount", label: "Risk Amount", type: "number", placeholder: "500", def: "500" },
  { key: "rr_ratio", label: "R:R Ratio", type: "number", placeholder: "2.0", def: "2.0" },
  { key: "breakeven_buffer_ticks", label: "Breakeven Buffer (ticks)", type: "number", placeholder: "10", def: "10" },
  { key: "max_daily_drawdown_pct", label: "Max Daily Drawdown %", type: "number", placeholder: "2.0", def: "2.0" },
  { key: "terminal_path", label: "Terminal Path (advanced)", type: "text", placeholder: "C:\\MT5\\terminal64.exe", def: "" },
] as const;

export function AddAccountModal({ open, onClose, onSaved }: Props) {
  const { user } = useAuth();
  const [form, setForm] = useState<Record<string, string>>(() =>
    Object.fromEntries(FIELDS.map((f) => [f.key, f.def])),
  );
  const [currency, setCurrency] = useState("USD");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  if (!open) return null;

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    const payload = {
      user_id: user?.id,
      account_number: form.account_number,
      server: form.server,
      symbol: form.symbol || "EURUSD",
      risk_amount: Number(form.risk_amount) || 0,
      risk_currency: currency,
      rr_ratio: Number(form.rr_ratio) || 2,
      breakeven_buffer_ticks: Number(form.breakeven_buffer_ticks) || 10,
      max_daily_drawdown_pct: Number(form.max_daily_drawdown_pct) || 2,
      terminal_path: form.terminal_path || null,
      status: "pending",
    };
    const { error } = await supabase.from("broker_accounts").insert(payload);
    setBusy(false);
    if (error) {
      setError(error.message);
      return;
    }
    onSaved();
    onClose();
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
      onClick={onClose}
    >
      <div
        className="w-full max-w-lg max-h-[90vh] overflow-y-auto bg-bg-overlay border border-border-muted rounded-lg p-6"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-label="Add broker account"
      >
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-base font-semibold text-text-primary">Add Broker Account</h2>
          <button onClick={onClose} aria-label="Close" className="text-text-muted hover:text-text-primary text-lg">✕</button>
        </div>

        <form onSubmit={submit} className="grid grid-cols-2 gap-4">
          {FIELDS.map((f) => (
            <label key={f.key} className={f.key === "terminal_path" ? "col-span-2" : ""}>
              <span className="text-xs uppercase tracking-wide text-text-secondary">{f.label}</span>
              <input
                type={f.type}
                value={form[f.key]}
                placeholder={f.placeholder}
                onChange={(e) => setForm((s) => ({ ...s, [f.key]: e.target.value }))}
                required={f.key === "account_number" || f.key === "server"}
                step={f.type === "number" ? "any" : undefined}
                className="mt-1.5 w-full bg-bg-elevated border border-border-muted rounded-md px-3 py-2 text-sm font-mono text-text-primary placeholder-text-muted focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-blue"
              />
            </label>
          ))}

          <label>
            <span className="text-xs uppercase tracking-wide text-text-secondary">Risk Currency</span>
            <select
              value={currency}
              onChange={(e) => setCurrency(e.target.value)}
              className="mt-1.5 w-full bg-bg-elevated border border-border-muted rounded-md px-3 py-2 text-sm font-mono text-text-primary focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-blue"
            >
              {["USD", "GBP", "EUR"].map((c) => <option key={c} value={c}>{c}</option>)}
            </select>
          </label>

          {error && <p className="col-span-2 text-xs text-bear">{error}</p>}

          <div className="col-span-2 flex justify-end gap-3 mt-2">
            <button type="button" onClick={onClose} className="text-sm px-4 py-2 rounded-md border border-border-muted text-text-secondary hover:text-text-primary">
              Cancel
            </button>
            <button type="submit" disabled={busy} className="text-sm px-4 py-2 rounded-md bg-brand-blue hover:bg-brand-dim text-white disabled:opacity-40">
              {busy ? "Saving…" : "Add Account"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
