import { useEffect, useRef } from "react";
import { supabase } from "../lib/supaclient";
import { useReplayStore } from "../store/replayStore";
import { useAuth } from "./useAuth";

const SAVE_DEBOUNCE_MS = 2000;

/**
 * Persists the current scrub position to replay_sessions.
 * On pair change, restores the previous session for that pair (if one exists).
 * Fails silently when Supabase is unreachable.
 */
export function useReplaySession() {
  const { user } = useAuth();
  const sessionIdRef = useRef<string | null>(null);
  const saveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const { currentTime, selectedTimeframe, selectedPair, dateRange, setCurrentTime, setSelectedTimeframe } =
    useReplayStore();

  // ── Restore session when pair changes ────────────────────────────────────
  useEffect(() => {
    if (!user) return;
    sessionIdRef.current = null;

    (async () => {
      try {
        const { data } = await supabase
          .from("replay_sessions")
          .select("*")
          .eq("user_id", user.id)
          .eq("pair", selectedPair)
          .order("updated_at", { ascending: false })
          .limit(1)
          .maybeSingle();
        if (!data) return;
        sessionIdRef.current = data.id as string;
        setCurrentTime(data.current_time as number);
        setSelectedTimeframe(data.selected_timeframe as "1m" | "5m" | "15m" | "1h");
      } catch {
        // Unreachable — start from the beginning of the loaded date range
      }
    })();
  }, [user, selectedPair, setCurrentTime, setSelectedTimeframe]);

  // ── Debounced save on scrub / timeframe change ────────────────────────────
  useEffect(() => {
    if (!user || !currentTime) return;

    if (saveTimerRef.current) clearTimeout(saveTimerRef.current);

    saveTimerRef.current = setTimeout(async () => {
      const payload = {
        user_id: user.id,
        pair: selectedPair,
        start_time: dateRange.start.getTime(),
        end_time: dateRange.end.getTime(),
        current_time: currentTime,
        playback_speed: useReplayStore.getState().playbackSpeed,
        selected_timeframe: selectedTimeframe,
        updated_at: new Date().toISOString(),
      };

      try {
        if (sessionIdRef.current) {
          await supabase
            .from("replay_sessions")
            .update(payload)
            .eq("id", sessionIdRef.current);
        } else {
          const { data } = await supabase
            .from("replay_sessions")
            .insert(payload)
            .select("id")
            .single();
          if (data) sessionIdRef.current = data.id as string;
        }
      } catch {
        // Silently fail — session persistence is best-effort
      }
    }, SAVE_DEBOUNCE_MS);

    return () => {
      if (saveTimerRef.current) clearTimeout(saveTimerRef.current);
    };
  }, [user, currentTime, selectedTimeframe, selectedPair, dateRange]);
}
