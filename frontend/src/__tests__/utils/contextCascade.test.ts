import { describe, it, expect } from "vitest";
import type { TradeEvent } from "../../types";

// ── replicate pure helpers from ContextCascade (not exported, so inline here) ─

const TF_ORDER = ["1m", "5m", "15m", "1h"] as const;

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

function evt(
  tf: TradeEvent["timeframe"],
  pattern: TradeEvent["pattern"],
  timestamp: number,
): TradeEvent {
  return {
    id: `${tf}-${timestamp}`,
    user_id: "u",
    account_id: "a",
    pair: "EURUSD",
    timestamp,
    timeframe: tf,
    type: "pattern_detected",
    pattern,
    price: 1.1,
    high: 1.11,
    low: 1.09,
    volume: 0,
  };
}

describe("parentTimeframes", () => {
  it("returns 5m,15m,1h when on 1m", () => {
    expect(parentTimeframes("1m")).toEqual(["5m", "15m", "1h"]);
  });

  it("returns 15m,1h when on 5m", () => {
    expect(parentTimeframes("5m")).toEqual(["15m", "1h"]);
  });

  it("returns only 1h when on 15m", () => {
    expect(parentTimeframes("15m")).toEqual(["1h"]);
  });

  it("returns empty array when on 1h (no parents)", () => {
    expect(parentTimeframes("1h")).toEqual([]);
  });
});

describe("latestPatternEvent", () => {
  const events: TradeEvent[] = [
    evt("15m", "FVG", 1_000),
    evt("15m", "MSS", 2_000),
    evt("15m", "OB", 3_000),
    evt("1h", "FVG", 1_500),
  ];

  it("returns the most recent pattern on the requested timeframe", () => {
    const result = latestPatternEvent(events, "15m", 10_000);
    expect(result?.pattern).toBe("OB");
  });

  it("respects currentTime — excludes future events", () => {
    const result = latestPatternEvent(events, "15m", 1_500);
    expect(result?.pattern).toBe("FVG");
  });

  it("returns null when no events match the timeframe", () => {
    expect(latestPatternEvent(events, "5m", 10_000)).toBeNull();
  });

  it("returns null when all events are in the future", () => {
    expect(latestPatternEvent(events, "15m", 500)).toBeNull();
  });

  it("ignores events without a pattern field", () => {
    const noPattern: TradeEvent = { ...evt("15m", undefined, 5_000), type: "entry" };
    const result = latestPatternEvent([noPattern], "15m", 10_000);
    expect(result).toBeNull();
  });
});
