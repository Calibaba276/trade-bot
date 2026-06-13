import { useReplayStore } from "../../store/replayStore";
import { TimeframeSelector } from "../Controls/TimeframeSelector";

export function ChartArea() {
  const { selectedPair, currentTime } = useReplayStore();

  const price = "—";

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
        <span className="font-mono text-[13px] font-medium text-[#34d399]">{price}</span>
        <TimeframeSelector />
      </div>

      {/* Chart body — TradingView Lightweight Charts mounts here (Phase 2.1) */}
      <div
        className="flex-1 flex items-center justify-center min-h-0"
        style={{ background: "#0f1419" }}
        id="chart-container"
      >
        <div className="text-center">
          <p className="font-mono text-[11px] text-[#374151] mb-2">
            TradingView Lightweight Charts
          </p>
          <p className="font-mono text-[10px] text-[#4b5563]">
            Candles + FVG / OB / MSS overlays render here
          </p>
          <div className="flex gap-2.5 justify-center mt-3 font-mono text-[10px]">
            <span style={{ color: "#fbbf24" }}>■ FVG</span>
            <span style={{ color: "#38bdf8" }}>■ OB</span>
            <span style={{ color: "#14b8a6" }}>■ MSS</span>
            <span style={{ color: "#34d399" }}>▲ Entry</span>
            <span style={{ color: "#f87171" }}>▼ Exit</span>
          </div>
          {currentTime > 0 && (
            <p className="font-mono text-[9px] text-[#4b5563] mt-3">
              t = {new Date(currentTime).toISOString()}
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
