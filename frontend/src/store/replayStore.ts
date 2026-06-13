import { create } from "zustand";
import { supabase } from "../lib/supaclient";
import type { TradeEvent, Candle } from "../types";

interface ReplayStore {
  // UI state
  selectedTimeframe: "1m" | "5m" | "15m" | "1h";
  currentTime: number;
  isPlaying: boolean;
  playbackSpeed: 1 | 2 | 4;
  showEventLog: boolean;
  selectedPair: string;

  // Data
  events: TradeEvent[];
  priceData: Record<string, Candle[]>;
  dateRange: { start: Date; end: Date };

  // Actions
  setSelectedTimeframe: (tf: "1m" | "5m" | "15m" | "1h") => void;
  setCurrentTime: (time: number) => void;
  setIsPlaying: (playing: boolean) => void;
  togglePlayback: () => void;
  setPlaybackSpeed: (speed: 1 | 2 | 4) => void;
  toggleEventLog: () => void;
  setSelectedPair: (pair: string) => void;
  setDateRange: (range: { start: Date; end: Date }) => void;
  loadEventsForDateRange: (start: Date, end: Date, pair: string) => Promise<void>;
  addEvent: (event: TradeEvent) => void;
}

export const useReplayStore = create<ReplayStore>((set, get) => ({
  selectedTimeframe: "5m",
  currentTime: 0,
  isPlaying: false,
  playbackSpeed: 1,
  showEventLog: true,
  selectedPair: "EURUSD",
  events: [],
  priceData: {},
  dateRange: {
    start: new Date(Date.now() - 7 * 24 * 60 * 60 * 1000),
    end: new Date(),
  },

  setSelectedTimeframe: (tf) => set({ selectedTimeframe: tf }),
  setCurrentTime: (time) => set({ currentTime: time }),
  setIsPlaying: (playing) => set({ isPlaying: playing }),
  togglePlayback: () => set((s) => ({ isPlaying: !s.isPlaying })),
  setPlaybackSpeed: (speed) => set({ playbackSpeed: speed }),
  toggleEventLog: () => set((s) => ({ showEventLog: !s.showEventLog })),
  setSelectedPair: (pair) => set({ selectedPair: pair }),
  setDateRange: (range) => set({ dateRange: range }),

  loadEventsForDateRange: async (start, end, pair) => {
    const [{ data: events, error: eventsError }, { data: candles }] =
      await Promise.all([
        supabase
          .from("trade_events")
          .select("*")
          .eq("pair", pair)
          .gte("timestamp", start.getTime())
          .lte("timestamp", end.getTime())
          .order("timestamp", { ascending: true }),

        supabase
          .from("candles")
          .select("*")
          .eq("pair", pair)
          .gte("time", start.getTime())
          .lte("time", end.getTime())
          .order("time", { ascending: true }),
      ]);

    if (eventsError) throw eventsError;

    const priceData: Record<string, Candle[]> = {
      "1m": candles?.filter((c) => c.timeframe === "1m") ?? [],
      "5m": candles?.filter((c) => c.timeframe === "5m") ?? [],
      "15m": candles?.filter((c) => c.timeframe === "15m") ?? [],
      "1h": candles?.filter((c) => c.timeframe === "1h") ?? [],
    };

    const startMs = start.getTime();
    set({
      events: events ?? [],
      priceData,
      currentTime: get().currentTime || startMs,
      dateRange: { start, end },
    });
  },

  addEvent: (event) =>
    set((s) => ({
      events: [...s.events, event].sort((a, b) => a.timestamp - b.timestamp),
    })),
}));
