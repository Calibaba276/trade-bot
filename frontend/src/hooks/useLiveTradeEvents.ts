import { useEffect, useRef } from "react";
import { supabase } from "../lib/supaclient";
import { useReplayStore } from "../store/replayStore";
import type { TradeEvent } from "../types";
import type { RealtimeChannel } from "@supabase/supabase-js";

/**
 * Subscribes to live INSERT events on trade_events for the given pair.
 * RLS on the table means users only receive their own rows — no extra filter needed.
 * The channel is torn down and recreated if `pair` or `enabled` changes.
 */
export function useLiveTradeEvents(pair: string, enabled = true) {
  const addEvent = useReplayStore((s) => s.addEvent);
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
          addEvent(payload.new as TradeEvent);
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
  }, [pair, enabled, addEvent]);
}
