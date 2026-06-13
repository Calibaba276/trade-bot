import { signOut } from "../../lib/supaclient";

interface AccountStats {
  balance: number;
  equity: number;
  plToday: number;
  plPct: number;
  drawdown: number;
}

interface Props {
  userName?: string;
  stats?: AccountStats;
  accounts?: { id: string; label: string }[];
  selectedAccountId?: string;
  onAccountChange?: (id: string) => void;
  isLive?: boolean;
  onToggleLive?: () => void;
}

export function Topbar({
  userName = "Trader",
  stats,
  accounts = [],
  selectedAccountId,
  onAccountChange,
  isLive = false,
  onToggleLive,
}: Props) {
  const fmt = (n: number, decimals = 2) =>
    n.toLocaleString("en-US", { minimumFractionDigits: decimals, maximumFractionDigits: decimals });

  return (
    <div
      className="flex items-center justify-between px-4 flex-shrink-0"
      style={{
        height: "40px",
        background: "#141921",
        borderBottom: "0.5px solid #1e2530",
      }}
    >
      {/* Greeting */}
      <div className="font-mono text-[12px] text-[#f3f4f6] whitespace-nowrap">
        Good{greeting()},{" "}
        <span className="text-[#34d399]">{userName}</span>
      </div>

      {/* Account stats — centred */}
      {stats && (
        <div className="flex items-center flex-1 justify-center">
          <Stat label="Balance" value={`$${fmt(stats.balance)}`} />
          <Divider />
          <Stat label="Equity" value={`$${fmt(stats.equity)}`} />
          <Divider />
          <Stat
            label="P/L Today"
            value={`${stats.plToday >= 0 ? "+" : ""}$${fmt(Math.abs(stats.plToday))} (${stats.plPct >= 0 ? "+" : ""}${fmt(stats.plPct)}%)`}
            positive={stats.plToday >= 0}
          />
          <Divider />
          <Stat
            label="Drawdown"
            value={`${stats.drawdown > 0 ? "-" : ""}${fmt(Math.abs(stats.drawdown))}%`}
            negative={stats.drawdown > 0}
          />
        </div>
      )}

      {/* Right controls */}
      <div className="flex items-center gap-2 flex-shrink-0">
        {accounts.length > 0 && (
          <select
            value={selectedAccountId}
            onChange={(e) => onAccountChange?.(e.target.value)}
            className="font-mono text-[11px] text-[#e5e7eb] px-2 py-1 cursor-pointer focus:outline-none"
            style={{
              background: "#1e2530",
              border: "0.5px solid #2a3040",
              borderRadius: "3px",
            }}
          >
            {accounts.map((a) => (
              <option key={a.id} value={a.id}>
                {a.label}
              </option>
            ))}
          </select>
        )}
        <TopbarBtn title="Notifications">🔔</TopbarBtn>
        <TopbarBtn title="Settings">⚙️</TopbarBtn>
        {/* Live / Replay mode indicator */}
        <button
          onClick={onToggleLive}
          title={isLive ? "Switch to Replay mode" : "Switch to Live mode"}
          className="font-mono text-[9px] uppercase cursor-pointer transition-colors"
          style={{
            padding: "2px 7px",
            borderRadius: "3px",
            background: isLive ? "rgba(52,211,153,0.12)" : "#1e2530",
            border: `0.5px solid ${isLive ? "#34d399" : "#2a3040"}`,
            color: isLive ? "#34d399" : "#6b7280",
            letterSpacing: "0.06em",
          }}
        >
          {isLive ? "● LIVE" : "REPLAY"}
        </button>

        <TopbarBtn title="Sign out" onClick={() => signOut()}>
          ↪
        </TopbarBtn>
      </div>
    </div>
  );
}

function Stat({
  label,
  value,
  positive,
  negative,
}: {
  label: string;
  value: string;
  positive?: boolean;
  negative?: boolean;
}) {
  const color = positive ? "#34d399" : negative ? "#f87171" : "#f3f4f6";
  return (
    <div className="flex flex-col items-center gap-px px-4">
      <span
        className="font-mono uppercase"
        style={{ fontSize: "9px", color: "#6b7280", letterSpacing: "0.05em" }}
      >
        {label}
      </span>
      <span className="font-mono" style={{ fontSize: "12px", fontWeight: 500, color }}>
        {value}
      </span>
    </div>
  );
}

function Divider() {
  return (
    <div style={{ width: "0.5px", height: "28px", background: "#1e2530", flexShrink: 0 }} />
  );
}

function TopbarBtn({
  children,
  onClick,
  title,
}: {
  children: React.ReactNode;
  onClick?: () => void;
  title?: string;
}) {
  return (
    <button
      onClick={onClick}
      title={title}
      className="font-mono text-[11px] text-[#e5e7eb] px-2 py-1 cursor-pointer transition-colors hover:text-white"
      style={{
        background: "#1e2530",
        border: "0.5px solid #2a3040",
        borderRadius: "3px",
      }}
    >
      {children}
    </button>
  );
}

function greeting() {
  const h = new Date().getHours();
  if (h < 12) return " morning";
  if (h < 17) return " afternoon";
  return " evening";
}
