import { useRef, useMemo } from "react";
import { useReplayStore } from "../../store/replayStore";
import { TimeframeSelector } from "../Controls/TimeframeSelector";
import { TradeReplayChart } from "./TradeReplayChart";

export function ChartArea() {
  const { selectedPair, currentTime, priceData, selectedTimeframe } = useReplayStore();
  const containerRef = useRef<HTMLDivElement>(null);

  // Live price = last visible candle's close
  const livePrice = useMemo(() => {
    const candles = priceData[selectedTimeframe] ?? [];
    const last = [...candles].filter((c) => c.time <= currentTime).at(-1);
    return last ? last.close.toFixed(last.close > 100 ? 2 : 5) : "—";
  }, [priceData, selectedTimeframe, currentTime]);

  return (
    <div className="flex flex-col flex-1 min-h-0" style={{ background: "#141921" }}>
      {/* Chart topbar */}
      <div
        className="flex items-center gap-2 px-2.5 flex-shrink-0"
        style={{ height: "36px", borderBottom: "0.5px solid #1e2530" }}
      >
        <span className="font-mono text-[13px] font-medium text-[#f3f4f6]">
          {selectedPair}
        </span>
        <span className="font-mono text-[13px] font-medium text-[#34d399]">
          {livePrice}
        </span>
        <TimeframeSelector />
      </div>

      {/* Chart body — TradingView mounts into this div */}
      <div
        ref={containerRef}
        className="flex-1 min-h-0 relative"
        style={{ background: "#0f1419" }}
      >
        <TradeReplayChart containerRef={containerRef} />

        {/* Empty state — shown until candle data loads */}
        {(priceData[selectedTimeframe] ?? []).length === 0 && (
          <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
            <p className="font-mono text-[10px] text-[#374151] mb-2">
              No candle data for {selectedPair} · {selectedTimeframe}
            </p>
            <div className="flex gap-3 font-mono text-[10px]">
              <span style={{ color: "#fbbf24" }}>■ FVG</span>
              <span style={{ color: "#38bdf8" }}>■ OB</span>
              <span style={{ color: "#14b8a6" }}>■ MSS</span>
              <span style={{ color: "#34d399" }}>▲ Entry</span>
              <span style={{ color: "#f87171" }}>▼ Exit</span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
