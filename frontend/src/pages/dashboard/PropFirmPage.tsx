import { useState, useEffect } from "react";
import { PropFirmPanel } from "../../components/dashboard/PropFirmPanel";

const STORAGE_KEY = "propfirm_config_v1";

function loadConfig() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) return JSON.parse(raw);
  } catch {}
  return null;
}

function saveConfig(cfg: object) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(cfg));
  } catch {}
}

export function PropFirmPage() {
  const saved = loadConfig();
  const [dailyLimit, setDailyLimit] = useState<number>(saved?.dailyLimit ?? 1000);
  const [maxConsec, setMaxConsec] = useState<number>(saved?.maxConsec ?? 3);
  const [avgLoss, setAvgLoss] = useState<number>(saved?.avgLoss ?? 120);
  const [profitTarget, setProfitTarget] = useState<number>(saved?.profitTarget ?? 800);
  const [accountSize, setAccountSize] = useState<number>(saved?.accountSize ?? 10000);

  useEffect(() => {
    saveConfig({ dailyLimit, maxConsec, avgLoss, profitTarget, accountSize });
  }, [dailyLimit, maxConsec, avgLoss, profitTarget, accountSize]);

  const tradesBeforeHalt = avgLoss > 0 ? Math.floor(dailyLimit / avgLoss) : 0;

  const Field = ({
    label,
    value,
    onChange,
    prefix,
  }: {
    label: string;
    value: number;
    onChange: (n: number) => void;
    prefix?: string;
  }) => (
    <label className="block">
      <span className="text-xs uppercase tracking-wide text-text-secondary">{label}</span>
      <div className="mt-1.5 flex items-center bg-bg-elevated border border-border-muted rounded-md overflow-hidden focus-within:ring-2 focus-within:ring-brand-blue">
        {prefix && <span className="px-2 text-text-muted text-sm font-mono">{prefix}</span>}
        <input
          type="number"
          value={value}
          onChange={(e) => onChange(Number(e.target.value))}
          className="w-full bg-transparent px-2 py-2 text-sm font-mono text-text-primary focus:outline-none"
        />
      </div>
    </label>
  );

  return (
    <div className="h-full overflow-y-auto p-6">
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 max-w-5xl">
        {/* Live panel */}
        <div>
          <h2 className="text-sm font-semibold text-text-primary mb-3">Live Constraints</h2>
          <PropFirmPanel
            config={{
              dailyLossLimit: dailyLimit,
              consecutiveLossLimit: maxConsec,
              profitTarget,
              accountSize,
            }}
            expanded
          />
        </div>

        {/* Config + simulation */}
        <div className="space-y-6">
          <div className="bg-bg-surface border border-border-subtle rounded-lg p-4">
            <h2 className="text-sm font-semibold text-text-primary mb-4">Prop Firm Configuration</h2>
            <div className="grid grid-cols-2 gap-4">
              <Field label="Daily Loss Limit" value={dailyLimit} onChange={setDailyLimit} prefix="$" />
              <Field label="Max Consecutive Losses" value={maxConsec} onChange={setMaxConsec} />
              <Field label="Account Size" value={accountSize} onChange={setAccountSize} prefix="$" />
              <Field label="Profit Target" value={profitTarget} onChange={setProfitTarget} prefix="$" />
            </div>
            <p className="text-xs text-text-muted mt-3">
              Configuration is saved locally and persists across reloads. These limits mirror the
              engine's enforcement. When the daily loss limit is reached, no new trades are taken
              until the next UTC day (1:00 AM NGT).
            </p>
          </div>

          <div className="bg-bg-surface border border-border-subtle rounded-lg p-4">
            <h2 className="text-sm font-semibold text-text-primary mb-1">Halt Simulation</h2>
            <p className="text-xs text-text-muted mb-4">
              Estimate how many losing trades it takes to trigger the daily halt.
            </p>
            <Field label="Average Loss Per Trade" value={avgLoss} onChange={setAvgLoss} prefix="$" />
            <div className="mt-4 bg-bg-elevated rounded-md p-4 text-center">
              <p className="text-3xl font-mono font-bold text-amber">{tradesBeforeHalt}</p>
              <p className="text-xs text-text-secondary mt-1">
                losing trades of ${avgLoss} before the engine halts at ${dailyLimit}
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
