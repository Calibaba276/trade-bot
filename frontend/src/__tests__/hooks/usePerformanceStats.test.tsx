import { describe, it, expect, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { usePerformanceStats } from "../../hooks/usePerformanceStats";
import { useReplayStore } from "../../store/replayStore";
import type { TradeEvent } from "../../types";

function makeEntry(ts: number): TradeEvent {
  return {
    id: `entry-${ts}`,
    user_id: "u",
    account_id: "a",
    pair: "EURUSD",
    timestamp: ts,
    timeframe: "5m",
    type: "entry",
    price: 1.1,
    high: 1.12,
    low: 1.08,
    volume: 0,
  };
}

function makeExit(ts: number, pnl: number): TradeEvent {
  return {
    id: `exit-${ts}`,
    user_id: "u",
    account_id: "a",
    pair: "EURUSD",
    timestamp: ts,
    timeframe: "5m",
    type: "exit",
    price: 1.1 + pnl * 0.001,
    high: 1.11,
    low: 1.09,
    volume: 0,
    metadata: { pnl },
  };
}

function Stats() {
  const s = usePerformanceStats();
  return (
    <div>
      <span data-testid="win-rate">{s.winRate}</span>
      <span data-testid="avg-rr">{s.avgRR.toFixed(2)}</span>
      <span data-testid="total">{s.totalTrades}</span>
      <span data-testid="best">{s.bestTrade}</span>
      <span data-testid="worst">{s.worstTrade}</span>
    </div>
  );
}

const NOW = 10_000;

// Zustand v5 setState expects the full state type; cast to any for test convenience
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const setState = (patch: object) => useReplayStore.setState(patch as any);

beforeEach(() => setState({ events: [], currentTime: NOW }));

describe("usePerformanceStats", () => {
  it("returns zeros when there are no exit events", () => {
    render(<Stats />);
    expect(screen.getByTestId("win-rate").textContent).toBe("0");
    expect(screen.getByTestId("total").textContent).toBe("0");
  });

  it("returns 100% win rate when all exits are profitable", () => {
    setState({
      events: [makeEntry(1_000), makeExit(2_000, 200), makeEntry(3_000), makeExit(4_000, 150)],
      currentTime: NOW,
    });
    render(<Stats />);
    expect(screen.getByTestId("win-rate").textContent).toBe("100");
  });

  it("calculates 50% win rate with one win and one loss", () => {
    setState({ events: [makeExit(1_000, 300), makeExit(2_000, -100)], currentTime: NOW });
    render(<Stats />);
    expect(screen.getByTestId("win-rate").textContent).toBe("50");
  });

  it("computes avg R:R as avgWin / avgLoss", () => {
    setState({ events: [makeExit(1_000, 300), makeExit(2_000, -100)], currentTime: NOW });
    render(<Stats />);
    // avgWin=300, avgLoss=100 → R:R = 3.00
    expect(screen.getByTestId("avg-rr").textContent).toBe("3.00");
  });

  it("counts only entry events before currentTime as total trades", () => {
    setState({
      events: [makeEntry(1_000), makeEntry(2_000), makeEntry(NOW + 1_000)],
      currentTime: NOW,
    });
    render(<Stats />);
    expect(screen.getByTestId("total").textContent).toBe("2");
  });

  it("excludes events after currentTime", () => {
    setState({ events: [makeExit(NOW + 1_000, 500)], currentTime: NOW });
    render(<Stats />);
    expect(screen.getByTestId("win-rate").textContent).toBe("0");
  });

  it("tracks best and worst trade correctly", () => {
    setState({
      events: [makeExit(1_000, 400), makeExit(2_000, -150), makeExit(3_000, 200)],
      currentTime: NOW,
    });
    render(<Stats />);
    expect(screen.getByTestId("best").textContent).toBe("400");
    expect(screen.getByTestId("worst").textContent).toBe("-150");
  });
});
