import { useEffect, useRef } from "react";
import { supabase } from "../lib/supaclient";
import { useReplayStore } from "../store/replayStore";
import { useToastStore } from "../store/toastStore";
import type { TradeEvent } from "../types";
import type { RealtimeChannel } from "@supabase/supabase-js";

/**
 * Subscribes to live INSERT events on trade_events for the given pair.
 * RLS on the table means users only receive their own rows — no extra filter needed.
 * The channel is torn down and recreated if `pair` or `enabled` changes.
 */
function toastForEvent(push: ReturnType<typeof useToastStore.getState>["push"], event: TradeEvent) {
  const pair = event.pair;
  const price = event.price.toFixed(event.price > 10 ? 2 : 5);

  switch (event.type) {
    case "entry":
      push({
        variant: "success",
        title: `Trade entered — ${pair}`,
        body: `${event.pattern ?? "signal"} @ ${price}`,
        durationMs: 7000,
      });
      break;
    case "exit": {
      const pnl = event.metadata?.pnl;
      const pnlStr = pnl != null ? ` · PnL ${pnl >= 0 ? "+" : ""}${pnl.toFixed(2)}R` : "";
      push({
        variant: pnl != null && pnl < 0 ? "warning" : "success",
        title: `Trade closed — ${pair}`,
        body: `Exit @ ${price}${pnlStr}`,
        durationMs: 8000,
      });
      break;
    }
    case "invalidated":
      push({
        variant: "warning",
        title: `Setup invalidated — ${pair}`,
        body: `${event.pattern ?? "pattern"} @ ${price}`,
        durationMs: 6000,
      });
      break;
    default:
      break;
  }
}

export function useLiveTradeEvents(pair: string, enabled = true) {
  const addEvent = useReplayStore((s) => s.addEvent);
  const push = useToastStore((s) => s.push);
  const channelRef = useRef<RealtimeChannel | null>(null);

  useEffect(() => {
    if (!enabled || !pair) return;

    const channel = supabase
      .channel(`live-trade-events:${pair}`)
      .on(
        "postgres_changes",
        {
          event: "INSERT",
          schema: "public",
          table: "trade_events",
          // Column filter: only events for the selected pair.
          // Syntax: column=operator.value (eq = equals)
          filter: `pair=eq.${pair}`,
        },
        (payload) => {
          const event = payload.new as TradeEvent;
          addEvent(event);
          toastForEvent(push, event);
        }
      )
      .subscribe((status) => {
        if (status === "CHANNEL_ERROR") {
          console.warn("[useLiveTradeEvents] channel error — will retry automatically");
        }
      });

    channelRef.current = channel;

    return () => {
      if (channelRef.current) {
        supabase.removeChannel(channelRef.current);
        channelRef.current = null;
      }
    };
  }, [pair, enabled, addEvent, push]);
}
