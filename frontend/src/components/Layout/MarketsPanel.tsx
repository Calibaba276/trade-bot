import { useState } from "react";
import { useReplayStore } from "../../store/replayStore";

interface MarketItem {
  symbol: string;
  price: string;
  changePct: number;
}

const MARKETS: { group: string; items: MarketItem[] }[] = [
  {
    group: "Forex",
    items: [
      { symbol: "EURUSD", price: "1.0875", changePct: 0.12 },
      { symbol: "GBPUSD", price: "1.2743", changePct: -0.08 },
      { symbol: "USDJPY", price: "149.82", changePct: 0.21 },
      { symbol: "AUDUSD", price: "0.6534", changePct: -0.15 },
      { symbol: "USDCAD", price: "1.3612", changePct: 0.05 },
      { symbol: "NZDUSD", price: "0.5987", changePct: -0.09 },
    ],
  },
  {
    group: "Indices",
    items: [
      { symbol: "NAS100", price: "17842", changePct: 0.34 },
      { symbol: "US30", price: "38450", changePct: -0.11 },
      { symbol: "SPX500", price: "5124", changePct: 0.18 },
    ],
  },
  {
    group: "Commodities",
    items: [
      { symbol: "XAUUSD", price: "2318.5", changePct: 0.44 },
      { symbol: "XAGUSD", price: "27.34", changePct: 0.22 },
      { symbol: "USOIL", price: "82.45", changePct: -0.31 },
    ],
  },
];

export function MarketsPanel() {
  const [collapsed, setCollapsed] = useState(false);
  const { selectedPair, setSelectedPair } = useReplayStore();

  return (
    <div
      className="flex flex-col flex-shrink-0 transition-all duration-200"
      style={{
        width: collapsed ? "34px" : "160px",
        minWidth: collapsed ? "34px" : "160px",
        background: "#141921",
        borderRight: "0.5px solid #1e2530",
      }}
    >
      {/* Header */}
      <div
        className="flex items-center justify-between px-2 flex-shrink-0"
        style={{
          padding: "8px 8px 6px",
          borderBottom: "0.5px solid #1e2530",
        }}
      >
        {!collapsed && (
          <span
            className="font-mono uppercase text-[#9ca3af] whitespace-nowrap overflow-hidden"
            style={{ fontSize: "10px", letterSpacing: "0.06em" }}
          >
            Markets
          </span>
        )}
        <button
          onClick={() => setCollapsed((c) => !c)}
          className="text-[#6b7280] hover:text-[#9ca3af] cursor-pointer transition-colors leading-none"
          style={{
            background: "none",
            border: "none",
            fontSize: "13px",
            padding: "1px",
            transform: collapsed ? "rotate(180deg)" : "none",
            marginLeft: collapsed ? "auto" : undefined,
          }}
          aria-label="Toggle markets panel"
        >
          ‹
        </button>
      </div>

      {/* Scrollable list */}
      {!collapsed && (
        <div className="flex-1 overflow-y-auto" style={{ scrollbarWidth: "thin", scrollbarColor: "#2a3040 transparent" }}>
          {MARKETS.map(({ group, items }) => (
            <div key={group}>
              <div
                className="font-mono uppercase text-[#4b5563] px-2"
                style={{ fontSize: "9px", padding: "6px 8px 3px", letterSpacing: "0.05em" }}
              >
                {group}
              </div>
              {items.map((item) => (
                <div
                  key={item.symbol}
                  onClick={() => setSelectedPair(item.symbol)}
                  className="flex items-center justify-between cursor-pointer transition-all"
                  style={{
                    padding: "5px 8px",
                    borderLeft: `2px solid ${selectedPair === item.symbol ? "#378add" : "transparent"}`,
                    background: selectedPair === item.symbol ? "#162040" : "transparent",
                  }}
                  onMouseEnter={(e) => {
                    if (selectedPair !== item.symbol) {
                      (e.currentTarget as HTMLElement).style.background = "#1a2030";
                    }
                  }}
                  onMouseLeave={(e) => {
                    if (selectedPair !== item.symbol) {
                      (e.currentTarget as HTMLElement).style.background = "transparent";
                    }
                  }}
                >
                  <span className="font-mono text-[11px] font-medium text-[#e5e7eb] whitespace-nowrap">
                    {item.symbol}
                  </span>
                  <div className="text-right">
                    <div className="font-mono text-[10px] text-[#9ca3af]">{item.price}</div>
                    <div
                      className="font-mono"
                      style={{
                        fontSize: "9px",
                        color: item.changePct >= 0 ? "#34d399" : "#f87171",
                      }}
                    >
                      {item.changePct >= 0 ? "+" : ""}
                      {item.changePct.toFixed(2)}%
                    </div>
                  </div>
                </div>
              ))}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
