import { useMemo } from "react";
import { useReplayStore } from "../../store/replayStore";
import type { TradeEvent } from "../../types";

const TF_ORDER = ["1m", "5m", "15m", "1h"] as const;

const PATTERN_COLOR: Record<string, string> = {
  FVG: "#fbbf24",
  OB: "#38bdf8",
  MSS: "#14b8a6",
  BOS: "#8b5cf6",
};

function parentTimeframes(selected: string): string[] {
  const idx = TF_ORDER.indexOf(selected as (typeof TF_ORDER)[number]);
  return idx >= 0 ? (TF_ORDER.slice(idx + 1) as unknown as string[]) : [];
}

function latestPatternEvent(
  events: TradeEvent[],
  tf: string,
  currentTime: number,
): TradeEvent | null {
  const hits = events.filter(
    (e) => e.timeframe === tf && e.timestamp <= currentTime && e.pattern,
  );
  return hits.at(-1) ?? null;
}

export function ContextCascade() {
  const { events, currentTime, selectedTimeframe } = useReplayStore();

  const parents = useMemo(() => parentTimeframes(selectedTimeframe), [selectedTimeframe]);

  const slots = useMemo(
    () => parents.map((tf) => ({ tf, event: latestPatternEvent(events, tf, currentTime) })),
    [parents, events, currentTime],
  );

  // No parent timeframes when 1h is selected
  if (!parents.length) return null;

  return (
    <div
      className="flex items-center gap-0 flex-shrink-0 px-3"
      style={{ height: "26px", background: "#0d1117", borderBottom: "0.5px solid #1e2530" }}
    >
      <span
        className="font-mono uppercase text-[#374151] mr-3 flex-shrink-0"
        style={{ fontSize: "8px", letterSpacing: "0.06em" }}
      >
        Context
      </span>

      {slots.map(({ tf, event }, i) => {
        const color = event?.pattern ? PATTERN_COLOR[event.pattern] : null;
        return (
          <span key={tf} className="flex items-center">
            {i > 0 && (
              <span className="font-mono text-[#1e2530] mx-2.5" style={{ fontSize: "10px" }}>
                /
              </span>
            )}
            <span className="font-mono text-[#6b7280] mr-1.5" style={{ fontSize: "9px" }}>
              {tf}
            </span>
            {color ? (
              <span
                className="font-mono"
                style={{
                  fontSize: "8px",
                  padding: "1px 5px",
                  borderRadius: "2px",
                  color,
                  background: color + "18",
                  border: `0.5px solid ${color}44`,
                  letterSpacing: "0.04em",
                }}
              >
                {event!.pattern}
              </span>
            ) : (
              <span className="font-mono text-[#2a3040]" style={{ fontSize: "9px" }}>
                —
              </span>
            )}
          </span>
        );
      })}
    </div>
  );
}
