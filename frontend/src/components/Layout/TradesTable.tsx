import { useState } from "react";

type Tab = "All" | "Open" | "Closed";

export interface TradeRow {
  id: string;
  time: string;
  pair: string;
  direction: "BUY" | "SELL";
  entry: number;
  sl: number;
  tp: number;
  lots: number;
  rr: number;
  pl: number | null;
  status: "OPEN" | "WIN" | "LOSS";
  setup: string;
}

interface Props {
  trades?: TradeRow[];
}

export function TradesTable({ trades = [] }: Props) {
  const [activeTab, setActiveTab] = useState<Tab>("All");

  const filtered = trades.filter((t) => {
    if (activeTab === "Open") return t.status === "OPEN";
    if (activeTab === "Closed") return t.status !== "OPEN";
    return true;
  });

  return (
    <div className="flex-shrink-0" style={{ borderTop: "0.5px solid #1e2530", background: "#0f1419" }}>
      {/* Header */}
      <div
        className="flex items-center justify-between px-2.5"
        style={{ height: "28px", borderBottom: "0.5px solid #1e2530" }}
      >
        <span
          className="font-mono uppercase text-[#9ca3af]"
          style={{ fontSize: "10px", letterSpacing: "0.05em" }}
        >
          Trades
        </span>
        <div className="flex gap-px">
          {(["All", "Open", "Closed"] as Tab[]).map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className="font-mono text-[10px] cursor-pointer transition-colors"
              style={{
                padding: "3px 9px",
                borderRadius: "3px",
                background: activeTab === tab ? "#162040" : "transparent",
                color: activeTab === tab ? "#85b7eb" : "#6b7280",
                border: "none",
              }}
            >
              {tab}
            </button>
          ))}
        </div>
      </div>

      {/* Table */}
      <div style={{ overflowX: "auto" }}>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "10px" }}>
          <thead>
            <tr>
              {["Time", "Pair", "Dir", "Entry", "SL", "TP", "Lots", "R:R", "P/L", "Status", "Setup"].map((h) => (
                <th
                  key={h}
                  className="font-mono text-left text-[#6b7280] whitespace-nowrap"
                  style={{
                    padding: "4px 10px",
                    fontWeight: 400,
                    borderBottom: "0.5px solid #1e2530",
                    background: "#0f1419",
                  }}
                >
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {filtered.length === 0 ? (
              <tr>
                <td
                  colSpan={11}
                  className="font-mono text-[10px] text-[#4b5563] text-center"
                  style={{ padding: "12px 10px" }}
                >
                  No trades
                </td>
              </tr>
            ) : (
              filtered.map((t) => (
                <tr
                  key={t.id}
                  style={{ borderBottom: "0.5px solid #1a1f2b" }}
                  onMouseEnter={(e) => ((e.currentTarget as HTMLElement).style.background = "#141921")}
                  onMouseLeave={(e) => ((e.currentTarget as HTMLElement).style.background = "transparent")}
                >
                  <td className="font-mono text-[#6b7280] whitespace-nowrap" style={{ padding: "5px 10px" }}>{t.time}</td>
                  <td className="font-mono text-[#d1d5db]" style={{ padding: "5px 10px" }}>{t.pair}</td>
                  <td style={{ padding: "5px 10px" }}>
                    <Badge variant={t.direction === "BUY" ? "buy" : "sell"}>{t.direction}</Badge>
                  </td>
                  <td className="font-mono text-[#d1d5db]" style={{ padding: "5px 10px" }}>{t.entry.toFixed(t.pair.includes("JPY") ? 3 : 5)}</td>
                  <td className="font-mono" style={{ padding: "5px 10px", color: "#f87171" }}>{t.sl.toFixed(t.pair.includes("JPY") ? 3 : 5)}</td>
                  <td className="font-mono" style={{ padding: "5px 10px", color: "#34d399" }}>{t.tp.toFixed(t.pair.includes("JPY") ? 3 : 5)}</td>
                  <td className="font-mono text-[#d1d5db]" style={{ padding: "5px 10px" }}>{t.lots.toFixed(2)}</td>
                  <td className="font-mono text-[#d1d5db]" style={{ padding: "5px 10px" }}>{t.rr.toFixed(1)}</td>
                  <td
                    className="font-mono"
                    style={{
                      padding: "5px 10px",
                      color: t.pl === null ? "#60a5fa" : t.pl >= 0 ? "#34d399" : "#f87171",
                    }}
                  >
                    {t.pl === null ? "—" : `${t.pl >= 0 ? "+" : ""}$${Math.abs(t.pl).toFixed(0)}`}
                  </td>
                  <td style={{ padding: "5px 10px" }}>
                    <Badge variant={t.status === "OPEN" ? "open" : t.status === "WIN" ? "win" : "loss"}>
                      {t.status}
                    </Badge>
                  </td>
                  <td className="font-mono text-[#9ca3af]" style={{ padding: "5px 10px" }}>{t.setup}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function Badge({ children, variant }: { children: React.ReactNode; variant: string }) {
  const styles: Record<string, React.CSSProperties> = {
    buy: { background: "#0d2d1a", color: "#34d399", border: "0.5px solid #166534" },
    sell: { background: "#2d0d0d", color: "#f87171", border: "0.5px solid #7f1d1d" },
    win: { background: "#0d2d1a", color: "#34d399" },
    loss: { background: "#2d0d0d", color: "#f87171" },
    open: { background: "#1a2535", color: "#60a5fa" },
  };
  return (
    <span
      className="font-mono"
      style={{
        display: "inline-block",
        padding: "1px 5px",
        borderRadius: "2px",
        fontSize: "9px",
        fontWeight: 500,
        ...(styles[variant] ?? {}),
      }}
    >
      {children}
    </span>
  );
}
