import { useMemo } from "react";
import { useReplayStore } from "../../store/replayStore";
import type { TradeEvent } from "../../types";

const DOT_COLOR: Record<string, string> = {
  entry: "#34d399",
  exit: "#f87171",
  FVG: "#fbbf24",
  OB: "#38bdf8",
  MSS: "#14b8a6",
  BOS: "#a78bfa",
};

const TYPE_COLOR: Record<string, string> = {
  FVG: "#fbbf24",
  OB: "#38bdf8",
  MSS: "#14b8a6",
  BOS: "#a78bfa",
  entry: "#34d399",
  exit: "#f87171",
  pattern_detected: "#9ca3af",
  invalidated: "#6b7280",
};

function dotColor(event: TradeEvent): string {
  if (event.pattern && DOT_COLOR[event.pattern]) return DOT_COLOR[event.pattern];
  if (DOT_COLOR[event.type]) return DOT_COLOR[event.type];
  return "#6b7280";
}

function typeLabel(event: TradeEvent): string {
  if (event.pattern) return event.pattern;
  if (event.type === "pattern_detected") return "SCAN";
  return event.type.toUpperCase();
}

function typeColor(event: TradeEvent): string {
  if (event.pattern && TYPE_COLOR[event.pattern]) return TYPE_COLOR[event.pattern];
  return TYPE_COLOR[event.type] ?? "#9ca3af";
}

function fmtTime(ms: number): string {
  return new Date(ms).toLocaleTimeString("en-GB", {
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "Africa/Lagos",
  });
}

export function EventLog() {
  const { events, currentTime, selectedTimeframe } = useReplayStore();

  const visible = useMemo(
    () =>
      events
        .filter((e) => e.timeframe === selectedTimeframe && e.timestamp <= currentTime)
        .sort((a, b) => b.timestamp - a.timestamp)
        .slice(0, 50),
    [events, currentTime, selectedTimeframe]
  );

  return (
    <div className="flex flex-col gap-1">
      {visible.length === 0 ? (
        <p className="font-mono text-[10px] text-[#4b5563] px-1">No events yet</p>
      ) : (
        visible.map((event) => (
          <div
            key={event.id}
            className="flex items-start gap-1.5 px-1.5 py-1 rounded-[2px]"
            style={{ background: "#0f1419" }}
          >
            <div
              className="rounded-full flex-shrink-0 mt-[3px]"
              style={{ width: "6px", height: "6px", background: dotColor(event) }}
            />
            <div className="flex flex-col gap-px min-w-0">
              <div className="flex items-center gap-1.5">
                <span className="font-mono text-[9px] text-[#6b7280]">
                  {fmtTime(event.timestamp)}
                </span>
                <span
                  className="font-mono text-[10px] font-medium"
                  style={{ color: typeColor(event) }}
                >
                  {typeLabel(event)}
                </span>
              </div>
              <span className="font-mono text-[10px] text-[#9ca3af] truncate">
                {event.metadata?.entryReason ??
                  (event.price ? `@ ${event.price.toFixed(4)}` : event.type)}
              </span>
            </div>
          </div>
        ))
      )}
    </div>
  );
}
