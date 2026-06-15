import { useMemo } from "react";
import { useReplayStore } from "../store/replayStore";
import type { TradeEvent } from "../types";

export interface Trade {
  id: string;
  signalId?: string;
  time: number;
  pair: string;
  direction: "BUY" | "SELL";
  entry: number;
  sl: number;
  tp: number;
  lots: number;
  rr: number;
  pnl: number | null;          // null = still open
  status: "OPEN" | "WIN" | "LOSS";
  setup: string;               // scenario / pattern tag
  entryEvent: TradeEvent;
  exitEvent?: TradeEvent;
}

function num(v: unknown, fallback = 0): number {
  return typeof v === "number" && Number.isFinite(v) ? v : fallback;
}

/**
 * Derive trade rows from the raw trade_events stream.
 * An `entry` event opens a trade; the next `exit` for the same pair closes it.
 * Falls back gracefully when metadata is sparse.
 */
export function useTrades(): Trade[] {
  const events = useReplayStore((s) => s.events);

  return useMemo(() => {
    const sorted = [...events].sort((a, b) => a.timestamp - b.timestamp);
    const entries = sorted.filter((e) => e.type === "entry");
    const exits = sorted.filter((e) => e.type === "exit");
    const usedExits = new Set<string>();

    return entries
      .map((e) => {
        const m = e.metadata ?? {};
        // Pair the entry with its matching exit: prefer signal_id, else next exit on same pair.
        let exit = e.signal_id
          ? exits.find((x) => x.signal_id === e.signal_id && !usedExits.has(x.id))
          : undefined;
        if (!exit) {
          exit = exits.find(
            (x) => x.pair === e.pair && x.timestamp > e.timestamp && !usedExits.has(x.id),
          );
        }
        if (exit) usedExits.add(exit.id);

        const direction: "BUY" | "SELL" =
          (m.direction as string)?.toUpperCase() === "SELL" ||
          (m.direction as string)?.toUpperCase() === "BUY"
            ? ((m.direction as string).toUpperCase() as "BUY" | "SELL")
            : num(m.tp) < num(e.price)
              ? "SELL"
              : "BUY";

        const pnl =
          typeof exit?.metadata?.pnl === "number" ? (exit.metadata.pnl as number) : null;

        return {
          id: e.id,
          signalId: e.signal_id,
          time: e.timestamp,
          pair: e.pair,
          direction,
          entry: num(e.price),
          sl: num(m.sl ?? m.stop_loss),
          tp: num(m.tp ?? m.take_profit),
          lots: num(m.lots ?? m.lot_size),
          rr: num(m.rr ?? m.rr_ratio, 3),
          pnl,
          status: pnl === null ? "OPEN" : pnl >= 0 ? "WIN" : "LOSS",
          setup: (m.scenario as string) ?? e.pattern ?? "—",
          entryEvent: e,
          exitEvent: exit,
        } satisfies Trade;
      })
      .sort((a, b) => b.time - a.time);
  }, [events]);
}
