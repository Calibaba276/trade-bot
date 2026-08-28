import { describe, it, expect, beforeEach } from "vitest";
import { useReplayStore } from "../../store/replayStore";
import type { TradeEvent } from "../../types";

function makeEvent(overrides: Partial<TradeEvent>): TradeEvent {
  return {
    id: "evt-1",
    user_id: "user",
    account_id: "acc",
    pair: "EURUSD",
    timestamp: 1_000_000,
    timeframe: "5m",
    type: "pattern_detected",
    price: 1.1,
    high: 1.11,
    low: 1.09,
    volume: 0,
    ...overrides,
  };
}

const reset = () => useReplayStore.setState({
  selectedTimeframe: "5m",
  currentTime: 0,
  isPlaying: false,
  playbackSpeed: 1,
  showEventLog: true,
  selectedPair: "EURUSD",
  events: [],
  priceData: {},
  dateRange: { start: new Date(0), end: new Date() },
});

beforeEach(reset);

describe("setSelectedTimeframe", () => {
  it("switches the active timeframe", () => {
    useReplayStore.getState().setSelectedTimeframe("1h");
    expect(useReplayStore.getState().selectedTimeframe).toBe("1h");
  });
});

describe("setCurrentTime", () => {
  it("updates currentTime", () => {
    useReplayStore.getState().setCurrentTime(9_999);
    expect(useReplayStore.getState().currentTime).toBe(9_999);
  });
});

describe("togglePlayback", () => {
  it("flips isPlaying", () => {
    expect(useReplayStore.getState().isPlaying).toBe(false);
    useReplayStore.getState().togglePlayback();
    expect(useReplayStore.getState().isPlaying).toBe(true);
    useReplayStore.getState().togglePlayback();
    expect(useReplayStore.getState().isPlaying).toBe(false);
  });
});

describe("addEvent", () => {
  it("inserts an event into an empty list", () => {
    const evt = makeEvent({ id: "a", timestamp: 5_000 });
    useReplayStore.getState().addEvent(evt);
    expect(useReplayStore.getState().events).toHaveLength(1);
    expect(useReplayStore.getState().events[0].id).toBe("a");
  });

  it("maintains chronological order when events arrive out of order", () => {
    useReplayStore.getState().addEvent(makeEvent({ id: "late", timestamp: 3_000 }));
    useReplayStore.getState().addEvent(makeEvent({ id: "early", timestamp: 1_000 }));
    useReplayStore.getState().addEvent(makeEvent({ id: "mid", timestamp: 2_000 }));

    const ids = useReplayStore.getState().events.map((e) => e.id);
    expect(ids).toEqual(["early", "mid", "late"]);
  });
});

describe("setSelectedPair", () => {
  it("updates selectedPair", () => {
    useReplayStore.getState().setSelectedPair("GBPUSD");
    expect(useReplayStore.getState().selectedPair).toBe("GBPUSD");
  });
});
