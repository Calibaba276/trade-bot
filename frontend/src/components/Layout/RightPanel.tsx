import { EventLog } from "../EventLog/EventLog";

interface PropFirmStats {
  dailyLoss: number;
  dailyLossLimit: number;
  drawdownPct: number;
  drawdownLimit: number;
  consecutiveLosses: number;
  consecutiveLossLimit: number;
}

interface PerfStats {
  winRate: number;
  avgRR: number;
  totalTrades: number;
  bestTrade: number;
  worstTrade: number;
}

interface Props {
  propFirm?: PropFirmStats;
  performance?: PerfStats;
}

const DEFAULT_PROP: PropFirmStats = {
  dailyLoss: 0,
  dailyLossLimit: 1200,
  drawdownPct: 0,
  drawdownLimit: 10,
  consecutiveLosses: 0,
  consecutiveLossLimit: 5,
};

const DEFAULT_PERF: PerfStats = {
  winRate: 0,
  avgRR: 0,
  totalTrades: 0,
  bestTrade: 0,
  worstTrade: 0,
};

export function RightPanel({ propFirm = DEFAULT_PROP, performance = DEFAULT_PERF }: Props) {
  return (
    <div
      className="flex flex-col overflow-hidden flex-shrink-0"
      style={{ width: "220px", minWidth: "220px", background: "#141921", borderLeft: "0.5px solid #1e2530" }}
    >
      {/* Event Log */}
      <Section title="Event Log" flex>
        <EventLog />
      </Section>

      {/* Prop Firm Rules */}
      <Section title="Prop Firm Rules">
        <PropRow
          label="Daily loss"
          value={`$${propFirm.dailyLoss.toFixed(0)} / $${propFirm.dailyLossLimit.toFixed(0)}`}
          pct={(propFirm.dailyLoss / propFirm.dailyLossLimit) * 100}
          barColor="#34d399"
          warnAt={70}
        />
        <PropRow
          label="Max drawdown"
          value={`${propFirm.drawdownPct.toFixed(1)}% / ${propFirm.drawdownLimit}%`}
          pct={(propFirm.drawdownPct / propFirm.drawdownLimit) * 100}
          barColor="#fbbf24"
          warnAt={60}
        />
        <div className="mt-1.5">
          <div className="flex justify-between font-mono text-[10px] text-[#9ca3af] mb-1">
            <span>Consecutive losses</span>
            <span className="text-[#e5e7eb] font-medium">
              {propFirm.consecutiveLosses} / {propFirm.consecutiveLossLimit}
            </span>
          </div>
          <div className="flex gap-1 mt-1">
            {Array.from({ length: propFirm.consecutiveLossLimit }).map((_, i) => (
              <div
                key={i}
                className="rounded-full"
                style={{
                  width: "8px",
                  height: "8px",
                  background: i < propFirm.consecutiveLosses ? "#f87171" : "#1e2530",
                }}
              />
            ))}
          </div>
        </div>
      </Section>

      {/* Monthly Performance */}
      <Section title="Monthly Performance" noBorder>
        <PerfRow label="Win rate" value={`${propFirm.dailyLossLimit > 0 ? performance.winRate.toFixed(1) : "—"}%`} />
        <PerfRow label="Avg R:R" value={performance.avgRR > 0 ? performance.avgRR.toFixed(1) : "—"} />
        <PerfRow label="Total trades" value={String(performance.totalTrades)} />
        <PerfRow
          label="Best trade"
          value={performance.bestTrade > 0 ? `+$${performance.bestTrade.toFixed(0)}` : "—"}
          color="#34d399"
        />
        <PerfRow
          label="Worst trade"
          value={performance.worstTrade < 0 ? `-$${Math.abs(performance.worstTrade).toFixed(0)}` : "—"}
          color="#f87171"
        />
      </Section>
    </div>
  );
}

function Section({
  title,
  children,
  flex,
  noBorder,
}: {
  title: string;
  children: React.ReactNode;
  flex?: boolean;
  noBorder?: boolean;
}) {
  return (
    <div
      className={flex ? "flex-1 overflow-y-auto min-h-0" : "flex-shrink-0"}
      style={{
        padding: "10px",
        borderBottom: noBorder ? "none" : "0.5px solid #1e2530",
      }}
    >
      <div
        className="font-mono uppercase text-[#6b7280] mb-2"
        style={{ fontSize: "9px", letterSpacing: "0.06em" }}
      >
        {title}
      </div>
      {children}
    </div>
  );
}

function PropRow({
  label,
  value,
  pct,
  barColor,
  warnAt,
}: {
  label: string;
  value: string;
  pct: number;
  barColor: string;
  warnAt: number;
}) {
  const color = pct >= warnAt ? "#f87171" : barColor;
  return (
    <div className="mb-1.5">
      <div className="flex justify-between font-mono text-[10px] text-[#9ca3af] mb-1">
        <span>{label}</span>
        <span className="text-[#e5e7eb] font-medium">{value}</span>
      </div>
      <div className="h-1 rounded-sm overflow-hidden" style={{ background: "#1e2530" }}>
        <div
          className="h-full rounded-sm transition-all"
          style={{ width: `${Math.min(pct, 100)}%`, background: color }}
        />
      </div>
    </div>
  );
}

function PerfRow({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div
      className="flex justify-between font-mono text-[10px] py-1"
      style={{ borderBottom: "0.5px solid #1e2530" }}
    >
      <span className="text-[#9ca3af]">{label}</span>
      <span style={{ color: color ?? "#f3f4f6", fontWeight: 500 }}>{value}</span>
    </div>
  );
}
