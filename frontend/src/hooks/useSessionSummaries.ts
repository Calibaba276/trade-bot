import { useMemo } from "react";
import { useReplayStore } from "../store/replayStore";
import type { TradeEvent } from "../types";

export interface SessionSummary {
  key: string;
  session: "London" | "NY";
  date: string;
  scans: number;
  verdicts: number;
  executedTrades: number;
  pnl: number;
  halted: boolean;
}

/** Returns the trading session a UTC timestamp falls in, plus the session's end time. */
function classifyEvent(ms: number): { session: "London" | "NY"; dayKey: string; endMs: number } | null {
  const d = new Date(ms);
  const h = d.getUTCHours() + d.getUTCMinutes() / 60;
  const yr = d.getUTCFullYear(), mo = d.getUTCMonth(), dy = d.getUTCDate();
  const dayKey = `${yr}-${String(mo + 1).padStart(2, "0")}-${String(dy).padStart(2, "0")}`;
  // London 09:00–11:00 NGT = 08:00–10:00 UTC
  if (h >= 8 && h < 10) return { session: "London", dayKey, endMs: Date.UTC(yr, mo, dy, 10, 0, 0) };
  // NY 13:00–17:00 NGT = 12:00–16:00 UTC
  if (h >= 12 && h < 16) return { session: "NY", dayKey, endMs: Date.UTC(yr, mo, dy, 16, 0, 0) };
  return null;
}

/**
 * Aggregates completed London and NY sessions from the current event stream.
 * A session is "completed" once its end time has passed.
 * Returns the `limit` most-recent completed sessions, newest first.
 */
export function useSessionSummaries(limit = 5): SessionSummary[] {
  const events = useReplayStore((s) => s.events);

  return useMemo(() => {
    const now = Date.now();
    const buckets = new Map<string, { session: "London" | "NY"; dayKey: string; endMs: number; ev: TradeEvent[] }>();

    for (const e of events) {
      const c = classifyEvent(e.timestamp);
      if (!c) continue;
      const key = `${c.dayKey}:${c.session}`;
      if (!buckets.has(key)) buckets.set(key, { ...c, ev: [] });
      buckets.get(key)!.ev.push(e);
    }

    return Array.from(buckets.entries())
      .filter(([, v]) => v.endMs < now)
      .sort(([a], [b]) => b.localeCompare(a))
      .slice(0, limit)
      .map(([key, v]) => {
        const exits = v.ev.filter((e) => e.type === "exit");
        const pnl = exits.reduce(
          (sum, e) => sum + (typeof e.metadata?.pnl === "number" ? (e.metadata.pnl as number) : 0),
          0,
        );
        const dateStr = new Date(`${v.dayKey}T12:00:00Z`).toLocaleDateString("en-GB", {
          month: "short",
          day: "2-digit",
          timeZone: "Africa/Lagos",
        });
        return {
          key,
          session: v.session,
          date: dateStr,
          scans: v.ev.filter((e) => e.type === "pattern_detected").length,
          verdicts: v.ev.filter((e) => e.type === "entry").length,
          executedTrades: exits.length,
          pnl,
          halted: v.ev.some((e) => (e.metadata as Record<string, unknown>)?.halted === true),
        } satisfies SessionSummary;
      });
  }, [events, limit]);
}
