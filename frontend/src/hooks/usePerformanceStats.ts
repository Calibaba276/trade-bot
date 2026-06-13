import { useMemo } from "react";
import { useReplayStore } from "../store/replayStore";

export interface PerformanceStats {
  winRate: number;
  avgRR: number;
  totalTrades: number;
  bestTrade: number;
  worstTrade: number;
}

export function usePerformanceStats(): PerformanceStats {
  const events = useReplayStore((s) => s.events);
  const currentTime = useReplayStore((s) => s.currentTime);

  return useMemo(() => {
    const exits = events.filter(
      (e) =>
        e.type === "exit" &&
        e.timestamp <= currentTime &&
        typeof e.metadata?.pnl === "number",
    );

    if (!exits.length) {
      return { winRate: 0, avgRR: 0, totalTrades: 0, bestTrade: 0, worstTrade: 0 };
    }

    const pnls = exits.map((e) => e.metadata!.pnl as number);
    const wins = pnls.filter((p) => p > 0);
    const losses = pnls.filter((p) => p < 0);

    const winRate = (wins.length / pnls.length) * 100;
    const avgWin = wins.length ? wins.reduce((a, b) => a + b, 0) / wins.length : 0;
    const avgLoss = losses.length
      ? Math.abs(losses.reduce((a, b) => a + b, 0) / losses.length)
      : 1;
    const avgRR = avgWin / avgLoss;
    const totalTrades = events.filter(
      (e) => e.type === "entry" && e.timestamp <= currentTime,
    ).length;

    return {
      winRate,
      avgRR,
      totalTrades,
      bestTrade: Math.max(...pnls),
      worstTrade: Math.min(...pnls),
    };
  }, [events, currentTime]);
}
