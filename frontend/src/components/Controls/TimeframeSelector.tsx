import { useReplayStore } from "../../store/replayStore";

const TIMEFRAMES = ["1m", "5m", "15m", "1h"] as const;

export function TimeframeSelector() {
  const { selectedTimeframe, setSelectedTimeframe } = useReplayStore();

  return (
    <div className="flex gap-1 ml-1">
      {TIMEFRAMES.map((tf) => {
        const active = tf === selectedTimeframe;
        return (
          <button
            key={tf}
            onClick={() => setSelectedTimeframe(tf)}
            className="font-mono cursor-pointer transition-all"
            style={{
              fontSize: "10px",
              padding: "2px 7px",
              borderRadius: "3px",
              background: active ? "#162040" : "#1e2530",
              border: `0.5px solid ${active ? "#378add" : "#2a3040"}`,
              color: active ? "#85b7eb" : "#9ca3af",
            }}
          >
            {tf}
          </button>
        );
      })}
    </div>
  );
}
